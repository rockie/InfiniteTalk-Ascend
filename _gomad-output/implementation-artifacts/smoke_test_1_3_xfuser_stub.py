#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Story 1.3 dry-run 烟测（AC-8 evidence）。

本脚本是 Task 5 五个 case 的**轻量等价物**：dev 环境下 torch / xfuser 等
重型依赖未安装时，无法直接运行 `generate_infinitetalk.py`。但 AC-8
的本质是验证 `wan/_npu_adapter/xfuser_stub.py` 的 2 个公共 helper 在
5 种场景下行为正确，**不**要求真实加载模型权重 / 真实 xfuser 安装 —
故本脚本通过 import-by-source + sys.modules 操作 + 直接调用公共 API
复现 Task 5 的五个 case：

    Case 1 — should_short_circuit_xfuser(1) == True
    Case 2 — should_short_circuit_xfuser(2) == False
    Case 3 — get_sequence_parallel_world_size_safe(1) == 1
             AND xfuser 不在 sys.modules（AC-1 物理判定线）
    Case 4a — xfuser-absent: get_sequence_parallel_world_size_safe(2)
              抛 ImportError，traceback 顶帧定位到 xfuser
    Case 4b — xfuser-present-dist-not-initialized:
              dummy `xfuser.core.distributed` 提供 get_sequence_parallel_world_size
              返回 2；safe(2) 透明放行返回 2

输出格式与 Task 5.4 PR 留痕兼容：每个 case 标注 case 编号 + stdout/stderr。
"""
from __future__ import annotations

import sys
import types
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _load_xfuser_stub_module():
    """直接从源文件加载 `wan/_npu_adapter/xfuser_stub.py`，绕开 `wan/__init__.py`
    的重型 import（diffusers / accelerate / safetensors 等）。dev box 不会安装
    完整推理栈，但本 story 只测 stub 层 — 这层零依赖（仅 stdlib + lazy xfuser）。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "wan._npu_adapter.xfuser_stub",
        str(REPO_ROOT / "wan" / "_npu_adapter" / "xfuser_stub.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wan._npu_adapter.xfuser_stub"] = mod
    spec.loader.exec_module(mod)
    return mod


def _purge_xfuser_modules():
    """清扫 sys.modules 内一切以 'xfuser' 起头的项，确保 case 入口 clean。"""
    for name in list(sys.modules):
        if name == "xfuser" or name.startswith("xfuser."):
            sys.modules.pop(name, None)


def _purge_stub_module():
    """清扫已加载的 stub 模块自身，确保每个 case 重新加载。"""
    for name in list(sys.modules):
        if name == "wan._npu_adapter.xfuser_stub":
            sys.modules.pop(name, None)


def case_1_should_short_circuit_true() -> int:
    """CASE 1 — should_short_circuit_xfuser(1) == True。"""
    print("=" * 72)
    print("[CASE 1] should_short_circuit_xfuser(1) == True")
    print("-" * 72)
    _purge_xfuser_modules()
    _purge_stub_module()

    stub = _load_xfuser_stub_module()
    rv = stub.should_short_circuit_xfuser(1)
    print(f"  should_short_circuit_xfuser(1) = {rv!r}")
    assert rv is True, f"expected True, got {rv!r}"
    print("[CASE 1] PASS — single-card path triggers short-circuit (AC-3)")
    return 0


def case_2_should_short_circuit_false() -> int:
    """CASE 2 — should_short_circuit_xfuser(2) == False。"""
    print()
    print("=" * 72)
    print("[CASE 2] should_short_circuit_xfuser(2) == False")
    print("-" * 72)
    _purge_xfuser_modules()
    _purge_stub_module()

    stub = _load_xfuser_stub_module()
    rv = stub.should_short_circuit_xfuser(2)
    print(f"  should_short_circuit_xfuser(2) = {rv!r}")
    assert rv is False, f"expected False, got {rv!r}"
    print("[CASE 2] PASS — multi-card path passes through to upstream (AC-4)")
    return 0


def case_3_safe_single_card_no_xfuser_import() -> int:
    """CASE 3 — get_sequence_parallel_world_size_safe(1) == 1
    AND xfuser 不在 sys.modules（AC-1 sys.modules 物理判定线）。
    """
    print()
    print("=" * 72)
    print("[CASE 3] get_sequence_parallel_world_size_safe(1) == 1")
    print("         AND not any(name.startswith('xfuser') for name in sys.modules)")
    print("-" * 72)
    _purge_xfuser_modules()
    _purge_stub_module()

    stub = _load_xfuser_stub_module()
    rv = stub.get_sequence_parallel_world_size_safe(1)
    print(f"  get_sequence_parallel_world_size_safe(1) = {rv!r}")
    assert rv == 1, f"expected 1, got {rv!r}"

    leaked = [name for name in sys.modules if name.startswith("xfuser")]
    print(f"  xfuser-prefixed modules in sys.modules: {leaked}")
    assert not leaked, f"xfuser leaked into sys.modules on single-card path: {leaked}"
    print("[CASE 3] PASS — single-card returns 1 with zero xfuser import (AC-1)")
    return 0


