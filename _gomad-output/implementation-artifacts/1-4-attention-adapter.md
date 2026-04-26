# Story 1.4: Attention adapter（device-aware xformers / npu_fusion_attention dispatch）

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Migration Engineer,
I want a device-aware attention adapter dispatching to either `xformers.ops.memory_efficient_attention`（CUDA 路径）或 `torch_npu.npu_fusion_attention`（NPU 路径，仅 BNSD 固定长度形态；BlockDiagonalMask + NPU 显式抛 NotImplementedError 标识多卡 SP NPU OOS Phase 2）,
so that **multitalk 主路径**（即消费 `SingleStreamAttention` / `SingleStreamMutiAttention` 的 `wan/modules/multitalk_model.WanModel`）能在 CUDA 与单卡 NPU 上跑而**无 class-specific bypass**（FR-05 / FR-06 / architecture-summary.md § 3 attention 算子替换）。**FR-06 两套 `WanModel` 共享 adapter 的 claim 在本 story 收缩为 multitalk 路径单一可验证项** —— `wan/modules/model.WanModel` 实测 grep 不消费 `xformers.ops.memory_efficient_attention`（仅 `from .attention import flash_attention`），因此 trivially 继承 FR-06（无 class-specific xformers bypass to remove）；其 NPU 适配属 Story 1.5 / Epic 4 territory。

> **Scope 边界澄清（避免越界 — 复刻 Story 1.3 措辞）**：
> - 本 story **只**处理 `wan/modules/attention.py` 中两处 `xformers.ops.memory_efficient_attention` 调用点（grep 锚定 line 266 / 380；具体行号以实施时 `grep -n "memory_efficient_attention" wan/modules/attention.py` 输出为准）+ 在 `wan/_npu_adapter/attention_dispatch.py` 提供 device-aware dispatch helper。
> - **不**触碰 `wan/distributed/xdit_context_parallel.py` —— 该文件 NFR-02 budget 为 **0/80**（Story 1.3 已锚定 zero-touch hard constraint）；其内部的 `memory_efficient_attention` 调用点（grep 锚定 line 540）由 Story 1.3 的 short-circuit 物理保证：单卡路径不 import `xdit_context_parallel.py` → line 540 不被执行。**多卡 CUDA 路径**（理论存在）继续走上游 xformers，与 NFR-05 字符等价。Phase 2 多卡 NPU 时再统一 dispatch。
> - **不**触碰 `flash_attention()` 函数（grep 锚定 `wan/modules/attention.py:33`）也**不**触碰 `attention()` 函数（grep 锚定 line 142）—— 它们走 `flash_attn_interface` / `flash_attn` / `torch.nn.functional.scaled_dot_product_attention` 链路，**与 FR-05 替换目标 `xformers` 正交**；本 story 范围严格限于"`xformers.ops.memory_efficient_attention` → `torch_npu.npu_fusion_attention` 替换"，flash_attention 链路在 NPU 上的行为留给 Story 1.5（multitalk happy path 跑通时如有问题再处理 — `torch.nn.functional.scaled_dot_product_attention` fallback 路径在 NPU 上 PyTorch 框架原生支持）。
> - **不**触碰 `wan/modules/multitalk_model.py` / `wan/modules/model.py` —— 它们仅消费 `flash_attention`（不在本 story scope）。**FR-06 "两套 `WanModel` 共享 adapter" 在本 story 收缩为 multitalk 路径单一可验证项**：`wan/modules/multitalk_model.WanModel`（multitalk 主路径）确实通过 `SingleStreamAttention` / `SingleStreamMutiAttention`（定义在 `wan/modules/attention.py`）进入 `memory_efficient_attention` 调用点 — 本 story 对这两个调用点的 dispatch 改造让 multitalk 路径自动获得 device-aware dispatch；而 `wan/modules/model.WanModel`（i2v/t2v/flf2v 主路径）经实测 grep 验证（`grep -nE "memory_efficient_attention|xformers|SingleStream" wan/modules/model.py` 返回 **0 行**；只有 `from .attention import flash_attention`）—— **不**消费 `xformers.ops.memory_efficient_attention`，因此既无 class-specific xformers bypass 需要拆除，也不在本 story FR-06 验证表面。`model.WanModel` 的 `flash_attention` 链路 NPU 适配属 Story 1.5（happy path）/ Epic 4（i2v/t2v/flf2v 模式落地）territory，不在本 story 验证范围。
> - **不**触碰 `generate_infinitetalk.py` / `app.py` —— Story 1.2 已落 `--device` flag + `set_device` / `resolve_torch_device`；本 story 通过 **lazy device 探测**（在 attention 入口检测 `q.device.type`）消费已设置好的 device 状态，不扩 CLI 表面。
> - **不**实现 NPU `npu_fusion_attention` 真实跑通 —— 那是 Story 1.5 的事（real NPU host）。本 story 仅保证：(a) CUDA 路径**字符等价**于上游（NFR-05 hard），dispatch wrapper 在 CUDA 上是直通；(b) NPU 路径**逻辑可达**（dispatch 分支在 `q.device.type == "npu"` 时落到 `npu_fusion_attention` 调用，layout / shape 转换正确），但**真实 NPU 数值正确性验证**移交 Story 1.5（无 NPU 硬件无法验证）。本 story smoke 在 dev box / CUDA host 上验证 dispatch 逻辑（mock 方式），**不**假装能验证 NPU 数值等价。
> - **不**为 `flash_attention` / `flash_attn` / `sageattention` 链路做 dispatch —— 这些是 CUDA-only kernel，NPU 路径上需要走 `torch.nn.functional.scaled_dot_product_attention`（PyTorch 原生支持 NPU backend）的回退；这条回退已经存在于 `wan/modules/attention.py:174-187` 的 `attention()` else 分支（FA 不可用时的 fallback）。本 story scope 严格限定于"`xformers.ops.memory_efficient_attention` 两处替换"，flash_attention NPU fallback 行为由 Story 1.5 在 happy path 验证时拉手观察 — 如发现 fallback 路径未被命中（因为 `try: import flash_attn` 在 NPU 上仍可能成功），由 Story 1.5 / 后续 story 处理。
> - **不**做"顶层 `import torch_npu` 在 `wan/modules/attention.py`" —— FR-18 / NFR-05 hard 约束：CUDA 路径 runtime 上 `torch_npu` 不应进入 `sys.modules`。所有 `torch_npu` import 必须 lazy 在 `attention_dispatch.py` 的 NPU 分支函数体内（与 Story 1.2 `device.py:_import_torch_npu()` 同形态）。
> - **不**吸收 deferred-work.md 任何 LOW 项 —— 经审视 5 条 LOW（1-1 #1/#2/#3 + 1-2 #1/#2），与本 story 主题（attention dispatch）均不直接相邻；与 Story 1.3 同契约留待后续集中清算。

## Acceptance Criteria

> **来源映射**：本 story AC 锚定 epics.md § Story 1.4 + PRD § FR-05 / FR-06 / FR-18 + architecture-summary.md § 3 attention 算子替换。AC 文本逐字承载 epics.md 四条 Given/When/Then，并补足 NFR-02 行预算 + NFR-05 CUDA 字符等价 + NFR-03 git revert 单组撤回的硬约束。

> **Line-number policy**（grep-binding contract，复刻 Story 1.3 措辞）：本 AC 与 Tasks / Dev Notes 中所有 `wan/modules/attention.py:NNN` 形式的行号引用均为 **2026-04-26 描述性快照**，仅供阅读时定位上下文 —— **grep 字面锚定**才是验证契约的唯一约束力来源（如 `grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py`）。dev agent 实施时以实测 grep 输出为准，上游 cosmetic shifts（空行 / 注释调整）让数字漂移不影响本 story DoD 判定。

