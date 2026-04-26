# -*- coding: utf-8 -*-
"""Attention dispatch（Story 1.4 — FR-05 / FR-06 / architecture-summary.md § 3 核心载体）。

本模块承载"`xformers.ops.memory_efficient_attention` ↔ `torch_npu.npu_fusion_attention`
device-aware 路由"这条 invariant 的物理实现。与 `wan/_npu_adapter/device.py`
（Story 1.2）/ `wan/_npu_adapter/xfuser_stub.py`（Story 1.3）同目录 = NFR-03
"可一组 git revert 撤回"的载体；不在 NFR-02 5 个主路径白名单 = 行预算豁免。

设计约束（来自 architecture-summary.md § 3 attention 算子替换）
---------------------------------------------------------------
1. **Lazy import 边界**：`torch_npu` **绝不**在模块顶层 `import`；只能在
   `q.device.type == "npu"` 触发的 `_npu_dispatch` 函数体内 import。这样
   `--device cuda` runtime 上 `torch_npu` 不会进入 `sys.modules`（AC-6 物理
   保证 — smoke CASE 3 binding runtime evidence）。`xformers.ops` 同样在
   CUDA 分支函数体内 local import — NPU host 上 dispatch 进 NPU 分支前完全
   不 import xformers（防御性；NPU host 上 xformers 可能装也可能没装）。
2. **BNSD-only**：单卡 MVP 仅支持 `attn_bias=None` 固定长度形态；
   `BlockDiagonalMask + NPU` 组合（多卡 SP 路径）显式抛
   `NotImplementedError` — 多卡 SP NPU 属 Phase 2 territory（与 Story 1.3
   单卡 MVP scope 对齐）。**显式不实现** TND layout / `actual_seq_qlen` /
   `actual_seq_kvlen` / `_extract_seqlens` / `_to_cumulative_int32` —
   留给 Phase 2 多卡 SP NPU story。
3. **公共 API = 1 个函数**：`dispatch_memory_efficient_attention`；
   `_npu_dispatch` 用 `_` 前缀私有化（避免 adapter 层接口蔓延 — 与
   Story 1.2 / 1.3 公共 API 数控制约束一致）。
4. **位置约束**：本文件（及 `wan/_npu_adapter/` 整个目录）**不**计入
   NFR-02 的 5 个主路径白名单 — 是为了把适配代码搬出主路径行预算的
   物理载体（NFR-03 "可一组 git revert 撤回"的核心）。

公共 API
--------
- `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`
  — device-aware 路由：CUDA 透明放行至 `xformers.ops.memory_efficient_attention`
  （NFR-05 字符等价）；NPU + `attn_bias is None` 落到 `torch_npu.npu_fusion_attention`
  BNSD；NPU + `BlockDiagonalMask` 抛 `NotImplementedError`。
"""

from __future__ import annotations


def dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None):
    """Device-aware attention dispatch（Phase 1 单卡 MVP — FR-05 / FR-06）。

    - ``q.device.type == "cuda"`` → 透明放行至
      `xformers.ops.memory_efficient_attention(q, k, v, attn_bias=attn_bias, op=op)`
      （字符等价 — NFR-05 hard）。
    - ``q.device.type == "npu"`` + ``attn_bias is None`` → BNSD 路由到
      `torch_npu.npu_fusion_attention`（lazy import；单卡 MVP 唯一 in-scope
      NPU 形态）。
    - ``q.device.type == "npu"`` + ``attn_bias is not None``（典型 = 多卡 SP
      路径的 `BlockDiagonalMask`）→ `NotImplementedError`（多卡 SP NPU 属
      Phase 2 OOS；与 Story 1.3 单卡 MVP scope 对齐）。
    - 其他 → `ValueError`（防御性；`--device` 已 argparse choices 限制）。
    """
    if q.device.type == "cuda":
        # local import：NPU host 上 dispatch 进 NPU 分支前完全不 import xformers
        import xformers.ops
        return xformers.ops.memory_efficient_attention(
            q, k, v, attn_bias=attn_bias, op=op,
        )
    if q.device.type == "npu":
        return _npu_dispatch(q, k, v, attn_bias=attn_bias)
    raise ValueError(
        f"Unsupported device type '{q.device.type}'; expected 'cuda' or 'npu'"
    )


