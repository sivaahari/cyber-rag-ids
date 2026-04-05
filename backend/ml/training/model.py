"""
model.py
--------
LSTM-based Intrusion Detection System classifier.

Architecture:
    Input  → (batch, seq_len=1, num_features)
    LSTM 1 → hidden_size=128, dropout=0.3
    LSTM 2 → hidden_size=64,  dropout=0.3
    FC 1   → 64 → 32, ReLU
    FC 2   → 32 → 1  (raw logit, no sigmoid — BCEWithLogitsLoss)
    Output → sigmoid(logit) gives probability of attack

For inference:
    prob = sigmoid(model(x))
    pred = 1 if prob > threshold else 0
"""

import torch
import torch.nn as nn
from loguru import logger


class LSTMClassifier(nn.Module):
    """
    Two-layer stacked LSTM for binary network intrusion detection.

    Args:
        num_features: Number of input features per time step
        hidden_size:  LSTM hidden state size (first layer)
        num_layers:   Number of stacked LSTM layers
        dropout:      Dropout probability between LSTM layers
        fc_hidden:    Hidden size of the fully-connected head
    """

    def __init__(
        self,
        num_features: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        fc_hidden: int = 32,
    ) -> None:
        super().__init__()

        self.num_features = num_features
        self.hidden_size  = hidden_size
        self.num_layers   = num_layers

        # ── LSTM Encoder ──────────────────────────────────────────────────────
        # batch_first=True → input shape: (batch, seq_len, features)
        self.lstm = nn.LSTM(
            input_size=num_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=False,
        )

        # ── Classifier Head ───────────────────────────────────────────────────
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, fc_hidden * 2),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(fc_hidden * 2, fc_hidden),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(fc_hidden, 1),
            # No sigmoid here — use BCEWithLogitsLoss during training
            # Apply sigmoid explicitly during inference
        )

        # Weight initialization:
        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize LSTM weights with orthogonal init, biases to zero."""
        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name:
                nn.init.kaiming_uniform_(param, nonlinearity="relu")
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)
                # Set forget gate bias to 1 (helps with long sequences)
                n = param.size(0)
                param.data[n // 4: n // 2].fill_(1.0)

        for layer in self.head:
            if isinstance(layer, nn.Linear):
                nn.init.kaiming_uniform_(layer.weight, nonlinearity="relu")
                nn.init.zeros_(layer.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, num_features)

        Returns:
            Logit tensor of shape (batch, 1) — raw (pre-sigmoid) scores
        """
        # LSTM forward: output shape (batch, seq_len, hidden_size)
        lstm_out, _ = self.lstm(x)

        # Take the last time step's hidden state:
        last_hidden = lstm_out[:, -1, :]  # (batch, hidden_size)

        # Classifier head:
        logits = self.head(last_hidden)   # (batch, 1)
        return logits

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """
        Convenience method: forward pass + sigmoid → probability.

        Args:
            x: Input tensor (batch, seq_len, num_features)

        Returns:
            Probability tensor (batch, 1), values in [0, 1]
        """
        logits = self.forward(x)
        return torch.sigmoid(logits)

    def predict(self, x: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
        """
        Binary prediction.

        Returns:
            Integer tensor (batch, 1): 0 = Normal, 1 = Attack
        """
        proba = self.predict_proba(x)
        return (proba >= threshold).long()

    def get_model_info(self) -> dict:
        """Return model metadata dict for logging / API responses."""
        total_params     = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        return {
            "architecture": "LSTM",
            "num_features": self.num_features,
            "hidden_size":  self.hidden_size,
            "num_layers":   self.num_layers,
            "total_params": total_params,
            "trainable_params": trainable_params,
        }


def load_model(
    checkpoint_path: str,
    num_features: int,
    device: torch.device | None = None,
) -> LSTMClassifier:
    """
    Load a saved LSTM model from checkpoint.

    Args:
        checkpoint_path: Path to .pt checkpoint file
        num_features:    Number of input features (must match training)
        device:          torch.device to load model onto

    Returns:
        Loaded LSTMClassifier in eval mode
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Support both raw state_dict and wrapped checkpoint:
    if "model_state_dict" in checkpoint:
        state_dict   = checkpoint["model_state_dict"]
        model_config = checkpoint.get("model_config", {})
    else:
        state_dict   = checkpoint
        model_config = {}

    model = LSTMClassifier(
        num_features=model_config.get("num_features", num_features),
        hidden_size=model_config.get("hidden_size", 128),
        num_layers=model_config.get("num_layers", 2),
        dropout=model_config.get("dropout", 0.3),
        fc_hidden=model_config.get("fc_hidden", 32),
    )
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    info = model.get_model_info()
    logger.info(f"Model loaded from {checkpoint_path}")
    logger.info(f"  Parameters: {info['total_params']:,}")
    logger.info(f"  Device: {device}")

    return model