1. **AC-1（NPU 路径 dispatch 落到 `npu_fusion_attention`，BNSD-only）**
   **Given** `--device npu`（即 Story 1.2 已落地的 NPU 单卡 MVP 路径）+ Q / K / V tensor `device.type == "npu"` + **`attn_bias is None`**（即固定长度 BNSD 形态）
   **When** 执行抵达 `wan/modules/attention.py` 中 grep 锚定的两处 `memory_efficient_attention` 调用点（即 `SingleStreamAttention.forward()` 在 `enable_sp=False` 单卡路径上 `attn_bias=None` 调用 + `SingleStreamMutiAttention.forward()` 内 `attn_bias=None` 调用）
   **Then** 调用通过 `wan/_npu_adapter/attention_dispatch.py` 的 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None)` helper 路由到 `torch_npu.npu_fusion_attention`，传入 `input_layout="BNSD"` + 适当的 `head_num` / `scale`
   **And** `torch_npu` 仅在 NPU 分支函数体内 lazy import（**不**出现在 `wan/modules/attention.py` 顶层 import 区；**不**出现在 `wan/_npu_adapter/attention_dispatch.py` 顶层 import 区）
   **And** `grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py` 返回 **0 行**（即两处 `xformers.ops.memory_efficient_attention(...)` 调用字面已被 `dispatch_memory_efficient_attention(...)` 完全替换；只有 `BlockDiagonalMask.from_seqlens(...)` 构造调用与顶层 `import xformers.ops` 可保留）

2. **AC-2（变长 `BlockDiagonalMask` 在 NPU 上显式 NotImplementedError —— 多卡 SP 路径 Phase 2 OOS）**
   **Given** 调用点传入 `attn_bias` 是 `xformers.ops.fmha.attn_bias.BlockDiagonalMask` 实例（**仅当** `SingleStreamAttention.forward()` 的 `enable_sp=True` 时由 `wan/modules/attention.py:263` 构造 — 实测 grep 锚定 `if enable_sp:` 在 line 257，`attn_bias = ... BlockDiagonalMask.from_seqlens(...)` 在 line 263，`else: attn_bias = None` 在 line 265）+ `q.device.type == "npu"`
   **When** dispatch 路由到 NPU 分支
   **Then** `dispatch_memory_efficient_attention` 抛出 `NotImplementedError`，错误消息字面包含 "BlockDiagonalMask" 与 "multi-card NPU OOS Phase 1"（or 等效语义片段："sequence parallel" / "Phase 2"）—— 让单卡 MVP NPU 路径在意外触发 SP 时获得清晰错误，而非神秘崩溃
   **And** 单卡 NPU 路径（Story 1.3 short-circuit）实测 `enable_sp=False` → `attn_bias=None`（line 265）→ 进 BNSD 分支（AC-1 验证），**不**触发本 AC-2 NotImplementedError 分支；本 AC-2 仅作为"多卡 NPU 误触发 SP 路径"的防御性诊断
   **And** 适配器**不**在 `wan/modules/attention.py` 内构造任何 NPU 专用 layout；NPU 路径分支判断全部外置到 `wan/_npu_adapter/attention_dispatch.py`（保护 NFR-02 行预算）
   **And** **明确不实现** TND layout / `actual_seq_qlen` / `actual_seq_kvlen` / `_extract_seqlens` / `_to_cumulative_int32` —— 多卡 SP NPU 路径属 Phase 2 单独立项；本 story 仅保证清晰的 NotImplementedError 让 dev / ops 第一时间归因（与 Story 1.3 单卡 MVP scope 对齐）

3. **AC-3（CUDA 路径字符等价 — NFR-05 hard 约束）**
   **Given** `--device cuda` 路径（任何 `world_size`）+ Q / K / V tensor `device.type == "cuda"`
   **When** 同样两处调用点执行
   **Then** dispatch 透明放行至原 `xformers.ops.memory_efficient_attention(q, k, v, attn_bias=..., op=None)` 调用，**输入 args / kwargs / 返回值字符级等价于上游**（NFR-05）
   **And** dispatch helper 在 CUDA 路径上**不**触发任何 `torch_npu` import（`grep -nE "^import torch_npu|^from torch_npu" wan/modules/attention.py wan/_npu_adapter/attention_dispatch.py` 必须返回 0 行）
   **And** dispatch helper 在 CUDA 路径上**不**引入额外 tensor 拷贝 / shape 变换 / 异步同步 —— 仅一层薄包装函数调用

4. **AC-4（FR-06 在本 story 收缩为 multitalk 路径单一可验证项 — 无 class-specific bypass）**
   **Given** `wan/modules/multitalk_model.WanModel`（multitalk 主路径，本 story 唯一 in-scope `WanModel`）
   **When** 该 `WanModel` 类的 forward 进入 `SingleStreamAttention` / `SingleStreamMutiAttention` 的 `memory_efficient_attention` 调用点（grep 锚定：`wan/modules/multitalk_model.py:14: from .attention import flash_attention, SingleStreamMutiAttention`）
   **Then** 进入 `dispatch_memory_efficient_attention(...)` 同一 helper —— **无** class-specific 旁路（即 multitalk `WanModel` **不**自带独立 `xformers` / `torch_npu` 包装；与未来 i2v/t2v/flf2v `WanModel` 适配同入口）
   **And** **物理保证形态**：本 story 修改的是 `wan/modules/attention.py` 中两个 `forward` 方法（属于 `SingleStreamAttention` / `SingleStreamMutiAttention` 类，而非 `WanModel` 类）；任何未来通过这两个共享类进入 attention 的 `WanModel` 实现自动获得同一 dispatch
   **And** **`wan/modules/model.WanModel`（i2v/t2v/flf2v 主路径）显式 OOS**：实测 grep `grep -nE "memory_efficient_attention|xformers|SingleStream" wan/modules/model.py` 返回 **0 行**（2026-04-26 verified）—— 该 `WanModel` 仅 `from .attention import flash_attention`（line 10），**不**消费 `xformers.ops.memory_efficient_attention`；既无 class-specific xformers bypass 需要拆除，也不在本 story FR-06 验证表面。`model.WanModel` 的 `flash_attention` 链路 NPU 适配属 Story 1.5（multitalk happy path 隐式触动 fallback）/ Epic 4（i2v/t2v/flf2v 模式落地）territory，本 story FR-06 trivially 继承（无 bypass to remove）

5. **AC-5（NFR-02 行预算 — 5 个主路径文件改动 ≤ 80 行 / 文件）**
   **Given** 本 story 完成后
   **When** `python3 tools/check_npu_line_budget.py` 运行（CI + pre-commit 已由 Story 1.1 落地，5 路径存在性检查由 Story 1.2 Task 7 落地）
   **Then** EXIT=0（即任意被本 story 改动的主路径文件 added 行 ≤ 80）
   **And** 主路径文件**白名单** = `wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` / `generate_infinitetalk.py` / `app.py`
   **And** 本 story 改动的主路径文件预期 = **仅** `wan/modules/attention.py`（其余 4 个 zero-touch；`wan/distributed/xdit_context_parallel.py` 0/80 budget 严格 zero-touch — 与 Story 1.3 衔接契约一致）
   **And** **`wan/modules/attention.py` 本 story 新增 ≤ +12 行（hard cap）；累积 ≤ 12/80**（baseline 实测 = `wan/modules/attention.py:0`，2026-04-26 `python3 tools/check_npu_line_budget.py` 输出确认）；目标值见 Task 3.x（target +6 / +8，hard cap +12）
   **And** 适配逻辑（`dispatch_memory_efficient_attention` / NPU layout 转换 / lazy `torch_npu` import）**必须**外置到 `wan/_npu_adapter/attention_dispatch.py`（与 Story 1.2 的 `device.py` / Story 1.3 的 `xfuser_stub.py` 同一适配层目录约定 — 见 Dev Notes § 适配层目录扩展）

6. **AC-6（`--device cuda` runtime 上 NPU 适配代码零侧效 — FR-18 / NFR-05 复刻 1.2 / 1.3 模式）**
   **Given** `--device cuda` 路径（任何 `world_size`）
   **When** 进程运行任意推理路径（包括 multitalk / i2v / t2v / flf2v 4 模式，由 Epic 4 在本 story 之后接手验证）
   **Then** `wan/_npu_adapter/attention_dispatch.py` 的 import 不引入 CUDA 路径行为变化（dispatch 在 `q.device.type == "cuda"` 时直通到 `xformers.ops.memory_efficient_attention`，输入输出字符等价）
   **And** `wan/_npu_adapter/attention_dispatch.py` 顶层**不** import `torch_npu` / `torch.npu`（与 Story 1.2 `_import_torch_npu()` lazy import 形态一致；CUDA 路径上 `torch_npu` 不进入 `sys.modules`）
   **And** `wan/modules/attention.py` 顶层**不**新增任何 `torch_npu` import（grep 验证：`grep -nE "^import torch_npu|^from torch_npu" wan/modules/attention.py` 必须返回 0 行）
   **Verified by**: Task 4.2 / 4.3 grep（静态 import 表面）+ **smoke CASE 3**（runtime — `not any(name.startswith('torch_npu') for name in sys.modules)` after dispatch on cuda tensor — 见 Task 5 重新编号后的 CASE 3）作为 binding runtime evidence。

7. **AC-7（适配层 git revert 单组撤回 — NFR-03 复刻 1.2 / 1.3 模式）**
   **Given** 本 story 完成后
   **When** 在 `wan/_npu_adapter/attention_dispatch.py`（新增）+ `wan/modules/attention.py`（修改）上执行 `git diff --stat HEAD~1` 检查
   **Then** 本 story 的所有适配代码可以被一组 `git revert` commit 完全撤回
   **And** revert 还原文件至 pre-story-1.4 状态（即 Story 1.3 完成态）；commitment 是**无外来制品**残留 —— revert 后不应有 cache、build 产物、side files 残留（`git status --porcelain` 在 revert 后必须无未追踪文件归因到本 story；smoke harness 在 `_gomad-output/` 下不计入主路径）

8. **AC-8（dispatch 逻辑 dry-run smoke 烟测 — 复刻 Story 1.2 / 1.3 surrogate 留痕模式）**
   **Given** 一个**纯导入 + mock device 调用 dry-run** smoke harness（不真正加载 NPU / xformers 实现，不真正调用 `torch_npu.npu_fusion_attention`，不真正调用 `xformers.ops.memory_efficient_attention`）
   **When** 在 dev box / CUDA host 上调用 `wan/_npu_adapter/attention_dispatch.py` 的公共 helper：
   - **CASE 1**（CUDA passthrough）：mock `q.device.type == "cuda"`；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`；期望调用流转入 mock 的 `xformers.ops.memory_efficient_attention`；mock spy 验证 args 字符等价（q/k/v/attn_bias=None/op=None 都 forward 不变）
   - **CASE 2**（NPU + BNSD layout）：mock `q.device.type == "npu"` + mock `torch_npu.npu_fusion_attention`；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None)`；期望路由到 mock 的 `npu_fusion_attention`，kwargs 含 `input_layout="BNSD"` + `head_num` + `scale`，**不**含 `actual_seq_qlen` / `actual_seq_kvlen`；返回值 = mock spy tuple 的第 0 项（**不**验证数值 — 真实数值正确性属 Story 1.5）
   - **CASE 3**（CUDA 路径不触发 torch_npu import — AC-6 物理判定线）：先 `_purge_torch_npu_modules()`（pop 所有 `torch_npu*` 项）；mock `q.device.type == "cuda"` + mock `xformers.ops.memory_efficient_attention`；调用 `dispatch_memory_efficient_attention(q, k, v)`；断言 `not any(name.startswith('torch_npu') for name in sys.modules)`
   - **CASE 4**（NPU + BlockDiagonalMask 显式 NotImplementedError — AC-2 防御性诊断）：mock `q.device.type == "npu"` + mock `BlockDiagonalMask` 实例（任何 attribute；本 case 不消费）；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=mock_block_diag)`；期望抛 `NotImplementedError`，错误消息字面包含 "BlockDiagonalMask" 与 "Phase 2"（or "multi-card NPU OOS"）；traceback 顶帧归因明确指向 dispatch 主体（不是 layout 转换内部）
   **Then** smoke harness 全部 case PASS
   **And** PR 描述粘贴 smoke harness 的 stdout 片段作为 AC-8 evidence（与 Story 1.1 / 1.2 / 1.3 的 evidence 留痕模式一致）

### Out-of-Scope Verification（不属于本 story 的承诺 — 显式声明，**非** AC）

> 本节是 **scope disclaimer**，不计入 8 个 AC 数；写下来仅为让 dev / reviewer 第一时间看到本 story 边界，避免"为什么本 story smoke 没验 NPU 数值"的反复问询。
>
> **NPU 数值正确性**：本 story **不**承担 `npu_fusion_attention` 输出与 `xformers.memory_efficient_attention` 输出的数值比对（PRD § FR-05 隐含项）。本 story 仅满足"dispatch 逻辑可达 + CUDA 字符等价 + NPU BNSD 入口参数形态正确 + BlockDiagonalMask 在 NPU 上显式 NotImplementedError"。真实 NPU 数值验证移交 Story 1.5（multitalk happy path 在真实 910B 上跑通时 implicit 验证 — 输出视频 ffprobe 通过即代表 attention 数值在可接受范围）；如 Story 1.5 跑通失败定位到 attention 数值偏差，按 NFR-09 / Story 2.x escalation workflow 处理（**不**回流本 story）。本 story 不引入"NPU 数值参考实现"的对比测试（无 NPU 硬件无法实施；不在本 story scope）。
>
> **多卡 NPU SP 路径**：本 story 在 `BlockDiagonalMask + npu` 组合上抛 `NotImplementedError` 而非真正实现 TND layout —— 多卡 SP NPU 路径属 Phase 2 单独立项（与 Story 1.3 单卡 MVP scope 对齐）。`actual_seq_qlen` / `actual_seq_kvlen` cumulative 格式探查（前置 0 vs 无前置 0；与 CANN `npu_fusion_attention` 文档对齐）也一并延期。
>
> **`wan/modules/model.WanModel` 的 NPU 适配**：i2v/t2v/flf2v 主路径的 `flash_attention` 链路 NPU 行为不在本 story scope（实测验证 model.py 不消费 xformers — 见 AC-4 grep 锚定）；属 Story 1.5（happy path 隐式 fallback 触动）/ Epic 4 territory。

## Tasks / Subtasks

