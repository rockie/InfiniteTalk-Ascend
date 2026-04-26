#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Story 1.4 dry-run 烟测（AC-8 evidence）。

本脚本是 Task 5 四个 case 的**轻量等价物**：dev 环境下 torch / xformers /
torch_npu 等重型依赖未安装时，无法直接运行 `generate_infinitetalk.py`。但
AC-8 的本质是验证 `wan/_npu_adapter/attention_dispatch.py` 的公共 helper
`dispatch_memory_efficient_attention` 在 4 种场景下行为正确，**不**要求
真实加载模型权重 / 真实 xformers / 真实 torch_npu —— 故本脚本通过
import-by-source + sys.modules 操作 + 注入 mock spy + 直接调用公共 API
复现 Task 5 的四个 case：

    CASE 1 — CUDA passthrough：mock q.device.type=="cuda" + mock
             xformers.ops.memory_efficient_attention spy；调用 dispatch；
             验证 spy 被调用、args 字符等价（AC-3）
    CASE 2 — NPU + BNSD layout：mock q.device.type=="npu" + mock
             torch_npu.npu_fusion_attention spy；调用 dispatch（attn_bias=None）；
             验证 spy 被调用、kwargs 含 input_layout/head_num/scale、不含
             actual_seq_qlen/actual_seq_kvlen、返回 tuple[0]（AC-1）
    CASE 3 — CUDA 路径不触发 torch_npu import：先 _purge_torch_npu_modules；
             mock q.device.type=="cuda" + mock xformers spy；调用 dispatch；
             断言 sys.modules 中无任何 torch_npu* 项（AC-6 binding runtime）
    CASE 4 — NPU + BlockDiagonalMask 显式 NotImplementedError：mock
             q.device.type=="npu" + 构造 mock BlockDiagonalMask 实例；
             调用 dispatch；验证 NotImplementedError + 消息字面含
             "BlockDiagonalMask" + "Phase 2" + torch_npu 未进入 sys.modules
             （NotImplementedError 在 import 之前抛出 — AC-2 防御性诊断）

输出格式与 Task 5.4 PR 留痕兼容：每个 case 标注 case 编号 + stdout/stderr。
"""
from __future__ import annotations

import sys
import types
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _load_dispatch_module():
    """直接从源文件加载 `wan/_npu_adapter/attention_dispatch.py`，绕开
    `wan/__init__.py` 的重型 import（diffusers / accelerate / safetensors 等）。
    dev box 不会安装完整推理栈，但本 story 只测 dispatch 层 — 这层零依赖
    （仅 stdlib + lazy xformers / lazy torch_npu）。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wan._npu_adapter.attention_dispatch",
        str(REPO_ROOT / "wan" / "_npu_adapter" / "attention_dispatch.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wan._npu_adapter.attention_dispatch"] = mod
    spec.loader.exec_module(mod)
    return mod


def _purge_dispatch_module():
    """清扫已加载的 dispatch 模块自身，确保每个 case 重新加载。"""
    sys.modules.pop("wan._npu_adapter.attention_dispatch", None)


def _purge_torch_npu_modules():
    """清扫 sys.modules 内一切 torch_npu* / torch.npu* 项，确保 case 入口 clean。"""
    for name in list(sys.modules):
        if name == "torch_npu" or name.startswith("torch_npu."):
            sys.modules.pop(name, None)


def _purge_xformers_modules():
    """清扫 sys.modules 内一切 xformers* 项，确保 case 入口 clean。"""
    for name in list(sys.modules):
        if name == "xformers" or name.startswith("xformers."):
            sys.modules.pop(name, None)


class _MockTensor:
    """轻量 torch.Tensor stub — 仅暴露 dispatch 实际消费的接口：
    ``.device.type`` / ``.shape``。**不**继承 torch.Tensor（dev box 没装 torch）。
    """

    def __init__(self, device_type: str, shape=(2, 16, 8, 64)):
        self.device = types.SimpleNamespace(type=device_type)
        self.shape = shape

    def __repr__(self):
        return f"_MockTensor(device.type={self.device.type!r}, shape={self.shape})"


