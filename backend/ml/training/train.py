"""
train.py
--------
Full LSTM training loop with:
  - Cosine annealing LR scheduler
  - Early stopping (patience=10)
  - Per-epoch metrics (Accuracy, Precision, Recall, F1, AUC-ROC)
  - Best checkpoint saving
  - Final evaluation on test set
  - Training history saved as JSON

Run:
    python ml/training/train.py
    python ml/training/train.py --epochs 30 --batch-size 512 --lr 0.001
"""

import argparse
import json
import time
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, BarColumn,
    TextColumn, TimeElapsedColumn, TimeRemainingColumn,
)

# Local imports:
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml.training.dataset import IDSDataset
from ml.training.model import LSTMClassifier

console = Console()

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parents[2]
PROCESSED_DIR  = BASE_DIR / "data" / "processed"
CHECKPOINT_DIR = BASE_DIR / "ml" / "checkpoints"
LOG_DIR        = BASE_DIR / "logs"


# ─── Metrics Helper ───────────────────────────────────────────────────────────
def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
) -> dict:
    """Compute all classification metrics."""
    return {
        "accuracy":  float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall":    float(recall_score(y_true, y_pred, zero_division=0)),
        "f1":        float(f1_score(y_true, y_pred, zero_division=0)),
        "auc_roc":   float(roc_auc_score(y_true, y_prob)),
    }


# ─── Evaluation Function ──────────────────────────────────────────────────────
@torch.no_grad()
def evaluate(
    model: LSTMClassifier,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    threshold: float = 0.5,
) -> tuple[float, dict]:
    """Run full evaluation on a DataLoader, return (loss, metrics_dict)."""
    model.eval()
    all_losses = []
    all_probs  = []
    all_preds  = []
    all_labels = []

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)

        logits = model(X_batch)
        loss   = criterion(logits, y_batch)
        probs  = torch.sigmoid(logits)
        preds  = (probs >= threshold).float()

        all_losses.append(loss.item())
        all_probs.extend(probs.cpu().numpy().flatten().tolist())
        all_preds.extend(preds.cpu().numpy().flatten().tolist())
        all_labels.extend(y_batch.cpu().numpy().flatten().tolist())

    avg_loss = float(np.mean(all_losses))
    metrics  = compute_metrics(
        np.array(all_labels),
        np.array(all_preds),
        np.array(all_probs),
    )
    return avg_loss, metrics