- [x] **Task 1**：扩展 NPU 适配层目录（不计入 5 个主路径文件预算 — AC-5 / AC-7）
  - [x] 1.1 在 `wan/_npu_adapter/` 内新建 `attention_dispatch.py`（与 Story 1.2 的 `device.py` / Story 1.3 的 `xfuser_stub.py` 同目录；保持 NFR-03 单组 git revert 可撤回的物理载体）
  - [x] 1.2 文件顶部添加 module docstring，参考 `wan/_npu_adapter/device.py:1-20` / `wan/_npu_adapter/xfuser_stub.py:1-25` 的注释风格 —— 注明：(a) 本模块承载 FR-05 / FR-06 attention dispatch 逻辑；(b) lazy import 边界 = `q.device.type == "npu"` 才触发 `torch_npu` import；(c) 不在主路径白名单 = NFR-02 行预算豁免；(d) 公共 API 只暴露 1 个函数（`dispatch_memory_efficient_attention`），可选 1 个内部 helper（`_npu_dispatch` 等，看实现拆分需要）
  - [x] 1.3 **绝对不允许**在该目录之外创建新 NPU-only 文件（保持 NFR-03 单组 git revert 可撤回；与 Story 1.2 / 1.3 同约定）
  - [x] 1.4 **`__init__.py` re-export 决策**：`dispatch_memory_efficient_attention` 由 caller 通过**子模块直接路径** `from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention` 导入，**不**从 `wan/_npu_adapter/__init__.py` re-export —— 与 Story 1.2 `device.py` 的 `set_device` / `resolve_torch_device` / `assert_single_card_or_fail` 的 caller import 模式一致（caller `wan/multitalk.py` 内 `from wan._npu_adapter.device import resolve_torch_device` 等，非 `from wan._npu_adapter import ...`）。`wan/_npu_adapter/__init__.py` 文件本 story **不修改**（保持 Story 1.2 落地的 docstring + 空导出形态）。