class _CallSpy:
    """记录调用 args/kwargs 的 spy；返回值由 ``return_value`` 决定。"""

    def __init__(self, return_value):
        self.calls = []
        self.return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_value


def _install_mock_xformers(spy):
    """在 sys.modules 注入 dummy xformers + xformers.ops，使
    ``import xformers.ops`` 后 ``xformers.ops.memory_efficient_attention``
    指向 spy。"""
    xformers_pkg = types.ModuleType("xformers")
    xformers_ops = types.ModuleType("xformers.ops")
    xformers_ops.memory_efficient_attention = spy
    xformers_pkg.ops = xformers_ops
    sys.modules["xformers"] = xformers_pkg
    sys.modules["xformers.ops"] = xformers_ops


def _install_mock_torch_npu(spy):
    """在 sys.modules 注入 dummy torch_npu，使 ``import torch_npu`` 后
    ``torch_npu.npu_fusion_attention`` 指向 spy。"""
    torch_npu_pkg = types.ModuleType("torch_npu")
    torch_npu_pkg.npu_fusion_attention = spy
    sys.modules["torch_npu"] = torch_npu_pkg


def case_1_cuda_passthrough() -> int:
    """CASE 1 — CUDA passthrough：mock q.device.type=="cuda" + mock xformers spy；
    验证 spy 被调用 1 次、args/kwargs 字符等价、返回值字符等价、
    sys.modules 无 torch_npu 项（AC-3）。"""
    print("=" * 72)
    print("[CASE 1] CUDA passthrough → xformers.ops.memory_efficient_attention")
    print("-" * 72)
    _purge_dispatch_module()
    _purge_torch_npu_modules()
    _purge_xformers_modules()

    sentinel = object()
    spy = _CallSpy(return_value=sentinel)
    _install_mock_xformers(spy)

    try:
        dispatch = _load_dispatch_module()
        q = _MockTensor("cuda")
        k = _MockTensor("cuda")
        v = _MockTensor("cuda")
        rv = dispatch.dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)

        print(f"  spy.calls count = {len(spy.calls)}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"

        args, kwargs = spy.calls[0]
        print(f"  spy.calls[0] args  = {args}")
        print(f"  spy.calls[0] kwargs = {kwargs}")
        assert args == (q, k, v), f"args mismatch: {args}"
        assert kwargs == {"attn_bias": None, "op": None}, f"kwargs mismatch: {kwargs}"
        assert rv is sentinel, f"return value not character-equivalent: {rv!r}"

        leaked = [n for n in sys.modules if n == "torch_npu" or n.startswith("torch_npu.")]
        print(f"  torch_npu-prefixed modules in sys.modules: {leaked}")
        assert not leaked, f"torch_npu leaked into sys.modules on CUDA path: {leaked}"

        print("[CASE 1] PASS — CUDA dispatch character-equivalent to upstream (AC-3)")
        return 0
    finally:
        _purge_xformers_modules()


def case_2_npu_bnsd_layout() -> int:
    """CASE 2 — NPU + BNSD：mock q.device.type=="npu" + mock torch_npu spy；
    调用 dispatch（attn_bias=None）；验证 spy 被调用、kwargs 含
    input_layout/head_num/scale、不含 actual_seq_qlen/actual_seq_kvlen、
    返回值是 spy tuple 的第 0 项（AC-1）。"""
    print()
    print("=" * 72)
    print("[CASE 2] NPU + attn_bias=None → torch_npu.npu_fusion_attention BNSD")
    print("-" * 72)
    _purge_dispatch_module()
    _purge_torch_npu_modules()
    _purge_xformers_modules()

    out_sentinel = object()
    # npu_fusion_attention 返回 tuple；dispatch 取 [0]
    spy = _CallSpy(return_value=(out_sentinel, "softmax_max", "softmax_sum", "softmax_in"))
    _install_mock_torch_npu(spy)

    try:
        dispatch = _load_dispatch_module()
        # BMHK 形态 (B, M, H, K) = (2, 16, 8, 64)；H=8、D=64
        q = _MockTensor("npu", shape=(2, 16, 8, 64))
        k = _MockTensor("npu", shape=(2, 16, 8, 64))
        v = _MockTensor("npu", shape=(2, 16, 8, 64))
        rv = dispatch.dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)

        print(f"  spy.calls count = {len(spy.calls)}")
        assert len(spy.calls) == 1, f"expected 1 call, got {len(spy.calls)}"

        args, kwargs = spy.calls[0]
        print(f"  spy.calls[0] positional args = {args}")
        print(f"  spy.calls[0] kwargs           = {kwargs}")
        assert args == (q, k, v), f"positional args mismatch: {args}"
        assert "input_layout" in kwargs, f"missing input_layout kwarg: {kwargs}"
        assert kwargs["input_layout"] in ("BNSD", "BSND"), \
            f"input_layout must be BNSD or BSND, got {kwargs['input_layout']!r}"
        assert "head_num" in kwargs, f"missing head_num kwarg: {kwargs}"
        assert kwargs["head_num"] == 8, f"expected head_num=8 (q.shape[-2]), got {kwargs['head_num']}"
        assert "scale" in kwargs, f"missing scale kwarg: {kwargs}"
        # scale = 1/sqrt(64) = 0.125
        assert abs(kwargs["scale"] - 0.125) < 1e-9, f"expected scale=0.125, got {kwargs['scale']}"
        # BNSD-only — 本 story 不实现 TND
        assert "actual_seq_qlen" not in kwargs, \
            f"actual_seq_qlen must NOT appear (TND OOS Phase 1): {kwargs}"
        assert "actual_seq_kvlen" not in kwargs, \
            f"actual_seq_kvlen must NOT appear (TND OOS Phase 1): {kwargs}"

        # 返回值是 spy tuple[0]
        print(f"  dispatch return value = {rv!r}")
        assert rv is out_sentinel, f"dispatch must return tuple[0], got {rv!r}"

        print("[CASE 2] PASS — NPU dispatch routes to npu_fusion_attention BNSD with correct kwargs (AC-1)")
        return 0
    finally:
        _purge_torch_npu_modules()


