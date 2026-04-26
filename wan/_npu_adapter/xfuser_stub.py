# -*- coding: utf-8 -*-
"""xfuser 单卡桩化（Story 1.3 — FR-07 / architecture-summary.md § 2 核心载体）。

本模块承载"`world_size==1` 时短路所有 xfuser 调用"这条 invariant 的物理实现。
与 `wan/_npu_adapter/device.py` 同目录 = NFR-03 "可一组 git revert 撤回" 的
载体；不在 NFR-02 5 个主路径白名单 = 行预算豁免。

设计约束
--------
1. **Lazy import 边界**：`world_size > 1` 才触发真 xfuser import；
   `world_size == 1` dry-run 后 `not any(name.startswith('xfuser')
   for name in sys.modules)` 必须为 ``True``（AC-1 物理判定线）。
2. **device 解耦**：stub 仅依赖 ``world_size``，不读取 `--device` 字符串
   也不 import `torch_npu`/`torch.npu`（架构原则：xfuser 是 SP 框架，
   不是 device-aware 算子；short-circuit 只看 `world_size==1`）。
3. **公共 API = 2 个函数**：`should_short_circuit_xfuser` /
   `get_sequence_parallel_world_size_safe`；不暴露其他实体（避免
   adapter 层接口蔓延）。

公共 API
--------
- `should_short_circuit_xfuser(world_size)` — 纯判定，无副作用，无 import
- `get_sequence_parallel_world_size_safe(world_size)` — 单卡返回 1（不 import
  xfuser）；多卡 lazy import 真 xfuser 并 delegate（NFR-05 上游路径不变）
"""

from __future__ import annotations


def should_short_circuit_xfuser(world_size: int) -> bool:
    """单卡 = 短路 xfuser 调用图（AC-1 / AC-3 hot-path 决策点）。

    纯函数；无副作用；**不**触发任何 xfuser import。调用方在 `if use_usp
    and not should_short_circuit_xfuser(_world_size):` guard 中消费此返回
    值，让 `world_size==1` 单卡路径绕开 USP patch 三连。
    """
    return world_size == 1


def get_sequence_parallel_world_size_safe(world_size: int) -> int:
    """`get_sequence_parallel_world_size()` 的 single-card 安全包装。

    - ``world_size == 1``：直接返回 ``1``，**不**触发
      `from xfuser.core.distributed import get_sequence_parallel_world_size`
      （AC-1 物理保证）。
    - ``world_size > 1``：lazy import 真 xfuser 并 delegate；行为与上游
      `get_sequence_parallel_world_size()` 字符等价（NFR-05 上游路径不变）。

    `_safe` 后缀提示调用方："单卡路径 import 隔离已在本函数内闭合，
    上层无需自己防御 `xfuser` 缺席"。
    """
    if should_short_circuit_xfuser(world_size):
        return 1
    # world_size > 1 透明放行 = NFR-05 上游路径不变
    from xfuser.core.distributed import get_sequence_parallel_world_size
    return get_sequence_parallel_world_size()
