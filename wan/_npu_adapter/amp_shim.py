"""Device-aware drop-in for ``torch.cuda.amp``.

The Wan model files (``wan/modules/{model,multitalk_model,vae}.py``) use
``import torch.cuda.amp as amp`` and rely on ``with amp.autocast(...)`` to
force fp32 islands inside an otherwise bf16 model graph. On NPU host
``torch.cuda.amp.autocast`` is a silent no-op (it dispatches only to the
CUDA backend), so the fp32 protection collapses and downstream
``assert e.dtype == torch.float32`` checks fail.

This shim provides ``autocast`` that auto-resolves the device backend
('npu' when ``torch.npu`` is loaded, otherwise 'cuda'). Replacing
``import torch.cuda.amp as amp`` with
``from wan._npu_adapter import amp_shim as amp`` keeps every call site
(``with amp.autocast(...)`` blocks AND ``@amp.autocast(enabled=False)``
decorators) working on both backends without further edits.

Use ``torch.amp.autocast(device_type, ...)`` directly when the device
context is explicit; this shim is for legacy code paths that hardcode
the cuda namespace.
"""
import torch


def _resolve_device_type():
    if hasattr(torch, "npu") and getattr(torch.npu, "is_available", lambda: False)():
        return "npu"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class autocast(torch.amp.autocast_mode.autocast):
    """``torch.cuda.amp.autocast`` substitute that picks the live backend."""

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            super().__init__(*args, **kwargs)
            return
        super().__init__(_resolve_device_type(), *args, **kwargs)