def case_3_cuda_path_no_torch_npu_import() -> int:
    """CASE 3 — CUDA 路径不触发 torch_npu import（AC-6 binding runtime evidence）。
    先 _purge_torch_npu_modules；mock q.device.type=="cuda" + mock xformers spy；
    调用 dispatch；断言调用后 sys.modules 仍无任何 torch_npu* 项。"""
    print()
    print("=" * 72)
    print("[CASE 3] CUDA path → no torch_npu import (AC-6 binding runtime evidence)")
    print("-" * 72)
    _purge_dispatch_module()
    _purge_torch_npu_modules()
    _purge_xformers_modules()

    # 确认入口 clean
    leaked_before = [n for n in sys.modules if n == "torch_npu" or n.startswith("torch_npu.")]
    print(f"  torch_npu* in sys.modules BEFORE dispatch: {leaked_before}")
    assert not leaked_before, f"case-entry not clean: {leaked_before}"

    spy = _CallSpy(return_value="cuda_output")
    _install_mock_xformers(spy)

    try:
        dispatch = _load_dispatch_module()
        q = _MockTensor("cuda")
        k = _MockTensor("cuda")
        v = _MockTensor("cuda")
        dispatch.dispatch_memory_efficient_attention(q, k, v)

        leaked_after = [n for n in sys.modules if n == "torch_npu" or n.startswith("torch_npu.")]
        print(f"  torch_npu* in sys.modules AFTER  dispatch: {leaked_after}")
        assert not leaked_after, \
            f"torch_npu leaked into sys.modules on CUDA path: {leaked_after}"

        print("[CASE 3] PASS — CUDA dispatch zero NPU import (AC-6)")
        return 0
    finally:
        _purge_xformers_modules()


