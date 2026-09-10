"""Device / dtype selection (Phase 13 — optimization).

Automatically uses the GPU (CUDA, float16) when one is available — e.g. on the
Hugging Face Spaces T4 — and falls back to CPU (float32) for local dev. Model
loaders call get_device() so the same code runs fast in production without any
code change; on a CPU-only machine the behaviour is unchanged.
"""
from __future__ import annotations

from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_device() -> str:
    """Return 'cuda' if a GPU is available, else 'cpu'. Never raises.

    Does not import torch unless it is actually installed — so LITE_MODE hosts
    (which ship without torch) stay lightweight.
    """
    import importlib.util
    if importlib.util.find_spec("torch") is None:
        return "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception as exc:  # torch broken → safe CPU fallback
        logger.debug("CUDA check failed (%s) — using CPU.", exc)
    return "cpu"


def get_dtype():
    """float16 on GPU, float32 on CPU."""
    import torch
    return torch.float16 if get_device() == "cuda" else torch.float32
