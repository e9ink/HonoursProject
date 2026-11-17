"""
Restricted unpickler for DEAP .dat files.

Allows only the three numpy types present in both v1 (pickle protocol 2,
GLOBAL opcode) and v2 (pickle protocol 4, STACK_GLOBAL opcode) mirrors.
Both protocols invoke find_class, so a single allow-list covers both.

Usage:
    from deap.src.loader import load_dat
    data = load_dat("bronze/DEAP/deap-dataset/data_preprocessed_python/s01.dat")
    # data["data"]: numpy array (40, 40, 8064)
    # data["labels"]: numpy array (40, 4)
"""

import io
import pickle


ALLOWED = {
    ("numpy.core.multiarray", "_reconstruct"),   # NumPy < 2.0
    ("numpy._core.multiarray", "_reconstruct"),  # NumPy >= 2.0
    ("numpy", "ndarray"),
    ("numpy", "dtype"),
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Refused: {module}.{name} not in allow-list"
        )


def load_dat(path: str) -> dict:
    """Load a DEAP .dat file. Returns dict with 'data' and 'labels' arrays."""
    with open(path, "rb") as fh:
        return RestrictedUnpickler(fh, encoding="latin1").load()


def load_dat_bytes(data: bytes) -> dict:
    """Load a DEAP .dat from raw bytes (used by fault injection)."""
    return RestrictedUnpickler(io.BytesIO(data), encoding="latin1").load()