def case_4a_xfuser_absent_raises_importerror() -> int:
    """CASE 4a — xfuser-absent: safe(2) 抛 ImportError，traceback 顶帧定位 xfuser。

    在 case 入口 `sys.modules['xfuser'] = None` 是 Python 标准的"显式标记
    模块不可达"手段：后续 `import xfuser.core.distributed` 会直接抛
    `ModuleNotFoundError`（ImportError 子类），traceback 顶帧 co_filename
    指向 importlib 内部 / 抛出语句 — 我们检查 ImportError chain 中含 'xfuser'
    字面（不指向本 stub 自身的逻辑错误）。
    """
    print()
    print("=" * 72)
    print("[CASE 4a] xfuser-absent → get_sequence_parallel_world_size_safe(2) raises ImportError")
    print("-" * 72)
    _purge_xfuser_modules()
    _purge_stub_module()

    # 显式标记 xfuser 不可达（dev box 默认状态 + 防御性）
    sys.modules["xfuser"] = None  # type: ignore[assignment]

    stub = _load_xfuser_stub_module()
    try:
        stub.get_sequence_parallel_world_size_safe(2)
    except ImportError as exc:
        msg = str(exc)
        print(f"  caught ImportError: {msg}")
        # 验证 ImportError 关联到 xfuser（不是本 stub 自身的逻辑错误）
        # ModuleNotFoundError 的消息形如 "import of xfuser halted; None in sys.modules"
        # 或 "No module named 'xfuser...'" — 两种形态都含 'xfuser' 字面
        tb = traceback.extract_tb(exc.__traceback__)
        last_frame = tb[-1] if tb else None
        print(f"  traceback last frame: {last_frame}")
        assert "xfuser" in msg.lower() or any("xfuser" in (f.filename or "") for f in tb), \
            "ImportError not attributable to xfuser — possibly stub-internal logic error"
        print("[CASE 4a] PASS — xfuser-absent attributable to xfuser, not stub logic (AC-8)")
        return 0
    finally:
        sys.modules.pop("xfuser", None)
    print("[CASE 4a] FAIL — expected ImportError but call succeeded", file=sys.stderr)
    return 4


def case_4b_xfuser_present_passthrough() -> int:
    """CASE 4b — xfuser-present-dist-not-initialized: dummy xfuser.core.distributed
    提供 `get_sequence_parallel_world_size` 返回 2；safe(2) 透明放行返回 2。
    """
    print()
    print("=" * 72)
    print("[CASE 4b] xfuser-present-dist-not-initialized → safe(2) passthrough returns 2")
    print("-" * 72)
    _purge_xfuser_modules()
    _purge_stub_module()

    # 注入 dummy xfuser 包路径，提供 get_sequence_parallel_world_size 桩
    xfuser_pkg = types.ModuleType("xfuser")
    xfuser_core = types.ModuleType("xfuser.core")
    xfuser_dist = types.ModuleType("xfuser.core.distributed")
    xfuser_dist.get_sequence_parallel_world_size = lambda: 2
    sys.modules["xfuser"] = xfuser_pkg
    sys.modules["xfuser.core"] = xfuser_core
    sys.modules["xfuser.core.distributed"] = xfuser_dist

    try:
        stub = _load_xfuser_stub_module()
        rv = stub.get_sequence_parallel_world_size_safe(2)
        print(f"  get_sequence_parallel_world_size_safe(2) = {rv!r}  (dummy xfuser returned 2)")
        assert rv == 2, f"expected 2, got {rv!r}"
        print("[CASE 4b] PASS — multi-card path delegates to xfuser unchanged (AC-4 / NFR-05)")
        return 0
    finally:
        for name in ("xfuser.core.distributed", "xfuser.core", "xfuser"):
            sys.modules.pop(name, None)


def main() -> int:
    rc = 0
    for case in (
        case_1_should_short_circuit_true,
        case_2_should_short_circuit_false,
        case_3_safe_single_card_no_xfuser_import,
        case_4a_xfuser_absent_raises_importerror,
        case_4b_xfuser_present_passthrough,
    ):
        rc = case() or rc
    print()
    print("=" * 72)
    if rc == 0:
        print("SMOKE TEST RESULT: ALL CASES PASSED (Story 1.3 AC-1/3/4/8 surrogate evidence)")
    else:
        print(f"SMOKE TEST RESULT: FAILED (rc={rc})")
    print("=" * 72)
    return rc


if __name__ == "__main__":
    sys.exit(main())