- [x] **Task 2**：实现 attention dispatch 公共 API（`wan/_npu_adapter/attention_dispatch.py`）— FR-05 / FR-06 核心载体（**BNSD-only**；BlockDiagonalMask + NPU 显式 NotImplementedError）
  - [x] 2.1 提供函数 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None) -> torch.Tensor`：
    ```python
    def dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None):
        """Device-aware attention dispatch (Phase 1 single-card MVP).

        - q.device.type == "cuda" → 透明放行至 xformers.ops.memory_efficient_attention
          （字符等价 — NFR-05 hard）
        - q.device.type == "npu" + attn_bias is None → BNSD 路由到 torch_npu.npu_fusion_attention
          （lazy import；单卡 MVP 唯一 in-scope NPU 形态）
        - q.device.type == "npu" + isinstance(attn_bias, BlockDiagonalMask) → NotImplementedError
          （多卡 SP NPU 路径属 Phase 2 OOS；与 Story 1.3 单卡 MVP scope 对齐）
        - 其他 → ValueError（防御性；--device 已 argparse choices 限制 cuda/npu）
        """
        if q.device.type == "cuda":
            import xformers.ops  # local import；CUDA 上字符等价于上游 — 见 Task 2.3 决策
            return xformers.ops.memory_efficient_attention(q, k, v, attn_bias=attn_bias, op=op)
        if q.device.type == "npu":
            return _npu_dispatch(q, k, v, attn_bias=attn_bias)
        raise ValueError(
            f"Unsupported device type '{q.device.type}'; expected 'cuda' or 'npu'"
        )
    ```
    （CUDA 路径**字符等价**于上游；NPU 路径委托给 `_npu_dispatch`）
  - [x] 2.2 提供内部 helper `_npu_dispatch(q, k, v, attn_bias) -> torch.Tensor`：lazy import `torch_npu`；**仅** BNSD（attn_bias is None）；BlockDiagonalMask 显式 NotImplementedError：
    ```python
    def _npu_dispatch(q, k, v, attn_bias):
        # BlockDiagonalMask + NPU 是多卡 SP 路径 — 单卡 MVP 不实现；Phase 2 单独立项
        if attn_bias is not None:
            # 不直接 import xformers.ops.fmha.attn_bias.BlockDiagonalMask（NPU host 可能不装 xformers）；
            # 通过类型字面字符 + duck-typing 判定：BlockDiagonalMask 实例的 __class__.__name__ == "BlockDiagonalMask"
            cls_name = type(attn_bias).__name__
            raise NotImplementedError(
                f"BlockDiagonalMask attention on NPU is multi-card NPU OOS Phase 1 "
                f"(got attn_bias of type {cls_name!r}); "
                f"single-card NPU path uses attn_bias=None (BNSD). "
                f"Multi-card SP NPU support is Phase 2."
            )

        try:
            import torch_npu  # noqa: F401  (lazy；CUDA 路径不进入)
        except ImportError as exc:  # pragma: no cover - 取决于 host 环境
            raise RuntimeError(
                "torch_npu not importable; install requirements-npu.txt "
                "and ensure CANN driver loaded"
            ) from exc

        # BMHK 形态 (B, M, H, K)（xformers 调用方约定 — 见 wan/modules/attention.py:253-255 rearrange "B H M K -> B M H K"）
        head_num = q.shape[-2]                # H
        scale = 1.0 / (q.shape[-1] ** 0.5)    # 1 / sqrt(head_dim) = xformers 默认 scale

        # BNSD layout：(B, N, S, D) = (B, H, M, K)；调用方是 (B, M, H, K) BMHK，需要 transpose H 与 M 维
        # （或选择直接传 BMHK 然后 input_layout="BSND"；CANN 文档支持 BNSD/BSND/SBH/TND）—— dev agent 按 CANN
        # `torch_npu.npu_fusion_attention` 文档 verify 选用最贴合 BMHK 的 input_layout 标识；推荐 "BSND" 避免无谓 transpose
        return torch_npu.npu_fusion_attention(
            q, k, v,
            head_num=head_num,
            input_layout="BSND",  # 或 "BNSD" — dev agent 按 q.shape 实际维度顺序 + CANN 文档对齐选用
            scale=scale,
        )[0]  # npu_fusion_attention 返回 tuple；取第 0 项作为 output
    ```
    （**注**：上述代码示例是**实施参考蓝本**，dev agent 实施时按 baseline 真实 `q` / `k` / `v` shape 与 CANN `npu_fusion_attention` 文档 verify 选 `input_layout` 字符；返回 tuple 元素数与第 0 项语义以 CANN 当前版本文档为准）
  - [x] 2.3 **不**在本文件 import `torch_npu` / `torch.npu` 在顶层（与 Story 1.2 / 1.3 lazy import 形态一致；AC-6 物理保证）。**xformers 优先 local import 形态**（在 CUDA 分支函数体内 `import xformers.ops`）—— 让 NPU host 上 dispatch 进 NPU 分支前完全不 import xformers（防御性；NPU host 上 xformers 可能装也可能没装 — 不假设）。详见 Dev Notes § import 形态决策。
  - [x] 2.4 暴露的公共 API 严格 = 1 个函数（`dispatch_memory_efficient_attention`），`_npu_dispatch` 用 `_` 前缀私有化（避免 adapter 层接口蔓延 — 与 Story 1.2 / 1.3 公共 API 数控制约束一致）。**显式不引入** `_extract_seqlens` / `_to_cumulative_int32` / TND layout helper —— 这些是多卡 SP NPU Phase 2 territory，本 story 不实现。

- [x] **Task 3**：在 `wan/modules/attention.py` 注入 dispatch 调用（AC-1 / AC-2 / AC-3 / AC-4 / AC-5）
  - [x] 3.1 **改写 grep 锚定的两处 `xformers.ops.memory_efficient_attention` 调用点**（实测 baseline grep `grep -n "xformers.ops.memory_efficient_attention" wan/modules/attention.py` 锚定 line 266 + line 380；不依赖 absolute line numbers — 由 grep 唯一定位）：
    - **第 1 处**（`SingleStreamAttention.forward()` 内 `attn_bias=attn_bias` 调用，grep 锚定 line 266）：
      **现状**：
      ```python
      x = xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None,)
      ```
      **目标**：
      ```python
      from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention
      x = dispatch_memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None)
      ```
      （`from` import 可放在 module 顶层 attention.py 而非 inline — 见 Task 3.3 import 位置决策）
    - **第 2 处**（`SingleStreamMutiAttention.forward()` 内 `attn_bias=None` 调用，grep 锚定 line 380）：
      **现状**：
      ```python
      x = xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=None, op=None,)
      ```
      **目标**：
      ```python
      x = dispatch_memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=None, op=None)
      ```
  - [x] 3.2 **保留**所有其他 `wan/modules/attention.py` 字符 —— 包括：
    - `flash_attention()` 函数体（line 33-139，CUDA flash_attn 链路；与本 story 正交）
    - `attention()` 函数体（line 142-188，FA fallback 到 `torch.nn.functional.scaled_dot_product_attention`；与本 story 正交）
    - `SingleStreamAttention.__init__` / `SingleStreamMutiAttention.__init__`（class 定义；不修改）
    - `import xformers.ops`（顶层 line 11；CUDA 路径仍需要 — 不删除，避免破坏 NFR-05 字符等价 + 避免破坏 `BlockDiagonalMask.from_seqlens(...)` 的构造调用）
    - `from xfuser.core.distributed import (...)`（顶层 line 6-10；上游 xfuser SP imports — 不删除）
    - 所有 `BlockDiagonalMask.from_seqlens(...)` 构造调用（grep 锚定 line 263 + line 539；CUDA 路径仍需要这个 attn_bias 对象传入 dispatch；NPU 路径在 dispatch `_npu_dispatch` 入口仅通过 `attn_bias is not None` 判定后即抛 `NotImplementedError`，**不**消费 BlockDiagonalMask 内部属性）
  - [x] 3.3 **新增 import** 形态决策：
    - **方案 A（顶层 import）**：在 `wan/modules/attention.py` 顶层（紧接 `import xformers.ops` 之后）追加：
      ```python
      from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention
      ```
      **优点**：调用点行 unchanged 字符多 — 仅函数名替换 1 处 import + 2 处 call → 累积 +3 行 added；
      **缺点**：顶层 import 会让 `wan/_npu_adapter/attention_dispatch.py` 在 attention.py import 时立即加载（不影响 — 因为 dispatch_memory_efficient_attention 顶层不 import torch_npu）
    - **方案 B（局部 import — 调用站点 inline）**：在两处 `forward()` 方法内调用前 inline import：
      ```python
      from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention
      x = dispatch_memory_efficient_attention(...)
      ```
      **优点**：物理上 deeper lazy；
      **缺点**：累积 added = 2 import + 2 call replace = +4 行；且每次 forward 调用都重新 import（CPython import cache 命中 — 无运行期开销，但代码看起来"本不该这么重复"）
    - **决议**：**优先方案 A**（顶层 import 1 行 + 调用点 2 处 line modification）—— 累积 +3 行 added，干净；因为 `attention_dispatch.py` 顶层不 import `torch_npu`，方案 A 在 CUDA host 上 startup 不引入 NPU 副作用（与 AC-6 兼容）
  - [x] 3.4 行预算分析（净 added，target 形态）：
    - **顶层新增 import**（方案 A）：+1 行（`from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention`）
    - **调用点 1**（line 266）：modification（1 added + 1 deleted = +1 added per `git diff --numstat`）
    - **调用点 2**（line 380）：modification（1 added + 1 deleted = +1 added per `git diff --numstat`）
    - **总 added = 3 行**（target；hard cap +12 留 9 行余量供 dev agent 处理 helper rename / try-except / docstring 等微调；累积 = baseline 0 + 本 story 3 = 3/80）
    - **若**实施过程发现需 +6 / +8 / +12 也允许（target = +3 / +6；hard cap = +12，远低于 80 行 budget）
  - [x] 3.5 行预算目标 / 上限：本 story `wan/modules/attention.py` added **target = +3（lower）/ +6（upper）；hard cap = +12**；累积上限 = baseline 0 + 本 story 12 行 = **12/80**（远低于 80 行 hard cap）。**实测 added = 3** （`wan/modules/attention.py:3` — lint gate stdout 确认；命中 target lower bound）

- [x] **Task 4**：行预算 + import 形态 invariant 自检（AC-5 / AC-6 / Story 1.1 lint gate 兼容）
  - [x] 4.1 本地运行 `python3 tools/check_npu_line_budget.py` → EXIT=0；预期 stdout（基于 Task 3 target +3 / hard cap +12）：
    ```
    wan/modules/attention.py:3        # target；本 story 首次改动（前置 Story 1.1/1.2/1.3 均不动此文件）；hard cap 12
    wan/multitalk.py:6                # 累积 — 不变（introduced by Story 1.3）
    wan/distributed/xdit_context_parallel.py:0  # zero-touch hard（与 Story 1.3 衔接契约一致）
    generate_infinitetalk.py:12       # 累积 — 不变（introduced by Story 1.2）
    app.py:0                          # zero-touch（Story 3.1 territory）
    ```
    （`wan/modules/attention.py` 累积 3-12 之间均可；超 80 必触发 lint gate fail）。**实测 EXIT=0**，`wan/modules/attention.py:3`（命中 target lower bound）。
  - [x] 4.2 验证 `wan/modules/attention.py` 顶层无 `torch_npu` import（AC-1 / AC-6）：
    ```bash
    grep -nE "^import torch_npu|^from torch_npu" wan/modules/attention.py
    # 必须返回 0 行
    ```
    **实测**：返回 0 行 ✓
  - [x] 4.3 验证 `wan/_npu_adapter/attention_dispatch.py` 顶层无 `torch_npu` import（AC-6）：
    ```bash
    grep -nE "^import torch_npu|^from torch_npu" wan/_npu_adapter/attention_dispatch.py
    # 必须返回 0 行
    ```
    **实测**：返回 0 行 ✓
  - [x] 4.4 验证 `wan/distributed/xdit_context_parallel.py` zero-touch（AC-5 hard 约束）：
    ```bash
    git diff --numstat <baseline_commit>..HEAD -- wan/distributed/xdit_context_parallel.py
    # 期望第 1 列（added）= 0；baseline_commit = fd631497254e065777f2b2d0642de3600d674e24（Story 1.1 锚定）
    ```
    **实测**：working-tree numstat 输出空（无变更）✓ + lint gate stdout `wan/distributed/xdit_context_parallel.py:0` ✓
  - [x] 4.5 验证两处 dispatch 调用点实际生效 + `xformers.ops.memory_efficient_attention(` 字面已清零（AC-1 hard 验证）：
    ```bash
    grep -nE "dispatch_memory_efficient_attention\(" wan/modules/attention.py
    # 期望命中 2 行（line 266 + line 380 周围 — 描述性快照；grep 唯一）
    grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py
    # 期望命中 0 行（AC-1 hard contract — 已全部替换为 dispatch 调用）
    grep -nE "xformers\.ops\.fmha\.attn_bias\.BlockDiagonalMask\.from_seqlens" wan/modules/attention.py
    # 期望命中 1 行（line 263 — CUDA 路径仍需要构造此对象传入 dispatch；NPU 路径在 _npu_dispatch
    # 内通过 isinstance / type().__name__ 判定后抛 NotImplementedError）
    grep -nE "^import xformers\.ops" wan/modules/attention.py
    # 期望命中 1 行（line 11 — CUDA 路径仍需要顶层 import）
    ```
    **注**：`xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(...)`（line 263）应**保留**（CUDA 路径构造 attn_bias 对象用；NPU 路径仅在 `_npu_dispatch` 入口判定 `attn_bias is not None` 即抛 NotImplementedError，**不**消费内部 attribute）
    **实测**：dispatch grep 命中 line 267 + 381（描述性快照；上游 cosmetic shift 让 +1 偏移），`xformers.ops.memory_efficient_attention(` grep 0 行 ✓（AC-1 hard contract），BlockDiagonalMask.from_seqlens grep 命中 line 264（保留），`^import xformers\.ops` grep 命中 line 11（保留）✓
  - [x] 4.6 **`actual_seq_qlen` 格式探查移交 Phase 2**（与 Task 2 单卡 MVP 范围对齐）：本 story **不**实现 TND layout，因此**不需要**探查 CANN `torch_npu.npu_fusion_attention` 文档中 `actual_seq_qlen` 的 cumulative 格式（前置 0 vs 无前置 0：`[l1, l1+l2, ...]` vs `[0, l1, l1+l2, ...]`）。该探查 + TND layout 实现统一移交 Phase 2 多卡 SP NPU story。`BlockDiagonalMask` attribute 探查（旧 Task 4.6 内容）也一并 drop —— `_npu_dispatch` 仅通过 `attn_bias is not None` + `type(attn_bias).__name__` 字面判定，**不**消费 BlockDiagonalMask 内部属性。
  - [x] 4.7 在 PR 描述 paste Task 4.1 / 4.2 / 4.3 / 4.4 / 4.5 的 stdout（与 Story 1.1 / 1.2 / 1.3 evidence 留痕模式一致）— 见 Dev Agent Record § Debug Log References。

- [x] **Task 5**：smoke harness 烟测（AC-8）— 复刻 Story 1.2 / 1.3 surrogate 留痕（**4 个 case**，BNSD-only + NotImplementedError）
  - [x] 5.1 新建 `_gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py`（与 Story 1.2 的 `smoke_test_1_2_device_factory.py` / Story 1.3 的 `smoke_test_1_3_xfuser_stub.py` 同目录；不计入主路径行预算）
  - [x] 5.2 smoke harness 覆盖 4 个 case（AC-8 列表，与 AC-8 case 编号严格对齐）：
    - **CASE 1**（CUDA passthrough）：mock `q.device.type == "cuda"` + mock `xformers.ops.memory_efficient_attention`（spy）；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`；断言：(a) mock spy 被调用 1 次；(b) 调用 args == (q, k, v)，kwargs == {"attn_bias": None, "op": None}；(c) 返回值是 mock spy 的返回值（字符等价）；(d) `not any(name.startswith('torch_npu') for name in sys.modules)`（CUDA 路径不触发 NPU import）
    - **CASE 2**（NPU + BNSD layout，attn_bias=None）：mock `q.device.type == "npu"` + mock `torch_npu.npu_fusion_attention`（spy 返回 `(out, max, sum, *_)` tuple）；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`；断言：(a) mock spy 被调用 1 次；(b) 调用 kwargs 含 `input_layout` 字面（"BNSD" 或 "BSND"，与 Task 2.2 实施选用一致）+ `head_num` 参数 + `scale`；(c) 不含 `actual_seq_qlen` / `actual_seq_kvlen`（本 story 不实现 TND）；(d) 返回值是 mock spy tuple 的第 0 项
    - **CASE 3**（CUDA 路径不触发 torch_npu import — AC-6 物理判定线 / AC-6 binding runtime evidence）：先 `_purge_torch_npu_modules()`（pop 所有 `torch_npu*` 项）；mock `q.device.type == "cuda"` + mock `xformers.ops.memory_efficient_attention`；调用 `dispatch_memory_efficient_attention(q, k, v)`；断言 `not any(name.startswith('torch_npu') for name in sys.modules)` 在调用后仍成立
    - **CASE 4**（NPU + BlockDiagonalMask 显式 NotImplementedError — AC-2 防御性诊断）：mock `q.device.type == "npu"` + 构造 mock 类 `class _MockBlockDiagonalMask: pass`（`type(instance).__name__ == "_MockBlockDiagonalMask"`，或直接命名 `BlockDiagonalMask` 让字面匹配 — dev agent 实施时按 `_npu_dispatch` 内部判定方式选）；调用 `dispatch_memory_efficient_attention(q, k, v, attn_bias=mock_bdm)`；期望抛 `NotImplementedError`；断言：(a) 异常类型 == `NotImplementedError`；(b) 异常消息字面含 "BlockDiagonalMask" + "Phase 2"（or "multi-card NPU OOS"）；(c) traceback 顶帧归因明确（来自 `_npu_dispatch` 主体，非 layout 转换内部 — 因为本 story 没有 layout 转换内部）；(d) `torch_npu` **未**进入 `sys.modules`（lazy import 在 NotImplementedError 之后才会触发；本 case `attn_bias is not None` 让 NotImplementedError 在 import 之前抛出 — 验证 import 顺序正确）
  - [x] 5.3 smoke harness 形态参考 `_gomad-output/implementation-artifacts/smoke_test_1_3_xfuser_stub.py`（importlib.util.spec_from_file_location 直接加载 + sys.modules 操作 + mock spy）；本 story smoke 比 1.3 略复杂 —— 需要 stub `torch.Tensor` 子集（提供 `.device.type` / `.shape` 接口；**不**需要 `.flatten` / `.unflatten` 因为 TND 已 drop）+ mock `torch_npu.npu_fusion_attention` + mock `xformers.ops.memory_efficient_attention`；**不**需要 mock `BlockDiagonalMask` 内部 attribute（`_npu_dispatch` 仅通过 `attn_bias is not None` + `type().__name__` 判定）；具体 mock 形态由 dev agent 实施时按 dispatch 实际调用面收口
  - [x] 5.4 在 PR 描述 paste smoke harness 的 stdout（**4 case PASS** 报告）作为 AC-8 evidence — 见 Dev Agent Record § Debug Log References。

- [x] **Task 6**：deferred-work review（no items adopted — 与 Story 1.3 § "Deferred-work review (no items adopted)" 同契约）
  - [x] 6.1 经审视 `_gomad-output/implementation-artifacts/deferred-work.md` 截至 Story 1.3 完成态的 5 条 LOW 项（1-1 #1/#2/#3 + 1-2 #1/#2），与本 story 主题（attention dispatch）均不直接相邻 —— 本 story **不吸收**任何 LOW 项；按"改动文件直接重叠"判断标准留待后续 stories 集中清算
  - [x] 6.2 如本 story 实施过程中产生新 LOW 遗留，按既有约定追加至 `deferred-work.md` 的 "From Story 1-4" 段落（与 Story 1.1 / 1.2 / 1.3 evidence 留痕模式一致）— 实施未产生新 LOW 遗留（dispatch BNSD 入口 / BlockDiagonalMask NotImplementedError / smoke harness 4 case 全部按 PM 评审修订后 scope 干净落地，无残留 archaeology / 决策待定项）。

## Dev Notes

> **核心定位**：本 story 是 Epic 1 五步 ordered checklist 的第 4 步（"attention adapter C3 — 依赖 C1 的设备 dispatch"），承前启后：前置 Story 1.2 已落地 `--device` flag + `set_device` / `resolve_torch_device` + `assert_single_card_or_fail`（让 Q/K/V tensor 落到正确 device）；前置 Story 1.3 已落地 xfuser 单卡桩化（让单卡路径不进入 `xdit_context_parallel.py`，间接保证 `xdit_context_parallel.py:540` 调用点在单卡上不被触发，从而本 story 不需要 dispatch 那个调用点）；后置 Story 1.5 在真实 910B 上跑 multitalk happy path（verify 本 story 的 NPU 分支真实数值正确性，跑通即过 — 见 AC-9）。出错最大代价 = NPU 单卡推理因 attention dispatch 错位 / layout 错配 / lazy import 失败导致神秘 OOM 或精度崩塌（按 NFR-09 / Story 2.x escalation 处理 — 不阻塞本 story DoD）。

### 关键架构约束（来自 architecture-summary.md § 3 attention 算子替换）

引用原文（pin 死）：

> **Attention 算子替换（FR-05 / FR-06）**：
> - 在 `wan/modules/attention.py:263,266,380` + `wan/distributed/xdit_context_parallel.py:540` 共 4 处调用点引入 device-aware adapter wrapper
> - adapter 在 `--device cuda` 时调用 `xformers.ops.memory_efficient_attention`；在 `--device npu` 时调用 `torch_npu.npu_fusion_attention`
> - 变长 attention（`BlockDiagonalMask` 形态）→ NPU 走 TND layout + `actual_seq_qlen/actual_seq_kvlen`
> - adapter 必须同时被两套 `WanModel` 共享（无 class-specific bypass）

> **本 story 对照解读**（PRD/architecture 原文 vs 实测 grep 校正）：
> - 上游架构原文写"`wan/modules/attention.py:263,266,380` + `wan/distributed/xdit_context_parallel.py:540` 共 4 处调用点"，**实测 grep**（2026-04-26）：
>   - `wan/modules/attention.py:263` = `attn_bias = xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(...)` —— **不是** `memory_efficient_attention` 调用，是 attn_bias **构造**（CUDA 路径仍需要构造该对象传入 dispatch；本 story **不**改这一行）
>   - `wan/modules/attention.py:266` = `xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None,)` ✓ —— **是**调用点，本 story 改 1 处
>   - `wan/modules/attention.py:380` = `xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=None, op=None,)` ✓ —— **是**调用点，本 story 改 2 处
>   - `wan/distributed/xdit_context_parallel.py:540` = `xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None,)` —— **是**调用点，但单卡路径不进入此文件（Story 1.3 short-circuit 物理保证）；本 story 严格 **zero-touch** 此文件（与 Story 1.3 衔接契约 + AC-5 hard 约束）
> - **结论**：架构原文"4 处调用点"在本 story scope 收缩为"2 处调用点 in `wan/modules/attention.py`"；line 540 在多卡 CUDA 路径继续走上游 xformers（NFR-05 字符等价），多卡 NPU 路径在 Phase 2 单独立项处理（OOS）。
> - 上游架构原文中的 line numbers 是写作时（架构 summary 起草日期）的快照，本 story 实施时以 `grep -n "xformers.ops.memory_efficient_attention" wan/modules/attention.py` 实测结果为准（baseline 2026-04-26 line 266 + 380；上游 cosmetic shift 都会变）。

本 story 四条 invariant 的物理实现（**Phase 1 单卡 MVP scope**）：

| 架构 invariant | 本 story 物理实现 | 验证 AC |
|---------------|------------------|---------|
| `--device cuda` → `xformers.ops.memory_efficient_attention` | dispatch helper 在 `q.device.type == "cuda"` 分支透明放行；args / kwargs 字符等价 | AC-3 / CASE 1 |
| `--device npu` + `attn_bias is None` → `torch_npu.npu_fusion_attention` BNSD | dispatch helper 在 `q.device.type == "npu"` 分支 lazy import torch_npu + 调 `npu_fusion_attention` (`input_layout="BNSD"` 或 "BSND") | AC-1 / CASE 2 |
| `BlockDiagonalMask` + `--device npu` → 显式 `NotImplementedError` | `_npu_dispatch` 入口判定 `attn_bias is not None` 即抛 NotImplementedError（消息含 "BlockDiagonalMask" + "Phase 2"）；不实现 TND layout | AC-2 / CASE 4 |
| FR-06（multitalk 路径无 class-specific bypass — 收缩范围） | 本 story 改的是 `wan/modules/attention.py` 内的 `SingleStreamAttention.forward()` / `SingleStreamMutiAttention.forward()`；`multitalk_model.WanModel` 通过 `from .attention import ...` 进入这两个 forward —— 无 class-specific bypass。`model.WanModel`（i2v/t2v/flf2v）grep 验证不消费 `xformers.ops.memory_efficient_attention`（trivially 继承 FR-06；显式 OOS 至 Story 1.5 / Epic 4） | AC-4 |

### `wan/_npu_adapter/` 适配层目录扩展

本 story 在 Story 1.2 / 1.3 已建立的目录上新增 `attention_dispatch.py`：

```
wan/
├── _npu_adapter/             ← Story 1.2 引入；NFR-03 "可一组 git revert" 的载体
│   ├── __init__.py           ← Story 1.2 落地（空 + docstring）
│   ├── device.py             ← Story 1.2 落地（设备工厂）
│   ├── xfuser_stub.py        ← Story 1.3 落地（xfuser 单卡桩化）
│   ├── attention_dispatch.py ← 本 story 新增（attention dispatch wrapper）
│   └── errors.py             ← Story 2.1 新增（错误翻译层）
├── modules/
│   └── attention.py          ← 本 story 修改：target +3 / hard cap +12 行（累积 12/80）
└── ...
```

> **为何 dispatch 文件名是 `attention_dispatch.py` 而非 `attention.py` / `attn_wrapper.py`**：与 PRD § FR-05 "attention 算子替换" + architecture-summary.md § 3 直接对齐，"dispatch" 标识词强调**device-aware 路由**而非"覆写 attention 实现"；维护者通过文件名即可定位"哪里实现了 FR-05/FR-06"。**避免** `attention.py` 命名与 `wan/modules/attention.py` 重名造成 import 歧义 / grep 噪音。

### `wan/modules/attention.py` baseline 调用点形态（实测 grep — 2026-04-26）

```bash
$ grep -nE "memory_efficient_attention|xformers" wan/modules/attention.py
11:import xformers.ops
263:            attn_bias = xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(visual_seqlen, kv_seq)
266:        x = xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None,)
380:        x = xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=None, op=None,)

