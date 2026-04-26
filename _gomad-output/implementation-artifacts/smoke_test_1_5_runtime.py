#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Story 1.5 runtime helper smoke surrogate (dispatch routing only) — AC-9 evidence.

NOTE on ordering: this harness pre-injects a mock `torch.npu` submodule
directly (bypassing the `set_device → _import_torch_npu` chain). It does
NOT verify the real-path ordering invariant that `set_device(...)` must
run before any helper. That invariant is enforced by control-flow in
`generate_infinitetalk.py:474` (Story 1.2's `set_device(...)` call) and
is exercised only in the J1 manual hardware verification (AC-1).

6 cases:
  CASE 1 — cuda + device_empty_cache → torch.cuda.empty_cache spy hit
  CASE 2 — cuda + device_ipc_collect → torch.cuda.ipc_collect spy hit
  CASE 3 — cuda + device_manual_seed_all(seed=42) → torch.cuda.manual_seed_all(42) hit
  CASE 4 — cuda + device_synchronize → torch.cuda.synchronize spy hit
  CASE 5 — npu + 4 helper → torch.npu.* spy hit (mock torch.npu submodule)
  CASE 6 — device.type='mps' → 4 helper all raise ValueError("Unsupported device.type='mps'")

输出格式与 PR 留痕兼容：每个 case 标注 case 编号 + stdout/stderr。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


class _CallSpy:
    def __init__(self, name: str, return_value=None):
        self.name = name
        self.calls = []
        self.return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_value


class _MockDevice:
    """Mock `torch.device` exposing only `.type` (the only attribute the helpers consume)."""

    def __init__(self, dev_type: str):
        self.type = dev_type

    def __repr__(self):
        return f"_MockDevice(type={self.type!r})"


def _purge_runtime_module():
    sys.modules.pop("wan._npu_adapter.runtime", None)


def _purge_torch_npu_modules():
    for name in list(sys.modules):
        if name == "torch_npu" or name.startswith("torch_npu."):
            sys.modules.pop(name, None)


def _load_runtime_with_mock_torch(cuda_spies: dict, npu_namespace=None):
    """Inject a mock `torch` module (with .cuda spies and optional .npu namespace),
    then load `wan/_npu_adapter/runtime.py` from source so it picks up the mock.

    Returns the loaded runtime module.
    """
    import importlib.util

    # Build mock torch module
    mock_torch = types.ModuleType("torch")
    mock_cuda = types.SimpleNamespace(**cuda_spies)
    mock_torch.cuda = mock_cuda  # type: ignore[attr-defined]
    if npu_namespace is not None:
        mock_torch.npu = npu_namespace  # type: ignore[attr-defined]

    # Save and replace
    saved_torch = sys.modules.get("torch")
    sys.modules["torch"] = mock_torch

    # Purge cached runtime so it re-imports against mocked torch
    _purge_runtime_module()

    try:
        spec = importlib.util.spec_from_file_location(
            "wan._npu_adapter.runtime",
            str(REPO_ROOT / "wan" / "_npu_adapter" / "runtime.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wan._npu_adapter.runtime"] = mod
        spec.loader.exec_module(mod)
        return mod, saved_torch
    except Exception:
        # restore on failure
        if saved_torch is not None:
            sys.modules["torch"] = saved_torch
        else:
            sys.modules.pop("torch", None)
        raise


def _restore_torch(saved_torch):
    if saved_torch is not None:
        sys.modules["torch"] = saved_torch
    else:
        sys.modules.pop("torch", None)
    _purge_runtime_module()


def case_1_cuda_empty_cache() -> int:
    print("=" * 72)
    print("[CASE 1] cuda device → torch.cuda.empty_cache spy")
    print("-" * 72)
    spy = _CallSpy("empty_cache")
    cuda_spies = {
        "empty_cache": spy,
        "ipc_collect": _CallSpy("ipc_collect"),
        "manual_seed_all": _CallSpy("manual_seed_all"),
        "synchronize": _CallSpy("synchronize"),
    }
    runtime, saved = _load_runtime_with_mock_torch(cuda_spies)
    try:
        dev = _MockDevice("cuda")
        runtime.device_empty_cache(dev)
        print(f"  empty_cache spy.calls = {spy.calls}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"
        assert spy.calls[0] == ((), {}), f"unexpected args: {spy.calls[0]}"
        print("[CASE 1] PASS — cuda device_empty_cache routes to torch.cuda.empty_cache")
        return 0
    finally:
        _restore_torch(saved)


def case_2_cuda_ipc_collect() -> int:
    print()
    print("=" * 72)
    print("[CASE 2] cuda device → torch.cuda.ipc_collect spy")
    print("-" * 72)
    spy = _CallSpy("ipc_collect")
    cuda_spies = {
        "empty_cache": _CallSpy("empty_cache"),
        "ipc_collect": spy,
        "manual_seed_all": _CallSpy("manual_seed_all"),
        "synchronize": _CallSpy("synchronize"),
    }
    runtime, saved = _load_runtime_with_mock_torch(cuda_spies)
    try:
        dev = _MockDevice("cuda")
        runtime.device_ipc_collect(dev)
        print(f"  ipc_collect spy.calls = {spy.calls}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"
        assert spy.calls[0] == ((), {}), f"unexpected args: {spy.calls[0]}"
        print("[CASE 2] PASS — cuda device_ipc_collect routes to torch.cuda.ipc_collect")
        return 0
    finally:
        _restore_torch(saved)


def case_3_cuda_manual_seed_all() -> int:
    print()
    print("=" * 72)
    print("[CASE 3] cuda device → torch.cuda.manual_seed_all(42) spy")
    print("-" * 72)
    spy = _CallSpy("manual_seed_all")
    cuda_spies = {
        "empty_cache": _CallSpy("empty_cache"),
        "ipc_collect": _CallSpy("ipc_collect"),
        "manual_seed_all": spy,
        "synchronize": _CallSpy("synchronize"),
    }
    runtime, saved = _load_runtime_with_mock_torch(cuda_spies)
    try:
        dev = _MockDevice("cuda")
        runtime.device_manual_seed_all(dev, 42)
        print(f"  manual_seed_all spy.calls = {spy.calls}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"
        assert spy.calls[0] == ((42,), {}), f"unexpected args: {spy.calls[0]}"
        print("[CASE 3] PASS — cuda device_manual_seed_all routes with seed forwarded")
        return 0
    finally:
        _restore_torch(saved)


def case_4_cuda_synchronize() -> int:
    print()
    print("=" * 72)
    print("[CASE 4] cuda device → torch.cuda.synchronize spy")
    print("-" * 72)
    spy = _CallSpy("synchronize")
    cuda_spies = {
        "empty_cache": _CallSpy("empty_cache"),
        "ipc_collect": _CallSpy("ipc_collect"),
        "manual_seed_all": _CallSpy("manual_seed_all"),
        "synchronize": spy,
    }
    runtime, saved = _load_runtime_with_mock_torch(cuda_spies)
    try:
        dev = _MockDevice("cuda")
        runtime.device_synchronize(dev)
        print(f"  synchronize spy.calls = {spy.calls}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"
        assert spy.calls[0] == ((), {}), f"unexpected args: {spy.calls[0]}"
        print("[CASE 4] PASS — cuda device_synchronize routes to torch.cuda.synchronize")
        return 0
    finally:
        _restore_torch(saved)


def case_5_npu_all_four_helpers() -> int:
    print()
    print("=" * 72)
    print("[CASE 5] npu device → 4 helper hit torch.npu.* spies")
    print("-" * 72)

    # cuda spies should NOT be touched on npu path
    cuda_empty = _CallSpy("cuda.empty_cache")
    cuda_ipc = _CallSpy("cuda.ipc_collect")
    cuda_seed = _CallSpy("cuda.manual_seed_all")
    cuda_sync = _CallSpy("cuda.synchronize")
    cuda_spies = {
        "empty_cache": cuda_empty,
        "ipc_collect": cuda_ipc,
        "manual_seed_all": cuda_seed,
        "synchronize": cuda_sync,
    }

    # npu spies
    npu_empty = _CallSpy("npu.empty_cache")
    npu_ipc = _CallSpy("npu.ipc_collect")
    npu_seed = _CallSpy("npu.manual_seed_all")
    npu_sync = _CallSpy("npu.synchronize")
    npu_namespace = types.SimpleNamespace(
        empty_cache=npu_empty,
        ipc_collect=npu_ipc,
        manual_seed_all=npu_seed,
        synchronize=npu_sync,
    )

    runtime, saved = _load_runtime_with_mock_torch(cuda_spies, npu_namespace=npu_namespace)
    try:
        dev = _MockDevice("npu")
        runtime.device_empty_cache(dev)
        runtime.device_ipc_collect(dev)
        runtime.device_manual_seed_all(dev, 7)
        runtime.device_synchronize(dev)

        print(f"  npu.empty_cache calls    = {npu_empty.calls}")
        print(f"  npu.ipc_collect calls    = {npu_ipc.calls}")
        print(f"  npu.manual_seed_all calls= {npu_seed.calls}")
        print(f"  npu.synchronize calls    = {npu_sync.calls}")
        assert len(npu_empty.calls) == 1, f"npu.empty_cache: {npu_empty.calls}"
        assert len(npu_ipc.calls) == 1, f"npu.ipc_collect: {npu_ipc.calls}"
        assert len(npu_seed.calls) == 1 and npu_seed.calls[0] == ((7,), {}), \
            f"npu.manual_seed_all: {npu_seed.calls}"
        assert len(npu_sync.calls) == 1, f"npu.synchronize: {npu_sync.calls}"

        # cuda branches must NOT have been touched on npu path
        assert len(cuda_empty.calls) == 0, f"cuda.empty_cache leaked on npu path: {cuda_empty.calls}"
        assert len(cuda_ipc.calls) == 0, f"cuda.ipc_collect leaked on npu path: {cuda_ipc.calls}"
        assert len(cuda_seed.calls) == 0, f"cuda.manual_seed_all leaked on npu path: {cuda_seed.calls}"
        assert len(cuda_sync.calls) == 0, f"cuda.synchronize leaked on npu path: {cuda_sync.calls}"

        print("[CASE 5] PASS — npu path routes to torch.npu.* without touching cuda branches")
        return 0
    finally:
        _restore_torch(saved)


def case_6_unsupported_device_type_mps() -> int:
    print()
    print("=" * 72)
    print("[CASE 6] device.type='mps' → 4 helper raise ValueError")
    print("-" * 72)
    cuda_spies = {
        "empty_cache": _CallSpy("empty_cache"),
        "ipc_collect": _CallSpy("ipc_collect"),
        "manual_seed_all": _CallSpy("manual_seed_all"),
        "synchronize": _CallSpy("synchronize"),
    }
    runtime, saved = _load_runtime_with_mock_torch(cuda_spies)
    try:
        dev = _MockDevice("mps")
        for name, fn in [
            ("device_empty_cache", lambda: runtime.device_empty_cache(dev)),
            ("device_ipc_collect", lambda: runtime.device_ipc_collect(dev)),
            ("device_manual_seed_all", lambda: runtime.device_manual_seed_all(dev, 0)),
            ("device_synchronize", lambda: runtime.device_synchronize(dev)),
        ]:
            try:
                fn()
            except ValueError as exc:
                msg = str(exc)
                print(f"  {name} raised ValueError: {msg}")
                assert "Unsupported device.type='mps'" in msg, \
                    f"message must contain \"Unsupported device.type='mps'\": {msg!r}"
            else:
                print(f"[CASE 6] FAIL — {name} did not raise ValueError on mps", file=sys.stderr)
                return 6

        print("[CASE 6] PASS — all 4 helpers raise ValueError(\"Unsupported device.type='mps'\")")
        return 0
    finally:
        _restore_torch(saved)


def _assert_no_torch_npu_in_sys_modules() -> int:
    leaked = [n for n in sys.modules if n == "torch_npu" or n.startswith("torch_npu.")]
    print()
    print("=" * 72)
    print(f"[POST] sys.modules torch_npu* check: {leaked}")
    if leaked:
        print(f"[POST] FAIL — torch_npu leaked into sys.modules", file=sys.stderr)
        return 1
    print("[POST] PASS — no torch_npu in sys.modules (cuda path zero side-effect)")
    return 0


def main() -> int:
    rc = 0
    for case in (
        case_1_cuda_empty_cache,
        case_2_cuda_ipc_collect,
        case_3_cuda_manual_seed_all,
        case_4_cuda_synchronize,
        case_5_npu_all_four_helpers,
        case_6_unsupported_device_type_mps,
    ):
        rc = case() or rc
    rc = _assert_no_torch_npu_in_sys_modules() or rc
    print()
    print("=" * 72)
    if rc == 0:
        print("SMOKE TEST RESULT: ALL 6 CASES PASSED (Story 1.5 AC-9 surrogate evidence)")
    else:
        print(f"SMOKE TEST RESULT: FAILED (rc={rc})")
    print("=" * 72)
    return rc


if __name__ == "__main__":
    sys.exit(main())
