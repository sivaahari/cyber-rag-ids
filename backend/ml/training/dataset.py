"""
dataset.py
----------
PyTorch Dataset wrapper for the preprocessed NSL-KDD numpy arrays.
Reshapes flat feature vectors into LSTM sequences (seq_len=1, features=N).
"""

from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset


class IDSDataset(Dataset):
    """
    PyTorch Dataset for IDS binary classification.

    The LSTM expects input of shape (batch, seq_len, features).
    We treat each row as a sequence of length 1 (single time step).
    For real packet streams, seq_len can be increased to capture temporal patterns.
    """

    def __init__(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Args:
            X: Feature array of shape (N, num_features), dtype float32
            y: Label array of shape (N,), dtype float32 (0.0 or 1.0)
        """
        # Add sequence dimension: (N, features) → (N, 1, features)
        self.X = torch.tensor(X, dtype=torch.float32).unsqueeze(1)
        self.y = torch.tensor(y, dtype=torch.float32).unsqueeze(1)  # (N, 1)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]

    @classmethod
    def from_numpy_files(cls, x_path: Path, y_path: Path) -> "IDSDataset":
        """Load directly from saved .npy files."""
        X = np.load(x_path).astype(np.float32)
        y = np.load(y_path).astype(np.float32)
        return cls(X, y)

    @property
    def num_features(self) -> int:
        """Number of input features."""
        return self.X.shape[2]

    @property
    def pos_weight(self) -> torch.Tensor:
        """
        Compute positive class weight for BCEWithLogitsLoss.
        pos_weight = num_negatives / num_positives
        """
        labels = self.y.squeeze()
        n_neg = (labels == 0).sum().float()
        n_pos = (labels == 1).sum().float()
        return n_neg / (n_pos + 1e-8)