$ grep -nE "flash_attn|flash_attention|sage|sdpa|scaled_dot_product_attention" wan/modules/attention.py
14:    import flash_attn_interface
20:    import flash_attn
28:    'flash_attention',
33:def flash_attention(
105:        x = flash_attn_interface.flash_attn_varlen_func(
122:        x = flash_attn.flash_attn_varlen_func(
158:        return flash_attention(
176:                'Padding mask is disabled when using scaled_dot_product_attention. ...'
184:        out = torch.nn.functional.scaled_dot_product_attention(
```

**关键观察**：
- `wan/modules/attention.py` 共 392 行（`wc -l` 验证 — 2026-04-26）
- `xformers.ops.memory_efficient_attention` 调用**仅 2 处**（line 266 + line 380）—— 本 story 改这两处
- `xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(...)` 构造调用**1 处**（line 263，仅在 `enable_sp=True` 时构造；`enable_sp=False` 单卡路径走 line 265 `attn_bias = None`）—— **不**修改（CUDA 路径仍需要构造此对象传入 dispatch；NPU 路径在 dispatch `_npu_dispatch` 入口判定 `attn_bias is not None` 即抛 NotImplementedError）
- `flash_attention()` / `attention()` 函数（line 33-188）使用 `flash_attn_interface` / `flash_attn` / `torch.nn.functional.scaled_dot_product_attention` —— **与本 story 正交**（本 story scope 严格限于 `xformers` → `npu_fusion_attention` 替换；flash_attn 在 NPU 上的行为留给 Story 1.5 happy path 隐式验证）
- `import xformers.ops`（顶层 line 11）—— **不删除**（CUDA 路径仍需要；line 263 的 `BlockDiagonalMask.from_seqlens(...)` 仍需要 `xformers.ops.fmha.attn_bias` 名空间）
- 顶层无任何 `torch_npu` import —— baseline 已满足 AC-6 物理保证；本 story 不引入

**结论**：本 story 在 `wan/modules/attention.py` 的全部职责 = (a) 添加顶层 `from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention` import 1 行；(b) 替换两处 `xformers.ops.memory_efficient_attention(...)` 调用为 `dispatch_memory_efficient_attention(...)` 调用（modification 2 行）；总累积 +3 行 added（target，hard cap +12）。

### Line-number reference policy（与 Story 1.3 § Line-number reference policy 同政策）

本 story 所有引用 `wan/modules/attention.py` 内部位置的地方**优先使用 grep 锚定字面**（如"含 `xformers.ops.memory_efficient_attention(` 字面的两行"、"含 `BlockDiagonalMask.from_seqlens(` 字面的行"）；**避免**写死 line 263 / 266 / 380 这类 absolute line numbers，因为上游 cosmetic shifts（空行 / 注释调整）会让数字漂移而 grep 锚定不漂。dev agent 实施时以 `grep -n "xformers.ops.memory_efficient_attention" wan/modules/attention.py` 输出为准。

### NPU layout 转换契约（Task 2.2 详细规约 — Phase 1 单卡 MVP BNSD-only）

`torch_npu.npu_fusion_attention` 的 layout 与 xformers `memory_efficient_attention` 的对应（**实施时按 CANN 2.5.1 / torch_npu 2.7.1 文档 verify**；本节是 dev agent 实施起点，不是终点）：

| 来源（attention.py 调用点） | 上下文 enable_sp | xformers 输入 | NPU 等价 layout | 关键参数 |
|------|------|--------------|----------------|---------|
| `SingleStreamAttention.forward()`（line 266 — 实测 grep `attn_bias = ...` 在 line 263，`else: attn_bias = None` 在 line 265） | **`enable_sp=True`** (多卡 SP 路径，attn_bias=BlockDiagonalMask) | `q/encoder_k/encoder_v` 形态 `(B, M, H, K)` BMHK；`attn_bias` 是 `BlockDiagonalMask` (变长) | **本 story 不实现** —— 抛 `NotImplementedError`（多卡 SP NPU OOS Phase 1） | N/A |
| `SingleStreamAttention.forward()`（line 266） | **`enable_sp=False`** (单卡 MVP 路径 — Story 1.3 short-circuit 物理保证；line 265 `attn_bias = None`) | `q/encoder_k/encoder_v` 形态 `(B, M, H, K)` BMHK；`attn_bias=None` (固定长) | `BNSD` 或 `BSND`（按 q.shape 维度顺序选用） | `head_num=H`, `input_layout="BNSD"` (or "BSND"), `scale=1/sqrt(D)` |
| `SingleStreamMutiAttention.forward()`（line 380） | (无 enable_sp 参数 — 仅固定长) | `q/encoder_k/encoder_v` 形态 `(B, M, H, K)` BMHK；`attn_bias=None` (固定长) | `BNSD` 或 `BSND` | `head_num=H`, `input_layout="BNSD"` (or "BSND"), `scale=1/sqrt(D)` |

> **关键 caveat**（dev agent 必读）：
> 1. **line 266 attn_bias 形态精确语义**：`wan/modules/attention.py` 实测 grep（2026-04-26）：line 257 `if enable_sp:` → line 263 `attn_bias = xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(visual_seqlen, kv_seq)`；line 264 `else:` → line 265 `attn_bias = None`；line 266 `x = xformers.ops.memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None,)`。即 line 266 的 `attn_bias` **仅当 `enable_sp=True` 时**为 `BlockDiagonalMask`，**否则**为 `None`。`enable_sp=True` 仅由 `wan/distributed/xdit_context_parallel.py:492` 设置（多卡 SP 路径）；单卡 MVP 路径（Story 1.3 short-circuit）实测 `enable_sp=False`（`SingleStreamAttention.forward()` 默认参数 `enable_sp=False` — 见 attention.py:227）→ `attn_bias=None` → BNSD 分支。**BlockDiagonalMask + NPU 组合在 Phase 1 不被实际触发**（多卡 NPU 路径 OOS）；本 story 实现的 NotImplementedError 仅是防御性诊断，让任何意外触发该组合时获得清晰错误。
> 2. `torch_npu.npu_fusion_attention` 返回 **tuple** `(output, softmax_max, softmax_sum, softmax_in, seed, offset, numels)`（具体长度见 CANN 文档）—— 取 `[0]` 作为 attention output；其他元素是反向传播 / debug 用，本 story 推理路径不需要
> 3. `head_num` 在 BMHK 形态下 = `q.shape[-2]`（dim H）；如 dev agent 的 reshape 把 H 维放别处，则 head_num 索引不同 —— 实施时按 `q.shape` 实际维度判定
> 4. `input_layout` 字符（"BNSD" vs "BSND" vs "BHSD"）按 CANN `torch_npu.npu_fusion_attention` 文档对齐 q.shape 实际维度顺序选用；本 story 调用方 q 形态是 BMHK 即 (B, M, H, K)，"BSND" 标识符通常对应这个 (Batch, Seq, Num_heads, Dim) 维度顺序。dev agent 实施时**优先**按 CANN 文档明确字符选用，而非猜测。

### import 形态决策（CUDA / NPU 解耦）

本 story `wan/_npu_adapter/attention_dispatch.py` 的 import 决策（按"side-effect 最小"排序）：

1. **顶层（绝对禁止）**：`import torch_npu` —— AC-1 / AC-6 hard 禁止；CUDA 路径上不应触发 NPU monkey-patch
2. **CUDA 分支函数体（建议 local import）**：`import xformers.ops` —— 让 NPU host 上 dispatch 进 NPU 分支前完全不 import xformers（防御性；NPU host 上 xformers 可能装也可能没装 — 不假设）
3. **NPU 分支函数体（hard 必须 local import）**：`import torch_npu` —— Story 1.2 `_import_torch_npu()` 已示范；本 story 复刻同形态
4. **顶层（允许）**：`import torch`（PyTorch 核心；CUDA / NPU host 都装；`torch.Tensor` 类型 hint 用）

### 与 Story 1.3 衔接契约（再次锚定）

Story 1.3 完成后，本 story 进入时的现状：

- `wan/modules/attention.py` 行预算余量 = 80（Story 1.3 0 触动）—— 本 story 消耗 +3 / hard cap +12
- `wan/distributed/xdit_context_parallel.py` 行预算余量 = 80（Story 1.3 0 触动；hard 约束 zero-touch）—— 本 story 严格 zero-touch（与 Story 1.3 § "本 story 与 Story 1.4 attention adapter 的衔接契约" 锚定）
- `wan/distributed/xdit_context_parallel.py:540` 调用点：仅在 multi-card 路径被 patch 进入 `usp_*_forward` 函数后才执行；单卡路径**不进入**（Story 1.3 short-circuit 物理保证）
- **传递契约 verify**：本 story 仅为 `wan/modules/attention.py` 两处调用点（line 266 + line 380）做 dispatch；**不**为 `wan/distributed/xdit_context_parallel.py:540` 写 dispatch（因为单卡不进入此调用 — Story 1.3 invariant 保证；多卡 CUDA 路径仍走上游 xformers — NFR-05 字符等价；多卡 NPU 路径 OOS / Phase 2）
- `wan/_npu_adapter/` 目录内 `__init__.py` / `device.py` / `xfuser_stub.py` —— 本 story **不**修改

### NFR-05 上游 CUDA 路径行为不变性保证（验证矩阵 — grep 锚定）

| 验证项 | 检查方法 | 期望 |
|--------|---------|------|
| `xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(...)` 构造调用不变（line 263） | `grep -n "BlockDiagonalMask.from_seqlens" wan/modules/attention.py` 仍命中 1 行 | 字符不变（CUDA 路径仍需要） |
| 顶层 `import xformers.ops` 不变（line 11） | `grep -n "^import xformers.ops" wan/modules/attention.py` 仍命中 1 行 | 字符不变（CUDA 路径仍需要） |
| `flash_attention()` / `attention()` 函数体字符不变 | `git diff <baseline_commit> -- wan/modules/attention.py` 在 line 33-188 范围 0 修改 | 字符不变（与本 story 正交） |
| `wan/distributed/xdit_context_parallel.py` 字符不变 | `git diff --numstat <baseline_commit>..HEAD -- wan/distributed/xdit_context_parallel.py` added=0 | 字符不变（zero-touch hard） |
| `dispatch_memory_efficient_attention` 在 `q.device.type == "cuda"` 分支 args / kwargs / 返回值字符等价 | smoke CASE 1 mock spy 验证 | 字符等价 ✓ |
| CUDA + multi-card dry-run 静态导入 attention.py 不报错 | `python3 -c "import wan.modules.attention"`（CUDA host） | exit 0 |

### 上游主路径文件 baseline 与零侵入对照表（更新版 — 累积 Story 1.2 / 1.3，实测 baseline 2026-04-26）

实测 baseline（`python3 tools/check_npu_line_budget.py` 输出，post-Story-1.3）：

```
wan/modules/attention.py:0
wan/multitalk.py:6
wan/distributed/xdit_context_parallel.py:0
generate_infinitetalk.py:12
app.py:0
```

> **来源归因**（introduced by — 让 reviewer 一眼追溯各累积行的故事来源）：
> - `wan/modules/attention.py:0` —— 本 story 之前**无任何**故事改动；本 story 是首次改动（target +3 / hard cap +12）。
> - `wan/multitalk.py:6` —— **introduced by Story 1.3**（xfuser 单卡桩化的 `if use_usp and not should_short_circuit_xfuser(_world_size):` short-circuit guard）。
> - `wan/distributed/xdit_context_parallel.py:0` —— Story 1.3 hard zero-touch 衔接契约；本 story 继续 zero-touch。
> - `generate_infinitetalk.py:12` —— **introduced by Story 1.2**（`--device {cuda,npu}` flag + `set_device(local_rank)` + `resolve_torch_device(device, device_id)` + `assert_single_card_or_fail`）。
> - `app.py:0` —— Story 3.1 territory；尚未触动。

| 文件 | 实测 Story 1.3 后累积 added | 来源归因 | 本 story 计划 added | 累积上限（含本 story） | 80 行 budget 余量（保守） |
|------|---------------------------|---------|---------------------|----------------------|---------------------------|
| `wan/modules/attention.py` | 0 | (无前置 — 本 story 首次改动) | target +3 / hard cap +12 | 3-12 | 68 |
| `wan/multitalk.py` | 6 | Story 1.3 | 0（zero-touch；归 Story 1.5 接手） | 6 | 74 |
| `wan/distributed/xdit_context_parallel.py` | 0 | (Story 1.3 hard zero-touch) | 0（zero-touch hard；与 Story 1.3 衔接契约一致） | 0 | 80 |
| `generate_infinitetalk.py` | 12 | Story 1.2 | 0 | 12 | 68 |
| `app.py` | 0 | (Story 3.1 territory) | 0（zero-touch；归 Story 3.1 接手） | 0 | 80 |

### Story 1.2 / 1.3 已落地资产（不重复实现）

- **Story 1.2**：`wan/_npu_adapter/{__init__,device}.py`（设备工厂 — `set_device` / `resolve_torch_device` / `assert_single_card_or_fail`）；`generate_infinitetalk.py` 的 `--device {cuda,npu}` flag + `set_device`（local_rank） + `resolve_torch_device(device, device_id)`（让 Q/K/V tensor 落到正确 device）
- **Story 1.3**：`wan/_npu_adapter/xfuser_stub.py`（短路助手 — `should_short_circuit_xfuser` / `get_sequence_parallel_world_size_safe`）；`wan/multitalk.py` 内 `if use_usp and not should_short_circuit_xfuser(_world_size):` short-circuit guard（让单卡路径不 import `xdit_context_parallel.py` 从而间接不进入 line 540 调用点）
- **Story 1.1**：`tools/check_npu_line_budget.py` lint gate；5 路径白名单 baseline；`requirements-npu.txt`（含 `torch_npu==2.7.1` exact pin；本 story 不修改）

### 本 story 与 Story 1.5 multitalk happy path 的衔接契约

Story 1.5 将在真实 910B host 上跑 `python generate_infinitetalk.py --device npu --task infinitetalk-14B --input examples/multitalk_demo.json ...`，期望产出 `out_multitalk.mp4` + ffprobe pass + exit code 0。本 story 完成后：

- **dispatch 逻辑可达**：单卡 NPU 路径 `q.device.type == "npu"` + `attn_bias=None`（`enable_sp=False` 单卡路径默认）→ 进入 `_npu_dispatch` 分支 → lazy import `torch_npu` 成功 → 调 `npu_fusion_attention` BNSD 落库
- **dispatch 数值正确性**：本 story **不验证**（无 NPU 硬件）；Story 1.5 跑通即代表 attention 数值在可接受范围（NFR-07 不要求 bit-exact CUDA↔NPU 输出等价）
- **Story 1.5 触发 attention dispatch 的预期路径**：
  1. `generate_infinitetalk.py` → `set_device("npu", local_rank)` + `resolve_torch_device("npu", device_id)` (Story 1.2)
  2. → `InfiniteTalkPipeline(...)` → `wan/multitalk.py` 内 `if use_usp and not should_short_circuit_xfuser(_world_size):` 走 else 分支 (Story 1.3)
  3. → `WanModel.forward` → `SingleStreamAttention.forward(enable_sp=False)` / `SingleStreamMutiAttention.forward()` → `dispatch_memory_efficient_attention(..., attn_bias=None, ...)` (本 story；`attn_bias=None` 由 attention.py:265 `else: attn_bias = None` 在 `enable_sp=False` 时设置)
  4. → `q.device.type == "npu"` → `_npu_dispatch(q, k, v, attn_bias=None)` → BNSD 分支 → `torch_npu.npu_fusion_attention(...)` → output tuple [0] → 视频帧
- **如 Story 1.5 在单卡 NPU 上意外触发 BlockDiagonalMask 路径**（理论上不应发生 — Story 1.3 short-circuit 物理保证 `enable_sp=False`）：本 story 实现的 NotImplementedError 立即抛出，错误消息字面 "BlockDiagonalMask" + "Phase 2"，让定位归因即时清晰；按 NFR-09 / Story 2.x escalation workflow 处理 —— **不**回流本 story DoD
- **如 Story 1.5 attention 数值偏差 / OOM / op-not-implemented**：按 NFR-09 / Story 2.x escalation workflow 处理 —— **不**回流本 story DoD（本 story DoD 仅含 dispatch 逻辑可达 BNSD + CUDA 字符等价 + smoke harness PASS）

### Testing Standards Summary

PRD § OOS-12 明确 MVP 阶段不要求 pytest CI 自动化套件。**本 story 例外**（与 Story 1.1 / 1.2 / 1.3 一致）：attention dispatch 的正确性可通过纯 dry-run + mock spy 烟测验证（无需真实 NPU / 真 torch_npu / 真 xformers 安装）。具体 5 case 见 Task 5。

烟测形式 = 本地 + macOS dev box（torch / xformers / torch_npu 均不可达）+ stub `torch.Tensor` 子集 + mock `xformers.ops.memory_efficient_attention` / `torch_npu.npu_fusion_attention` 双 spy + 直接调用 `wan/_npu_adapter/attention_dispatch.py` 公共 API + PR 描述 paste stdout，与 Story 1.1 / 1.2 / 1.3 一致。

> **关键不要**：本 story **不**引入 pytest fixture / unittest module —— 那会增加上游 rebase 表面（违反 NFR-04 ≤5 工作日演练）。dry-run + grep + stdout 留痕已足够覆盖 AC-1~AC-8。

> **关键不要 2**：本 story smoke harness **不**断言"NPU 数值 == CUDA 数值"—— 那要求真实 NPU 硬件 + 真实 xformers + 真实 torch_npu 同时跑通；与 NFR-07（不要求 bit-exact）也不一致。本 story smoke 仅断言 dispatch **逻辑路由**正确（哪个 device.type 进哪个分支 + args 形态正确）；数值正确性留 Story 1.5 真实硬件隐式验证（出视频 ffprobe 通过即可接受）。

### 已知 NPU 调用点遗留（**显式不在本 story scope，传递给下游 stories**）

- `flash_attention()` 函数（`wan/modules/attention.py:33-139`）使用 `flash_attn_interface.flash_attn_varlen_func` / `flash_attn.flash_attn_varlen_func` —— 本 story **不**改；Story 1.5 跑通时如发现 flash_attn 在 NPU 上不可用 / 数值错乱，按 NFR-09 处理（可临时禁用 FA 让 fallback 到 `attention()` else 分支的 `torch.nn.functional.scaled_dot_product_attention` —— PyTorch 原生 NPU 支持）
- `attention()` 函数（`wan/modules/attention.py:142-188`）的 FA fallback 分支 —— 本 story **不**改；Story 1.5 隐式验证
- `wan/distributed/xdit_context_parallel.py:540` 调用点 —— 本 story **严格 zero-touch**（与 Story 1.3 衔接契约 + AC-5 hard 约束一致）；多卡 NPU 路径 OOS / Phase 2 单独立项
- `wan/multitalk.py` 中的 `torch.cuda.empty_cache()` 等 hot-loop calls —— 本 story **不**改；Story 1.5 接手（与 Story 1.2 / 1.3 同契约）
- 两套 `WanModel`（`wan/modules/multitalk_model.py` / `wan/modules/model.py`）—— 本 story **不**改；FR-06 通过共享 `SingleStreamAttention` / `SingleStreamMutiAttention` 类间接满足（无 class-specific bypass — AC-4）

本 story 新引入的 import：`from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention` —— 该 import 在 `wan/modules/attention.py` 顶层执行，**不**触发 `torch_npu` import / **不**触发 `xformers` 副作用（attention_dispatch.py 顶层无重型 import；`xformers.ops` import 已在 attention.py 顶层 line 11 早就存在 — 本 story 不重复 import）；纯 stdlib + 本仓内 module 引用，无外部依赖。

### 命名 / 缩写约定

- `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`：动词 `dispatch_` 起头，回答"路由到哪个后端"；签名与 `xformers.ops.memory_efficient_attention` 字符一致（便于上游 rebase 时 grep 替换）；返回类型 = `torch.Tensor`（与 xformers 一致）
- `_npu_dispatch(q, k, v, attn_bias)`：单下划线私有；NPU 分支主体；不暴露给外部（避免 adapter 接口蔓延）
- `BNSD` / `BSND`：NPU layout 标识，与 CANN 文档一致 — `BNSD` = Batch-Num_heads-Seq-Dim（4D）；`BSND` = Batch-Seq-Num_heads-Dim（4D）；本 story 调用方 BMHK 形态对应 `BSND`，dev agent 实施时按 CANN `npu_fusion_attention` 文档对齐 q.shape 维度顺序选字符。
- **显式不引入**：`_extract_seqlens` / `_to_cumulative_int32` / `TND` 标识 —— 多卡 SP NPU TND layout 属 Phase 2 territory，本 story 不实现。

### Project Structure Notes

- **新增文件**：
  - `wan/_npu_adapter/attention_dispatch.py`（FR-05 / FR-06 attention dispatch 主体；1 个公共 API + 1 个私有 helper `_npu_dispatch`；BNSD-only NPU 实现 + BlockDiagonalMask NotImplementedError）
  - `_gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py`（Task 5 烟测 harness；4 case；不计入主路径行预算）
- **修改文件**（计入 NFR-02 行预算）：
  - `wan/modules/attention.py`（顶层新增 1 个 import + 替换 2 处调用；target +3 / hard cap +12 行 added；累积 3-12/80）
- **禁止修改**（zero-touch in this story）：
  - `wan/distributed/xdit_context_parallel.py`（hard 0/80 budget — 与 Story 1.3 衔接契约一致）
  - `wan/multitalk.py`（Story 1.5 接手 hot-loop CUDA-only 调用）
  - `generate_infinitetalk.py`（Story 1.2 已落 — 本 story 不动）
  - `app.py`（Story 3.1 接手）
  - `wan/modules/multitalk_model.py` / `wan/modules/model.py`（FR-06 通过共享 `SingleStreamAttention` / `SingleStreamMutiAttention` 间接满足 — 本 story 不直接动两套 `WanModel`）
  - `wan/modules/attention.py` 中的 `flash_attention()` / `attention()` / `BlockDiagonalMask.from_seqlens(...)` 构造调用 / 顶层 `import xformers.ops` 等所有非 grep 锚定的 `xformers.ops.memory_efficient_attention(...)` 调用点
  - `wan/image2video.py` / `wan/text2video.py` / `wan/first_last_frame2video.py`（Epic 4 的 stories 接手）
  - `requirements-npu.txt` / `requirements.txt`（Story 1.1 已落地）
  - `wan/_npu_adapter/{__init__,device,xfuser_stub}.py`（Story 1.2 / 1.3 已落地，本 story 不动）
  - `tools/check_npu_line_budget.py`（Story 1.1 + Story 1.2 Task 7 已落地）

### Story DoD（仅本 story 对 Epic 1 DoD 的贡献项）

| 本 story DoD 项 | 验证方式 |
|----------------|---------|
| `wan/_npu_adapter/attention_dispatch.py` 提供 1 个公共 API（`dispatch_memory_efficient_attention`） | AC-1 / AC-8 |
| `wan/modules/attention.py` 中 grep 锚定的两处 `memory_efficient_attention` 调用替换为 `dispatch_memory_efficient_attention` + `xformers.ops.memory_efficient_attention(` 字面 grep 0 行 | AC-1 / Task 4.5 grep 验证 |
| CUDA 路径字符等价：dispatch 在 `q.device.type == "cuda"` 透明放行 | AC-3 / smoke CASE 1 |
| NPU 路径 dispatch 逻辑可达：`q.device.type == "npu"` + `attn_bias is None` 落到 `npu_fusion_attention` BNSD 调用 | AC-1 / smoke CASE 2 |
| BlockDiagonalMask + NPU 显式 NotImplementedError（多卡 SP NPU OOS Phase 1 防御性诊断） | AC-2 / smoke CASE 4 |
| FR-06 multitalk 路径无 class-specific bypass（model.py grep 0 行 — trivially 继承） | AC-4（grep 验证 + 间接物理保证 attention.py 内两处调用点都用 dispatch） |
| 5 个主路径文件 added 行 ≤ 80（累积 wan/modules/attention.py 3-12/80） | AC-5（lint gate 自动消费） |
| `wan/distributed/xdit_context_parallel.py` zero-touch（0/80） | AC-5 / Task 4.4 |
| `wan/_npu_adapter/attention_dispatch.py` + `wan/modules/attention.py` 顶层无 `torch_npu` import | AC-6 / Task 4.2 / 4.3 grep 验证（静态）+ smoke CASE 3（runtime） |
| smoke harness **4 case** PASS evidence 在 PR 描述留痕 | AC-8 / Task 5 |

**不属于本 story DoD**（避免越界实施）：
- multitalk happy path 真实 910B 跑通 + `out_multitalk.mp4` 产出（Story 1.5）
- NPU 数值正确性 vs CUDA bit-exact / 数值偏差测量（Story 1.5 隐式验证 + NFR-07 声明性）
- observability 三信号（Story 1.6）
- README-NPU.md 第一版（Story 1.7）
- i2v/t2v/flf2v 模式（Epic 4）
- `app.py --device` flag（Story 3.1）
- `wan/distributed/xdit_context_parallel.py:540` 调用点的 dispatch（Phase 2 / OOS）
- `flash_attention()` / `attention()` 函数的 NPU 适配（Story 1.5 隐式 / 后续 story）
- **TND layout 实现 + `actual_seq_qlen` / `actual_seq_kvlen` cumulative 格式探查**（Phase 2 多卡 SP NPU territory；本 story 仅在 BlockDiagonalMask + NPU 抛 NotImplementedError）
- **`_extract_seqlens` / `_to_cumulative_int32` helper**（与 TND 实现一并 Phase 2 territory；本 story `_npu_dispatch` 仅判定 `attn_bias is not None` 即抛错）
- **`BlockDiagonalMask` 内部 attribute 探查**（`q_seqinfo.seqlen_py` vs `_seqlens_q` 等版本依赖路径；本 story 不消费内部属性）
- **`wan/modules/model.WanModel` 的 NPU 适配**（实测 grep 验证 model.py 不消费 xformers — 见 AC-4；属 Story 1.5 / Epic 4 territory）

### References

- [Source: _gomad-output/planning-artifacts/epics.md#Story-1.4] — AC 文本来源
- [Source: _gomad-output/planning-artifacts/prd.md#FR-05] — `xformers.ops.memory_efficient_attention` → `torch_npu.npu_fusion_attention` 替换 + BNSD/TND layout
- [Source: _gomad-output/planning-artifacts/prd.md#FR-06] — 两套 `WanModel` 共享同一 adapter（无 class-specific bypass）
- [Source: _gomad-output/planning-artifacts/prd.md#FR-18] — 适配代码模块化，cuda runtime 不受影响
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-02] — 5 个主路径文件 ≤ 80 行/文件 hard cap
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-03] — 适配代码可被一组 `git revert` 完全撤回
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-05] — `--device cuda` 路径上游行为不变
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-07] — bit-exact CUDA↔NPU 输出等价**不**作要求（声明性）
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#3-attention-算子替换] — adapter wrapper 在 4 处调用点 + BNSD/TND layout + 两套 WanModel 共享
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#实施顺序约束] — 设备抽象层（C1）必须先于 attention 替换（C3）
- [Source: _gomad-output/implementation-artifacts/1-1-npu-branch-infrastructure.md] — Story 1.1 落地 lint gate / `requirements-npu.txt` / 5 路径白名单 baseline
- [Source: _gomad-output/implementation-artifacts/1-2-device-flag-and-init-abstraction.md] — Story 1.2 落地 `wan/_npu_adapter/{__init__,device}.py` + `--device` flag + `set_device` / `resolve_torch_device` + `assert_single_card_or_fail`
- [Source: _gomad-output/implementation-artifacts/1-3-xfuser-single-card-stub.md] — Story 1.3 落地 `wan/_npu_adapter/xfuser_stub.py` + `if use_usp and not should_short_circuit_xfuser(_world_size):` short-circuit + `xdit_context_parallel.py` 单卡路径不 import 物理保证
- [Source: _gomad-output/implementation-artifacts/deferred-work.md] — Story 1.1 / 1.2 LOW 项审视清单（本 story 不吸收 — Task 6 论证）

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]（Amelia / gm-dev-story）

### Debug Log References

#### Lint gate (Task 4.1) — `python3 tools/check_npu_line_budget.py`

```
wan/modules/attention.py:3
wan/multitalk.py:6
wan/distributed/xdit_context_parallel.py:0
generate_infinitetalk.py:12
app.py:0
EXIT=0
```

**结论**：`wan/modules/attention.py` 实测 added=3（命中 target lower bound +3 / 远低于 hard cap +12 / 远低于 budget 80）；其他 4 个主路径文件累积值与 baseline（post-Story-1.3）一致，本 story 全程 zero-touch。

#### Grep invariants (Task 4.2 / 4.3 / 4.4 / 4.5)

```
$ grep -nE "^import torch_npu|^from torch_npu" wan/modules/attention.py
(0 lines — AC-1 / AC-6 物理保证)

$ grep -nE "^import torch_npu|^from torch_npu" wan/_npu_adapter/attention_dispatch.py
(0 lines — AC-6 物理保证)

$ git diff --numstat fd631497254e065777f2b2d0642de3600d674e24 -- wan/distributed/xdit_context_parallel.py
(empty — zero-touch ✓ 与 Story 1.3 衔接契约一致)

$ grep -nE "dispatch_memory_efficient_attention\(" wan/modules/attention.py
267:        x = dispatch_memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=attn_bias, op=None)
381:        x = dispatch_memory_efficient_attention(q, encoder_k, encoder_v, attn_bias=None, op=None)

$ grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py
(0 lines — AC-1 hard contract ✓)

$ grep -nE "xformers\.ops\.fmha\.attn_bias\.BlockDiagonalMask\.from_seqlens" wan/modules/attention.py
264:            attn_bias = xformers.ops.fmha.attn_bias.BlockDiagonalMask.from_seqlens(visual_seqlen, kv_seq)
(1 line — CUDA 路径仍需要构造此对象传入 dispatch ✓)

$ grep -nE "^import xformers\.ops" wan/modules/attention.py
11:import xformers.ops
(1 line — CUDA 路径仍需要顶层 import ✓)
```

**注**：dispatch 调用点实际行号为 267 + 381（baseline 描述性行号 266 + 380；多了 1 行 import 让下半文件全部 +1 偏移；grep 锚定字面唯一）。

#### Smoke test (Task 5) — `python3 _gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py`

```
========================================================================
[CASE 1] CUDA passthrough → xformers.ops.memory_efficient_attention
------------------------------------------------------------------------
  spy.calls count = 1
  spy.calls[0] args  = (_MockTensor(device.type='cuda', shape=(2, 16, 8, 64)), _MockTensor(device.type='cuda', shape=(2, 16, 8, 64)), _MockTensor(device.type='cuda', shape=(2, 16, 8, 64)))
  spy.calls[0] kwargs = {'attn_bias': None, 'op': None}
  torch_npu-prefixed modules in sys.modules: []
[CASE 1] PASS — CUDA dispatch character-equivalent to upstream (AC-3)

========================================================================
[CASE 2] NPU + attn_bias=None → torch_npu.npu_fusion_attention BNSD
------------------------------------------------------------------------
  spy.calls count = 1
  spy.calls[0] positional args = (_MockTensor(device.type='npu', shape=(2, 16, 8, 64)), _MockTensor(device.type='npu', shape=(2, 16, 8, 64)), _MockTensor(device.type='npu', shape=(2, 16, 8, 64)))
  spy.calls[0] kwargs           = {'head_num': 8, 'input_layout': 'BSND', 'scale': 0.125}
  dispatch return value = <object object at 0x104bc43b0>
[CASE 2] PASS — NPU dispatch routes to npu_fusion_attention BNSD with correct kwargs (AC-1)

========================================================================
[CASE 3] CUDA path → no torch_npu import (AC-6 binding runtime evidence)
------------------------------------------------------------------------
  torch_npu* in sys.modules BEFORE dispatch: []
  torch_npu* in sys.modules AFTER  dispatch: []
[CASE 3] PASS — CUDA dispatch zero NPU import (AC-6)

========================================================================
[CASE 4] NPU + BlockDiagonalMask → NotImplementedError (AC-2)
------------------------------------------------------------------------
  caught NotImplementedError: BlockDiagonalMask attention on NPU is multi-card NPU OOS Phase 1 (got attn_bias of type 'BlockDiagonalMask'); single-card NPU path uses attn_bias=None (BNSD). Multi-card SP NPU support is Phase 2.
  traceback last frame: <FrameSummary file /Users/rockie/Documents/GitHub/xgent/InfiniteTalk/wan/_npu_adapter/attention_dispatch.py, line 99 in _npu_dispatch>
  torch_npu* in sys.modules after NotImplementedError: []
[CASE 4] PASS — BlockDiagonalMask + NPU raises NotImplementedError pre-import (AC-2)

========================================================================
SMOKE TEST RESULT: ALL CASES PASSED (Story 1.4 AC-1/2/3/6/8 surrogate evidence)
========================================================================
EXIT=0
```

### Completion Notes List

- 新建 `wan/_npu_adapter/attention_dispatch.py`（约 110 行包括 docstring）：1 个公共 API `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)` + 1 个私有 helper `_npu_dispatch(q, k, v, attn_bias)`。CUDA 路径在分支函数体内 `import xformers.ops` 后透明放行至上游（NFR-05 字符等价）；NPU 路径 lazy `import torch_npu` 后调 `torch_npu.npu_fusion_attention(q, k, v, head_num=q.shape[-2], input_layout="BSND", scale=1/sqrt(q.shape[-1]))[0]`。BlockDiagonalMask + NPU 组合在 lazy `import torch_npu` 之前抛 `NotImplementedError`，错误消息含 "BlockDiagonalMask" + "Phase 2" + "multi-card NPU OOS Phase 1"（AC-2 防御性诊断）。
- 修改 `wan/modules/attention.py`：顶层新增 1 行 `from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention`；替换 line 266 + line 380 两处 `xformers.ops.memory_efficient_attention(...)` 调用为 `dispatch_memory_efficient_attention(...)` 调用（注：去掉了原调用末尾多余的 trailing comma 让代码风格统一）。**实测 added = 3**（命中 Task 3.4 target lower bound）。
- AC-1 hard contract 验证：`grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py` 返回 0 行 ✓。
- AC-6 verify：`wan/modules/attention.py` + `wan/_npu_adapter/attention_dispatch.py` 顶层均无 `torch_npu` import；smoke CASE 3 binding runtime evidence 证实 CUDA dispatch 后 `sys.modules` 无任何 `torch_npu*` 项。
- 新建 smoke harness `_gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py`，4 个 case 全部 PASS（与 AC-8 case 编号严格对齐；EXIT=0；不计入主路径行预算）。
- `wan/distributed/xdit_context_parallel.py` 严格 zero-touch（与 Story 1.3 衔接契约 + AC-5 hard 约束一致）；其余 4 个主路径文件均 zero-touch。
- 不吸收任何 deferred-work LOW 项；本 story 实施未产生新 LOW 遗留。
- I/O 副作用：`wan/_npu_adapter/__pycache__/`（CPython 自动生成）— 不在主路径白名单 / 不计入预算。

### File List

**新增（不计入主路径预算）**：
- `wan/_npu_adapter/attention_dispatch.py` — FR-05 / FR-06 attention dispatch 主体（1 公共 API + 1 私有 helper）
- `_gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py` — Task 5 烟测 harness（4 case）

**修改（计入 NFR-02 行预算）**：
- `wan/modules/attention.py` — 顶层 +1 import + 2 处调用点替换；累积 added = **3/80**（命中 target lower bound +3）

**修改（仅元数据 / 状态）**：
- `_gomad-output/implementation-artifacts/1-4-attention-adapter.md` — Status: ready-for-dev → in-progress → review；Tasks 全部 [x]；Dev Agent Record / Completion Notes / File List / Change Log 填充
- `_gomad-output/implementation-artifacts/sprint-status.yaml` — `1-4-attention-adapter`: ready-for-dev → in-progress → review

### Change Log

| 日期 | 作者 | 变更 |
|------|------|------|
| 2026-04-26 | Bob (Scrum Master) | 创建 Story 1.4：attention adapter（device-aware xformers / npu_fusion_attention dispatch）。基于 Story 1.2 已落地的 `wan/_npu_adapter/{__init__,device}.py` + Story 1.3 已落地的 `xfuser_stub.py` + 单卡 short-circuit 物理保证，规划本 story 在 `wan/modules/attention.py` 两处 `xformers.ops.memory_efficient_attention` 调用点（grep 锚定 line 266 + line 380）替换为 `wan/_npu_adapter/attention_dispatch.py` 内的 `dispatch_memory_efficient_attention` device-aware helper。Scope 收缩 = 不触碰 `xdit_context_parallel.py:540`（与 Story 1.3 zero-touch 衔接契约一致）/ 不触碰 `flash_attention` 链路（与 FR-05 替换目标正交）/ 不假装验证 NPU 数值正确性（声明 AC-9 — 留 Story 1.5 真实硬件隐式验证）。Status: backlog → ready-for-dev。 |
| 2026-04-26 | Bob (Scrum Master) | **PM 评审修订（Phase 1.5）**——基于 PM John 11 项 findings + Elon 三段裁决 ALL ACCEPT（#2 选 option b）应用本次大刀阔斧的 scope 收缩：(1) FR-06 收缩为 multitalk 路径单一可验证项（`model.WanModel` grep 实测不消费 xformers — finding #1）；(2) **drop TND layout 实现**，BlockDiagonalMask + NPU 改为显式 NotImplementedError 多卡 SP NPU OOS Phase 2（finding #2 option b — Elon 裁决）；(3) `_extract_seqlens` BlockDiagonalMask attribute archaeology 一并 drop（finding #3 因 #2 moot）；(4) `actual_seq_qlen` 格式探查移交 Phase 2（finding #4）；(5) baseline 表加 introduced-by 来源归因（finding #5）；(6) AC-1 加 `xformers.ops.memory_efficient_attention(` 字面 grep 0 行 hard contract（finding #6）；(7) AC-6 引用 smoke CASE 3 作为 binding runtime evidence（finding #7）；(8) 旧 AC-9 改名为 "Out-of-Scope Verification" 非 AC 章节，AC 数量从 8+1 = 9 收缩为严格 8（finding #8）；(9) Dev Notes layout 表精确标注 line 266 attn_bias 在 `enable_sp=True/False` 的精确语义（finding #9）；(10) 加 Task 1.4 `__init__.py` re-export 决策（finding #10）；(11) AC 头加 line-number policy 段落明确 grep-binding contract（finding #11）。Smoke 从 5 case 收缩为 4 case（drop CASE 3 TND；drop CASE 5 torch_npu-unavailable RuntimeError 因为 BlockDiagonalMask NotImplementedError 已涵盖大部分错误归因；新 CASE 4 = NPU + BlockDiagonalMask NotImplementedError）。Status: ready-for-dev → ready-for-dev（保持，仅修订）。 |
| 2026-04-26 | Amelia (Senior Dev) | **实施 Phase 2**——按 Tasks 1-6 顺序落地：(1) 新建 `wan/_npu_adapter/attention_dispatch.py`（1 公共 API `dispatch_memory_efficient_attention` + 1 私有 helper `_npu_dispatch`；CUDA 分支函数体内 `import xformers.ops`，NPU 分支 lazy `import torch_npu`；BlockDiagonalMask + NPU 抛 NotImplementedError（含 "BlockDiagonalMask" + "Phase 2" + "multi-card NPU OOS Phase 1" 字面）；NPU BNSD 分支调 `npu_fusion_attention(q,k,v,head_num=q.shape[-2],input_layout="BSND",scale=1/sqrt(q.shape[-1]))[0]`）；(2) `wan/modules/attention.py` 顶层 +1 import + 2 处调用点替换为 `dispatch_memory_efficient_attention(...)`；(3) 行预算 + grep invariants 全部 PASS（实测 attention.py:3 / hard cap 12 / `xformers.ops.memory_efficient_attention(` 字面 grep 0 行 / 顶层 `torch_npu` import 双文件 0 行 / `xdit_context_parallel.py` zero-touch）；(4) smoke harness 4 case 全部 PASS（CUDA passthrough / NPU+BNSD layout / CUDA-no-torch_npu-pollution / BlockDiagonalMask+NPU NotImplementedError）；(5) Task 6 deferred-work review confirm no items adopted, no new LOW left. Status: in-progress → review. |
