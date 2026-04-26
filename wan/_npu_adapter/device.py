# -*- coding: utf-8 -*-
"""设备工厂（Story 1.2 — FR-01 / FR-03 / FR-18 核心载体）。

本模块是 NPU 适配层中**唯一**承载设备初始化逻辑的文件。它的存在让
`generate_infinitetalk.py` / `wan/multitalk.py` 这两个主路径文件保持
"对 `--device` 字符串无感知" — pipeline 类只看到 `torch.device` 对象，
CLI 入口只看到 `set_device(...) / resolve_torch_device(...)` 这层接口。

设计约束（来自 architecture-summary.md § 1 设备抽象层）
-------------------------------------------------------
1. **Lazy import**：`torch_npu` **绝不**在模块顶层 `import`；只能在
   `--device npu` 路径触发的函数体内 import。这样 `--device cuda` runtime
   上 `torch_npu` 不会进入 `sys.modules`（AC-8 物理保证）。
2. **Fail-loudly**：`torch_npu` 不可达时给出含算子定位线索的清晰错误
   （AC-5）；多卡 NPU 在启动期 raise `NotImplementedError`（AC-6），
   不允许沉默 fallback 到 NCCL。
3. **位置约束**：本文件（及 `wan/_npu_adapter/` 整个目录）**不**计入
   NFR-02 的 5 个主路径白名单 — 是为了把适配代码搬出主路径行预算的
   物理载体（NFR-03 "可一组 git revert 撤回" 的核心）。
"""

from __future__ import annotations

import torch


_VALID_DEVICES = ("cuda", "npu")


def is_npu(device: str) -> bool:
    """纯字符串判断当前设备是否为 NPU。

    **不**触发任何 import；用于 hot path 上避免 `torch_npu` 误激活。
    """
    return device == "npu"


def _import_torch_npu() -> None:
    """Lazy import `torch_npu`，并在不可达时按 AC-5 给出友好错误。

    成功时副作用：`torch.npu` 子模块被 monkey-patch 注入；之后调用方
    可以像使用 `torch.cuda.set_device(...)` 一样使用 `torch.npu.set_device(...)`。
    """
    try:
        import torch_npu  # noqa: F401  (import触发 monkey-patch)
        # 再次 import torch 以确保 `torch.npu` 属性已注入（顺序敏感）。
        import torch  # noqa: F401
    except ImportError as exc:  # pragma: no cover - 取决于 host 环境
        raise RuntimeError(
            "torch_npu not importable; install requirements-npu.txt "
            "and ensure CANN driver loaded"
        ) from exc


def set_device(device: str, local_rank: int) -> None:
    """根据 `--device` flag 分发到 cuda 或 npu 的 set_device 调用。

    - ``cuda``：`torch.cuda.set_device(local_rank)`
    - ``npu`` ：lazy import `torch_npu` 后 `torch.npu.set_device(local_rank)`
    - 其他   ：`ValueError`（argparse 已 choices 限制，多一道防线无害）

    AC-1 / AC-2 由本函数承载。
    """
    if device == "cuda":
        torch.cuda.set_device(local_rank)
        return
    if device == "npu":
        _import_torch_npu()
        torch.npu.set_device(local_rank)  # type: ignore[attr-defined]
        return
    raise ValueError(
        f"Unsupported device '{device}'; expected one of {_VALID_DEVICES}"
    )


def resolve_torch_device(device: str, device_id: int) -> "torch.device":
    """返回 `torch.device` 实例，pipeline 类后续不再接触字符串字面量。

    - ``cuda`` → `torch.device(f"cuda:{device_id}")`
    - ``npu`` → lazy import `torch_npu` 后 `torch.device(f"npu:{device_id}")`

    AC-2 / AC-4 由本函数承载（消除 `wan/multitalk.py:157` 的硬编码
    `f"cuda:{device_id}"`）。
    """
    if device == "cuda":
        return torch.device(f"cuda:{device_id}")
    if device == "npu":
        _import_torch_npu()
        return torch.device(f"npu:{device_id}")
    raise ValueError(
        f"Unsupported device '{device}'; expected one of {_VALID_DEVICES}"
    )


def assert_single_card_or_fail(device: str, world_size: int) -> None:
    """NPU 多卡分支启动期 fail-loudly（AC-6）。

    当 ``device == "npu" and world_size > 1`` 时抛 `NotImplementedError`，
    把失败时机从"运行时神秘 NCCL 报错"提前到"启动时显式声明"。
    Phase 2 才设计 HCCL 等价物 — 本 story 范围严格 MVP / 单卡。

    其他组合（`cuda + multi-card` / `* + single-card`）放行；上游 NCCL
    路径不变（NFR-05）。
    """
    if device == "npu" and world_size > 1:
        raise NotImplementedError(
            "Multi-card NPU SP is Phase 2 scope; use world_size==1 for MVP"
        )