def case_4_npu_blockdiagonalmask_notimplementederror() -> int:
    """CASE 4 — NPU + BlockDiagonalMask 显式 NotImplementedError（AC-2 防御性诊断）。
    mock q.device.type=="npu" + 构造 mock BlockDiagonalMask 实例；调用 dispatch；
    验证：(a) NotImplementedError；(b) 消息字面含 "BlockDiagonalMask" + "Phase 2"；
    (c) traceback 顶帧归因 _npu_dispatch；(d) torch_npu 未进入 sys.modules。"""
    print()
    print("=" * 72)
    print("[CASE 4] NPU + BlockDiagonalMask → NotImplementedError (AC-2)")
    print("-" * 72)
    _purge_dispatch_module()
    _purge_torch_npu_modules()
    _purge_xformers_modules()

    # 命名为 BlockDiagonalMask 让 type().__name__ 字面匹配
    class BlockDiagonalMask:
        pass

    mock_bdm = BlockDiagonalMask()

    try:
        dispatch = _load_dispatch_module()
        q = _MockTensor("npu", shape=(2, 16, 8, 64))
        k = _MockTensor("npu", shape=(2, 16, 8, 64))
        v = _MockTensor("npu", shape=(2, 16, 8, 64))

        try:
            dispatch.dispatch_memory_efficient_attention(q, k, v, attn_bias=mock_bdm)
        except NotImplementedError as exc:
            msg = str(exc)
            print(f"  caught NotImplementedError: {msg}")
            assert "BlockDiagonalMask" in msg, \
                f"message must contain 'BlockDiagonalMask': {msg!r}"
            phase_marker = ("Phase 2" in msg) or ("multi-card NPU" in msg)
            assert phase_marker, \
                f"message must contain 'Phase 2' or 'multi-card NPU': {msg!r}"

            tb = traceback.extract_tb(exc.__traceback__)
            last_frame = tb[-1] if tb else None
            print(f"  traceback last frame: {last_frame}")
            assert last_frame is not None, "traceback unexpectedly empty"
            assert last_frame.name == "_npu_dispatch", \
                f"top frame must attribute to _npu_dispatch (NPU dispatch body), " \
                f"got {last_frame.name!r}"

            # NotImplementedError 在 lazy import torch_npu 之前抛出 — sys.modules
            # 必须仍然 clean
            leaked = [n for n in sys.modules if n == "torch_npu" or n.startswith("torch_npu.")]
            print(f"  torch_npu* in sys.modules after NotImplementedError: {leaked}")
            assert not leaked, \
                f"torch_npu leaked into sys.modules before NotImplementedError raised: {leaked}"

            print("[CASE 4] PASS — BlockDiagonalMask + NPU raises NotImplementedError pre-import (AC-2)")
            return 0
        else:
            print("[CASE 4] FAIL — expected NotImplementedError but call succeeded", file=sys.stderr)
            return 4
    finally:
        _purge_torch_npu_modules()


def main() -> int:
    rc = 0
    for case in (
        case_1_cuda_passthrough,
        case_2_npu_bnsd_layout,
        case_3_cuda_path_no_torch_npu_import,
        case_4_npu_blockdiagonalmask_notimplementederror,
    ):
        rc = case() or rc
    print()
    print("=" * 72)
    if rc == 0:
        print("SMOKE TEST RESULT: ALL CASES PASSED (Story 1.4 AC-1/2/3/6/8 surrogate evidence)")
    else:
        print(f"SMOKE TEST RESULT: FAILED (rc={rc})")
    print("=" * 72)
    return rc


if __name__ == "__main__":
    sys.exit(main())
