"""
preprocess.py
-------------
Full preprocessing pipeline for NSL-KDD dataset:
  1. Load raw CSVs with correct column names
  2. Encode categorical features (protocol_type, service, flag)
  3. Binary label encoding (normal=0, attack=1)
  4. Remove low-variance / irrelevant features
  5. StandardScaler normalization
  6. SMOTE oversampling for class balance
  7. Save processed arrays + fitted scaler

Run:
    python ml/training/preprocess.py
"""

import sys
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parents[2]
RAW_DIR       = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
CHECKPOINT_DIR = BASE_DIR / "ml" / "checkpoints"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Column Definitions ───────────────────────────────────────────────────────
COLUMNS = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty_level",
]

# Categorical columns to one-hot encode:
CATEGORICAL_COLS = ["protocol_type", "service", "flag"]

# Columns to drop (not useful for classification):
DROP_COLS = [
    "difficulty_level",
    "num_outbound_cmds",   # always 0 in NSL-KDD
    "is_host_login",       # always 0
    "su_attempted",        # very low variance
]

# NSL-KDD attack categories → binary label mapping
ATTACK_MAP = {
    "normal": 0,
    # DoS
    "back": 1, "land": 1, "neptune": 1, "pod": 1, "smurf": 1,
    "teardrop": 1, "apache2": 1, "udpstorm": 1, "processtable": 1,
    "mailbomb": 1,
    # Probe
    "ipsweep": 1, "nmap": 1, "portsweep": 1, "satan": 1,
    "mscan": 1, "saint": 1,
    # R2L
    "ftp_write": 1, "guess_passwd": 1, "imap": 1, "multihop": 1,
    "phf": 1, "spy": 1, "warezclient": 1, "warezmaster": 1,
    "sendmail": 1, "named": 1, "snmpgetattack": 1, "snmpguess": 1,
    "xlock": 1, "xsnoop": 1, "worm": 1,
    # U2R
    "buffer_overflow": 1, "loadmodule": 1, "perl": 1, "rootkit": 1,
    "httptunnel": 1, "ps": 1, "sqlattack": 1, "xterm": 1,
}


def load_dataset(filepath: Path) -> pd.DataFrame:
    """Load NSL-KDD CSV with proper column names."""
    logger.info(f"Loading: {filepath.name}")

    # Determine number of columns in file:
    with open(filepath, "r") as f:
        first_line = f.readline()
    col_count = len(first_line.split(","))

    # Use full COLUMNS or without difficulty_level:
    cols = COLUMNS if col_count == len(COLUMNS) else COLUMNS[:-1]

    df = pd.read_csv(filepath, header=None, names=cols)
    logger.info(f"  Shape: {df.shape}")
    logger.info(f"  Label distribution:\n{df['label'].value_counts().head(10)}")
    return df


def encode_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Convert attack names to binary labels (0=normal, 1=attack)."""
    logger.info("Encoding labels (binary: normal=0, attack=1) ...")
    df = df.copy()
    df["label"] = df["label"].str.strip().str.lower()
    df["binary_label"] = df["label"].map(ATTACK_MAP)

    # Handle any unmapped labels (treat as attack):
    unmapped = df["binary_label"].isna().sum()
    if unmapped > 0:
        logger.warning(f"  {unmapped} unmapped labels → treating as attack (1)")
        df["binary_label"] = df["binary_label"].fillna(1)

    df["binary_label"] = df["binary_label"].astype(int)
    normal_count = (df["binary_label"] == 0).sum()
    attack_count = (df["binary_label"] == 1).sum()
    logger.info(f"  Normal: {normal_count:,} | Attack: {attack_count:,}")
    return df


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode protocol_type, service, flag."""
    logger.info("One-hot encoding categorical features ...")
    df = pd.get_dummies(df, columns=CATEGORICAL_COLS, dtype=float)
    logger.info(f"  Shape after encoding: {df.shape}")
    return df


def drop_unused_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove non-informative columns."""
    existing_drop = [c for c in DROP_COLS if c in df.columns]
    df = df.drop(columns=existing_drop + ["label"], errors="ignore")
    logger.info(f"  Dropped columns: {existing_drop + ['label']}")
    return df


def align_columns(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Ensure train and test have identical feature columns (fill missing with 0)."""
    logger.info("Aligning train/test feature columns ...")
    all_cols = sorted(set(train_df.columns) | set(test_df.columns))
    all_cols = [c for c in all_cols if c != "binary_label"]

    for col in all_cols:
        if col not in train_df.columns:
            train_df[col] = 0.0
        if col not in test_df.columns:
            test_df[col] = 0.0

    logger.info(f"  Total features: {len(all_cols)}")
    return train_df[all_cols + ["binary_label"]], test_df[all_cols + ["binary_label"]]


