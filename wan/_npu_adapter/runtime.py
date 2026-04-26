# -*- coding: utf-8 -*-
"""Story 1.5 hot-loop runtime helpers (empty_cache / ipc_collect / manual_seed_all / synchronize); device-aware dispatch wrapper for `wan/multitalk.py`.

设计约束（来自 Story 1.5 Dev Notes + architecture-summary.md § 1 设备抽象层）
-----------------------------------------------------------------------------
1. **Lazy import**：`torch_npu` **绝不**在模块顶层 `import`；本模块假设
   `wan/_npu_adapter/device.py:_import_torch_npu` 已在 `set_device(...)` 阶段
   触发过 monkey-patch 注入 `torch.npu` 子模块。helper 内部直接读 `torch.npu`
   即可（Story 1.2 已落地 `set_device → _import_torch_npu` 链路, 顺序由
   `generate_infinitetalk.py:474` 的 control-flow 强制保证）。
2. **`device.type == "npu"` 判断仅在本模块内出现**：`wan/multitalk.py` 不出现
   任何 device-aware 字面量分支（架构 § 1 设备扩散原则；Story 1.2 AC-4 契约
   延续；Story 1.5 AC-4 grep verifier 强制）。
3. **CUDA 路径字符等价**：cuda 分支保留 4 个 `torch_cuda` 字面量调用
   （NFR-05 上游行为不变；AC-6 grep verifier 强制 4 行命中）。
4. **不计入 NFR-02 主路径白名单**：本文件随 `wan/_npu_adapter/` 整个目录
   归 NFR-03 物理载体。
"""

from __future__ import annotations

import logging

import torch


logger = logging.getLogger(__name__)


def device_empty_cache(device_obj: "torch.device") -> None:
    """Device-aware `torch.{cuda,npu}.empty_cache()` 分发。"""
    if device_obj.type == "cuda":
        torch.cuda.empty_cache()
        return
    if device_obj.type == "npu":
        torch.npu.empty_cache()  # type: ignore[attr-defined]
        return
    raise ValueError(f"Unsupported device.type='{device_obj.type}'")


def device_ipc_collect(device_obj: "torch.device") -> None:
    """Device-aware `torch.{cuda,npu}.ipc_collect()` 分发。

    注：CANN 5.x torch_npu 已支持 `torch.npu.ipc_collect`；如该 attr 不存在
    （旧 CANN / 不同 torch_npu 版本），silent skip + 一行 debug log，**不**降级
    到 cuda 调用（会崩），**不**抛 RuntimeError（fallback ops 数量列入
    NFR-09 escalation territory 而非本 story DoD）。
    """
    if device_obj.type == "cuda":
        torch.cuda.ipc_collect()
        return
    if device_obj.type == "npu":
        if hasattr(torch.npu, "ipc_collect"):  # type: ignore[attr-defined]
            torch.npu.ipc_collect()  # type: ignore[attr-defined]
        else:
            logger.debug("torch.npu.ipc_collect not available; skipping")
        return
    raise ValueError(f"Unsupported device.type='{device_obj.type}'")


def device_manual_seed_all(device_obj: "torch.device", seed: int) -> None:
    """Device-aware `torch.{cuda,npu}.manual_seed_all(seed)` 分发。"""
    if device_obj.type == "cuda":
        torch.cuda.manual_seed_all(seed)
        return
    if device_obj.type == "npu":
        torch.npu.manual_seed_all(seed)  # type: ignore[attr-defined]
        return
    raise ValueError(f"Unsupported device.type='{device_obj.type}'")


def device_synchronize(device_obj: "torch.device") -> None:
    """Device-aware `torch.{cuda,npu}.synchronize()` 分发。"""
    if device_obj.type == "cuda":
        torch.cuda.synchronize()
        return
    if device_obj.type == "npu":
        torch.npu.synchronize()  # type: ignore[attr-defined]
        return
    raise ValueError(f"Unsupported device.type='{device_obj.type}'")