# ─── Training Loop ────────────────────────────────────────────────────────────
def train(args: argparse.Namespace) -> None:
    logger.add(
        LOG_DIR / "training.log",
        rotation="50 MB",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    # ── Device setup ──────────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    console.print(f"\n[bold cyan]Device:[/bold cyan] {device}")
    if device.type == "cuda":
        console.print(f"  GPU: {torch.cuda.get_device_name(0)}")
        console.print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory // 1024**2} MB")

    # ── Load datasets ─────────────────────────────────────────────
    console.print("\n[bold cyan]Loading datasets...[/bold cyan]")
    for split in ["X_train", "y_train", "X_val", "y_val", "X_test", "y_test"]:
        fpath = PROCESSED_DIR / f"{split}.npy"
        if not fpath.exists():
            logger.error(f"Missing: {fpath}")
            console.print(f"[red]ERROR: Run preprocess.py first![/red]")
            sys.exit(1)

    train_ds = IDSDataset.from_numpy_files(
        PROCESSED_DIR / "X_train.npy",
        PROCESSED_DIR / "y_train.npy",
    )
    val_ds = IDSDataset.from_numpy_files(
        PROCESSED_DIR / "X_val.npy",
        PROCESSED_DIR / "y_val.npy",
    )
    test_ds = IDSDataset.from_numpy_files(
        PROCESSED_DIR / "X_test.npy",
        PROCESSED_DIR / "y_test.npy",
    )

    num_features = train_ds.num_features
    console.print(f"  Train samples: {len(train_ds):,}")
    console.print(f"  Val samples:   {len(val_ds):,}")
    console.print(f"  Test samples:  {len(test_ds):,}")
    console.print(f"  Features:      {num_features}")

    # ── DataLoaders ───────────────────────────────────────────────
    pin_memory = (device.type == "cuda")
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,      # 0 on Windows (avoids multiprocessing issues)
        pin_memory=pin_memory,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size * 2,
        shuffle=False,
        num_workers=0,
        pin_memory=pin_memory,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=args.batch_size * 2,
        shuffle=False,
        num_workers=0,
        pin_memory=pin_memory,
    )

    # ── Model ─────────────────────────────────────────────────────
    model = LSTMClassifier(
        num_features=num_features,
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
        fc_hidden=32,
    ).to(device)

    info = model.get_model_info()
    console.print(f"\n[bold cyan]Model:[/bold cyan] {info['architecture']}")
    console.print(f"  Parameters: {info['total_params']:,}")

    # ── Loss, Optimizer, Scheduler ────────────────────────────────
    # Use BCEWithLogitsLoss (numerically stable, includes sigmoid)
    pos_weight = train_ds.pos_weight.to(device)
    criterion  = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.lr,
        weight_decay=1e-5,
        betas=(0.9, 0.999),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=1e-6,
    )

    # ── Training State ────────────────────────────────────────────
    best_val_f1    = 0.0
    best_epoch     = 0
    patience_count = 0
    history        = []

    checkpoint_path = CHECKPOINT_DIR / "lstm_ids.pt"

    console.print(f"\n[bold green]Starting training for {args.epochs} epochs...[/bold green]")
    console.print(f"  Batch size:    {args.batch_size}")
    console.print(f"  Learning rate: {args.lr}")
    console.print(f"  Early stopping patience: {args.patience}")
    console.print()

    # ── Epoch Loop ────────────────────────────────────────────────
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_losses = []
        t0 = time.time()

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]Epoch {epoch:02d}/{args.epochs}[/cyan]"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Training", total=len(train_loader))

            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(device, non_blocking=True)
                y_batch = y_batch.to(device, non_blocking=True)

                optimizer.zero_grad(set_to_none=True)
                logits = model(X_batch)
                loss   = criterion(logits, y_batch)
                loss.backward()

                # Gradient clipping (prevents exploding gradients):
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

                optimizer.step()
                epoch_losses.append(loss.item())
                progress.advance(task)

        # LR step:
        scheduler.step()
        current_lr = scheduler.get_last_lr()[0]

        # ── Validation ────────────────────────────────────────────
        train_loss = float(np.mean(epoch_losses))
        val_loss, val_metrics = evaluate(model, val_loader, criterion, device)

        elapsed = time.time() - t0
        val_f1  = val_metrics["f1"]

        # Log to history:
        history.append({
            "epoch":      epoch,
            "train_loss": round(train_loss, 6),
            "val_loss":   round(val_loss, 6),
            "lr":         round(current_lr, 8),
            **{f"val_{k}": round(v, 6) for k, v in val_metrics.items()},
        })

        # ── Print epoch summary ───────────────────────────────────
        console.print(
            f"  Epoch [{epoch:02d}/{args.epochs}] "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_loss:.4f} | "
            f"Val F1: {val_f1:.4f} | "
            f"Val AUC: {val_metrics['auc_roc']:.4f} | "
            f"LR: {current_lr:.6f} | "
            f"Time: {elapsed:.1f}s"
        )
        logger.info(
            f"Epoch {epoch:02d} | "
            f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"val_f1={val_f1:.4f} val_auc={val_metrics['auc_roc']:.4f}"
        )

        # ── Checkpoint if best ────────────────────────────────────
        if val_f1 > best_val_f1:
            best_val_f1  = val_f1
            best_epoch   = epoch
            patience_count = 0

            torch.save(
                {
                    "epoch":            epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_f1":           val_f1,
                    "val_metrics":      val_metrics,
                    "model_config": {
                        "num_features": num_features,
                        "hidden_size":  args.hidden_size,
                        "num_layers":   args.num_layers,
                        "dropout":      args.dropout,
                        "fc_hidden":    32,
                    },
                },
                checkpoint_path,
            )
            console.print(
                f"    [bold green]✓ New best model saved! "
                f"Val F1: {best_val_f1:.4f} (Epoch {epoch})[/bold green]"
            )
        else:
            patience_count += 1
            if patience_count >= args.patience:
                console.print(
                    f"\n[yellow]Early stopping triggered "
                    f"(patience={args.patience}, best epoch={best_epoch})[/yellow]"
                )
                break

    # ── Final Test Evaluation ─────────────────────────────────────
    console.print("\n[bold cyan]Loading best checkpoint for final evaluation...[/bold cyan]")
    best_ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(best_ckpt["model_state_dict"])

    test_loss, test_metrics = evaluate(model, test_loader, criterion, device)

    # ── Confusion Matrix ──────────────────────────────────────────
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            logits = model(X_batch.to(device))
            preds  = (torch.sigmoid(logits) >= 0.5).float()
            all_preds.extend(preds.cpu().numpy().flatten())
            all_labels.extend(y_batch.numpy().flatten())

    cm = confusion_matrix(all_labels, all_preds)
    tn, fp, fn, tp = cm.ravel()

    # ── Results Table ─────────────────────────────────────────────
    table = Table(title="Final Test Set Results", style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Test Loss",         f"{test_loss:.4f}")
    table.add_row("Accuracy",          f"{test_metrics['accuracy']:.4f}")
    table.add_row("Precision",         f"{test_metrics['precision']:.4f}")
    table.add_row("Recall",            f"{test_metrics['recall']:.4f}")
    table.add_row("F1 Score",          f"{test_metrics['f1']:.4f}")
    table.add_row("AUC-ROC",           f"{test_metrics['auc_roc']:.4f}")
    table.add_row("True Positives",    str(tp))
    table.add_row("True Negatives",    str(tn))
    table.add_row("False Positives",   str(fp))
    table.add_row("False Negatives",   str(fn))
    table.add_row("False Positive Rate", f"{fp / (fp + tn):.4f}")
    table.add_row("Best Epoch",        str(best_epoch))

    console.print()
    console.print(table)

    # ── Save training history ─────────────────────────────────────
    history_path = CHECKPOINT_DIR / "training_history.json"
    with open(history_path, "w") as f:
        json.dump(
            {
                "config": vars(args),
                "best_epoch": best_epoch,
                "best_val_f1": best_val_f1,
                "test_metrics": test_metrics,
                "history": history,
            },
            f, indent=2,
        )
    logger.info(f"Training history saved: {history_path}")

    console.print(f"\n[bold green]Training complete![/bold green]")
    console.print(f"  Best model: {checkpoint_path}")
    console.print(f"  Best Val F1: {best_val_f1:.4f} at epoch {best_epoch}")


# ─── CLI ──────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train LSTM IDS Model")
    p.add_argument("--epochs",      type=int,   default=50,   help="Max training epochs")
    p.add_argument("--batch-size",  type=int,   default=256,  help="Batch size")
    p.add_argument("--lr",          type=float, default=1e-3, help="Initial learning rate")
    p.add_argument("--hidden-size", type=int,   default=128,  help="LSTM hidden size")
    p.add_argument("--num-layers",  type=int,   default=2,    help="LSTM layers")
    p.add_argument("--dropout",     type=float, default=0.3,  help="Dropout probability")
    p.add_argument("--patience",    type=int,   default=10,   help="Early stopping patience")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