def scale_features(
    X_train: np.ndarray,
    X_val: np.ndarray,
    X_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """Fit StandardScaler on training data, transform all splits."""
    logger.info("Fitting StandardScaler on training features ...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled   = scaler.transform(X_val)
    X_test_scaled  = scaler.transform(X_test)

    # Save scaler for inference:
    scaler_path = CHECKPOINT_DIR / "scaler.pkl"
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    logger.success(f"  Scaler saved: {scaler_path}")

    return X_train_scaled, X_val_scaled, X_test_scaled, scaler


def apply_smote(
    X: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply SMOTE to balance classes in training set."""
    logger.info("Applying SMOTE for class balancing ...")
    before_dist = dict(zip(*np.unique(y, return_counts=True)))
    logger.info(f"  Before SMOTE: {before_dist}")

    smote = SMOTE(random_state=42, k_neighbors=5)
    X_res, y_res = smote.fit_resample(X, y)

    after_dist = dict(zip(*np.unique(y_res, return_counts=True)))
    logger.info(f"  After SMOTE:  {after_dist}")
    return X_res, y_res


def save_arrays(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val:   np.ndarray, y_val:   np.ndarray,
    X_test:  np.ndarray, y_test:  np.ndarray,
    feature_names: list[str],
) -> None:
    """Save processed numpy arrays and feature metadata."""
    logger.info(f"Saving processed arrays to: {PROCESSED_DIR}")

    np.save(PROCESSED_DIR / "X_train.npy", X_train)
    np.save(PROCESSED_DIR / "y_train.npy", y_train)
    np.save(PROCESSED_DIR / "X_val.npy",   X_val)
    np.save(PROCESSED_DIR / "y_val.npy",   y_val)
    np.save(PROCESSED_DIR / "X_test.npy",  X_test)
    np.save(PROCESSED_DIR / "y_test.npy",  y_test)

    # Save feature names list for inference reference:
    feat_path = PROCESSED_DIR / "feature_names.pkl"
    with open(feat_path, "wb") as f:
        pickle.dump(feature_names, f)

    logger.success("  All arrays saved!")
    logger.info(f"  X_train: {X_train.shape} | y_train: {y_train.shape}")
    logger.info(f"  X_val:   {X_val.shape}   | y_val:   {y_val.shape}")
    logger.info(f"  X_test:  {X_test.shape}  | y_test:  {y_test.shape}")
    logger.info(f"  Features: {len(feature_names)}")


def main() -> None:
    logger.add(
        BASE_DIR / "logs" / "preprocess.log",
        rotation="10 MB",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    logger.info("=" * 60)
    logger.info("NSL-KDD Preprocessing Pipeline")
    logger.info("=" * 60)

    # ── 1. Load raw files ──────────────────────────────────────────
    train_path = RAW_DIR / "KDDTrain+.csv"
    test_path  = RAW_DIR / "KDDTest+.csv"

    if not train_path.exists() or not test_path.exists():
        logger.error("Dataset files not found! Run download_dataset.py first.")
        sys.exit(1)

    train_df = load_dataset(train_path)
    test_df  = load_dataset(test_path)

    # ── 2. Encode labels ───────────────────────────────────────────
    train_df = encode_labels(train_df)
    test_df  = encode_labels(test_df)

    # ── 3. Encode categoricals ─────────────────────────────────────
    train_df = encode_categoricals(train_df)
    test_df  = encode_categoricals(test_df)

    # ── 4. Drop unused columns ─────────────────────────────────────
    train_df = drop_unused_columns(train_df)
    test_df  = drop_unused_columns(test_df)

    # ── 5. Align columns ───────────────────────────────────────────
    train_df, test_df = align_columns(train_df, test_df)

    # ── 6. Separate features / labels ─────────────────────────────
    feature_names = [c for c in train_df.columns if c != "binary_label"]
    X_full  = train_df[feature_names].values.astype(np.float32)
    y_full  = train_df["binary_label"].values.astype(np.float32)
    X_test  = test_df[feature_names].values.astype(np.float32)
    y_test  = test_df["binary_label"].values.astype(np.float32)

    # ── 7. Train / Validation split (80/20 of training set) ────────
    logger.info("Splitting train → train/val (80/20) ...")
    X_train, X_val, y_train, y_val = train_test_split(
        X_full, y_full,
        test_size=0.2,
        random_state=42,
        stratify=y_full,
    )
    logger.info(f"  Train: {X_train.shape} | Val: {X_val.shape}")

    # ── 8. Scale features ──────────────────────────────────────────
    X_train_s, X_val_s, X_test_s, _ = scale_features(X_train, X_val, X_test)

    # ── 9. SMOTE on training set only ─────────────────────────────
    X_train_balanced, y_train_balanced = apply_smote(X_train_s, y_train)

    # ── 10. Save everything ────────────────────────────────────────
    save_arrays(
        X_train_balanced, y_train_balanced,
        X_val_s, y_val,
        X_test_s, y_test,
        feature_names,
    )

    logger.success("=" * 60)
    logger.success("Preprocessing complete!")
    logger.success("=" * 60)
    logger.info("Next step: python ml/training/train.py")


if __name__ == "__main__":
    main()