def _npu_dispatch(q, k, v, attn_bias):
    """NPU 分支主体（BNSD-only；BlockDiagonalMask + NPU 显式 NotImplementedError）。

    - ``attn_bias is not None``（典型 = 多卡 SP 路径的 `BlockDiagonalMask`
      由 `wan/modules/attention.py:263` 在 `enable_sp=True` 时构造）→ 抛
      `NotImplementedError`，错误消息字面含 "BlockDiagonalMask" + "Phase 2"，
      让单卡 MVP NPU 路径在意外触发 SP 时获得清晰错误（防御性诊断 — 单卡
      MVP 路径默认 `enable_sp=False` → `attn_bias=None` → 走 BNSD 分支，
      不触发本路径）。
    - ``attn_bias is None`` → lazy import `torch_npu` + 调
      `npu_fusion_attention(q, k, v, head_num=H, input_layout="BSND",
      scale=1/sqrt(D))`，取返回 tuple 的 ``[0]`` 作为 attention output。

    输入形态：q / k / v 经 `wan/modules/attention.py:253-255` rearrange 后是
    BMHK ``(B, M, H, K)`` 即 ``(Batch, Seq, Num_heads, Dim)``，对应 CANN
    `npu_fusion_attention` 的 ``input_layout="BSND"`` 标识符（B=batch、
    S=seq、N=num_heads、D=dim）。``head_num=q.shape[-2]``（H 维），
    ``scale=1/sqrt(q.shape[-1])``（xformers 默认 1/sqrt(head_dim)）。

    NPU 数值正确性**不**在本 story 验证范围 — 本 story 仅保证 dispatch
    逻辑可达 + 入口参数形态正确。Story 1.5 在真实 910B host 上跑通 multitalk
    happy path 时 implicit 验证（出视频 ffprobe 通过即可接受 — NFR-07 不
    要求 bit-exact CUDA↔NPU 输出等价）。
    """
    if attn_bias is not None:
        # 通过 type().__name__ 字面判定，**不** import
        # `xformers.ops.fmha.attn_bias.BlockDiagonalMask`（NPU host 可能不装
        # xformers）；调用方实际形态由 `wan/modules/attention.py:263`
        # `BlockDiagonalMask.from_seqlens(...)` 构造，仅在 `enable_sp=True`
        # 多卡 SP 路径触达。
        cls_name = type(attn_bias).__name__
        raise NotImplementedError(
            f"BlockDiagonalMask attention on NPU is multi-card NPU OOS Phase 1 "
            f"(got attn_bias of type {cls_name!r}); "
            f"single-card NPU path uses attn_bias=None (BNSD). "
            f"Multi-card SP NPU support is Phase 2."
        )

    try:
        import torch_npu  # noqa: F401  (lazy；CUDA 路径不进入 sys.modules)
    except ImportError as exc:  # pragma: no cover - 取决于 host 环境
        raise RuntimeError(
            "torch_npu not importable; install requirements-npu.txt "
            "and ensure CANN driver loaded"
        ) from exc

    # BMHK 形态 (B, M, H, K) — 见 wan/modules/attention.py:253-255 rearrange
    # "B H M K -> B M H K"；对应 CANN input_layout="BSND"。
    head_num = q.shape[-2]
    scale = 1.0 / (q.shape[-1] ** 0.5)

    return torch_npu.npu_fusion_attention(
        q, k, v,
        head_num=head_num,
        input_layout="BSND",
        scale=scale,
    )[0]
