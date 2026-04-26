---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
completedAt: '2026-04-26'
inputDocuments:
  - _gomad-output/planning-artifacts/prd.md
  - _gomad-output/planning-artifacts/architecture-summary.md
---

# InfiniteTalk 昇腾 NPU 迁移 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **InfiniteTalk 昇腾 NPU 迁移**, decomposing the requirements from the PRD and the architecture-summary (architectural decisions extracted from the PRD itself) into implementable stories.

源文档：
- PRD：`_gomad-output/planning-artifacts/prd.md`（764 行，含 22 FR / 12 OOS / 10 NFR）
- Architecture Summary：`_gomad-output/planning-artifacts/architecture-summary.md`（PRD 嵌入式架构决策的提炼，非独立架构文档）
- UX Design：N/A（无 UX 文档；本项目唯一 UI 是上游 Gradio app.py，仅做 NPU 设备开关适配）

## Requirements Inventory

### Functional Requirements

来源：PRD `## Functional Requirements`（共 22 条）。

**Device Abstraction & CLI Surface**

- FR-01: Migration Engineer 通过 `--device {cuda,npu}` flag 在 `generate_infinitetalk.py` 选择计算设备
- FR-02: POC Operator 通过 `--device {cuda,npu}` flag 在 `app.py`（Gradio）选择计算设备
- FR-03: System 替换硬编码的 `torch.cuda.set_device` 为 device-aware 初始化
- FR-04: System 通过扩展 `--task` 枚举或新增 `--mode` flag 支持 4 模式分发（C12 决议）

**Attention & xfuser Adaptation**

- FR-05: System 在 NPU 路径上将 `xformers.ops.memory_efficient_attention` 替换为 `torch_npu.npu_fusion_attention`
- FR-06: System 通过两套 `WanModel` 共享同一 attention adapter（无 class-specific bypass）
- FR-07: System 在 `world_size==1` 时短路 xfuser 序列并行（包括 `xFuserLongContextAttention` import 隔离 + `usp_*` patch 绕开）

**Pipeline Mode Coverage**

- FR-08: Migration Engineer 在单 910B 上跑通 `multitalk` 模式
- FR-09: Migration Engineer 在单 910B 上跑通 `image2video` 模式
- FR-10: Migration Engineer 在单 910B 上跑通 `text2video` 模式
- FR-11: Migration Engineer 在单 910B 上跑通 `first_last_frame2video` 模式

**Gradio NPU Compatibility**

- FR-12: POC Operator 在 910B 上启动 Gradio Demo 并触发一次 `multitalk` 推理

**Observability, Diagnostics & Escalation**

- FR-13: System 输出 unsupported-operator fallback 清单（`TORCH_NPU_DUMP_UNSUPPORTED_OPS=1` 触发）
- FR-14: System 记录每次推理的 NPU HBM 峰值与端到端 wall-clock
- FR-15: System 将 NPU 错误码翻译为含算子名 + 输入 shape 的字符串
- FR-16: Migration Engineer 从任意 blocker 复现产出 vendor-ready escalation packet
- FR-17: Vendor Escalation Coordinator 在 `KNOWN_ISSUES.md` 记录跨 PR 持久的 known-issue 条目

**Adaptation Layer, Distribution & Documentation**

- FR-18: System 保持 NPU 适配代码模块化，`--device cuda` runtime 不受影响
- FR-19: System 提供独立 `requirements-npu.txt`，pin `torch_npu==2.7.1`
- FR-20: Upstream Rebase Maintainer 合入上游 commit 时冲突仅在共享行
- FR-21: System 交付 `README-NPU.md` / `KNOWN_ISSUES.md` / `CHANGELOG-NPU.md` 三份文档并按节奏维护
- FR-22: POC Reviewer 对每个 MVP 模式记录 acceptance 验收 + 可审计 artifact

### NonFunctional Requirements

来源：PRD `## Non-Functional Requirements`（共 10 条）。

**Performance**

- NFR-01: `--device cuda` 时 CUDA 推理路径相对上游基线退化 ≤ 5%（MVP 收尾一次性验证）

**Maintainability**

- NFR-02: NPU 适配代码对每个上游主路径文件的直接编辑行数 ≤ 80 行
- NFR-03: NPU 适配代码可被单组 `git revert` commit 完全撤回
- NFR-04: J4 rebase 演练 wall-clock ≤ 5 工作日

**Compatibility**

- NFR-05: `--device cuda` 时所有上游 CUDA 路径 acceptance 行为不变
- NFR-06: NPU 路径在 Python 3.8 / 3.9 / 3.10 三个版本上均可执行 J1 acceptance 命令
- NFR-07: NPU 路径不要求与 CUDA 路径输出 bit-exact 等价

**Reliability**

- NFR-08: J1 acceptance 命令同输入连续 N≥3 次全部退出码 0
- NFR-09: NPU 算子级阻塞不阻塞 MVP 主线推进（临时绕过解锁）

**Observability**

- NFR-10: 三类观测信号（fallback ops / HBM / wall-clock）以机器可解析格式输出

### Additional Requirements

来源：`architecture-summary.md`（PRD 嵌入式架构决策的提炼）。

**Starter Template**：N/A——fork-and-patch 现有上游 InfiniteTalk 仓库，无项目脚手架工作。Epic 1 Story 1 直接从环境与依赖准备开始。

**架构层面 sequencing constraints（影响 epic 顺序）**：

1. 设备抽象层（C1）必须先于 attention 替换（C3）——C3 的 dispatch 依赖 device flag 已存在
2. xfuser stub（C2）必须先于 4 模式 happy path（FR-08~11）——stub 不到位 multitalk 直接挂
3. CLI 分发扩展（C4）必须先于 i2v/t2v/flf2v 跑通（FR-09~11）——当前 CLI 写死 multitalk
4. Observability 三信号（FR-13/14）应在第一次成功跑通前就启用——否则 Phase 2 escalation 缺数据
5. `README-NPU.md` 第一版必须在 Phase 1a 收尾前落地——J5 acceptance 依赖文档存在
6. CUDA 路径回归验证（NFR-05）在 Phase 1a 收尾时执行一次，是 MVP acceptance 的硬前置

**架构层面 integration points（不交付但要被认知）**：

- 上游 InfiniteTalk 主仓：通过 cherry-pick 同步；适配层独立 wrapper 隔离冲突
- 910B 工程师 vendor escalation：escalation packet → GitHub Issues → `KNOWN_ISSUES.md`
- CANN / 驱动 / 固件：由 Infra/SRE 配置（J1 prerequisite，外部 dependency，不在 epic 范围）

**Phase 切分（直接对应 epic 分组）**：

| 阶段 | 范围 | 收尾门槛 |
|------|------|----------|
| Phase 1a | multitalk + Gradio + 设备抽象 + xfuser 单卡 stub | J1 + J3 acceptance |
| Phase 1b | i2v/t2v/flf2v + CLI 分发扩展 | 4 模式各自 J5 验收 |
| Phase 2（不在本范围） | 多卡 SP + VACE + TeaCache + int8 | — |

### UX Design Requirements

**N/A**——本项目无独立 UX 文档。唯一涉及 UI 的工作是 `app.py`（Gradio Demo）的 NPU device 适配（FR-02 / FR-12），不引入新交互模式 / 新 UI 组件 / 新设计 token。Gradio 的现有 UI 形态完全继承自上游。

### FR Coverage Map

```
FR-01 → Epic 1 (--device flag on generate_infinitetalk.py)
FR-02 → Epic 3 (--device flag on app.py)
FR-03 → Epic 1 (torch.cuda.set_device 替换为 device-aware)
FR-04 → Epic 4 (CLI 任务分发扩展, C12 决议)
FR-05 → Epic 1 (xformers → npu_fusion_attention adapter)
FR-06 → Epic 1 (两套 WanModel 共享同一 adapter)
FR-07 → Epic 1 (xfuser 单卡 stub)
FR-08 → Epic 1 (multitalk 单 910B 跑通)
FR-09 → Epic 4 (image2video 跑通)
FR-10 → Epic 4 (text2video 跑通)
FR-11 → Epic 4 (first_last_frame2video 跑通)
FR-12 → Epic 3 (Gradio multitalk 端到端)
FR-13 → Epic 1 (unsupported-operator fallback 清单)
FR-14 → Epic 1 (HBM 峰值 + wall-clock 记录)
FR-15 → Epic 2 (NPU 错误码翻译层)
FR-16 → Epic 2 (escalation packet 产出)
FR-17 → Epic 2 (KNOWN_ISSUES.md 跟踪)
FR-18 → Epic 1 (NPU 适配代码模块化)
FR-19 → Epic 1 (requirements-npu.txt + torch_npu==2.7.1 pin)
FR-20 → Epic 5 (上游 rebase 演练)
FR-21 → Epic 5 完整 closure（README-NPU 第一版在 Epic 1 落地）
FR-22 → Epic 5 (PR comment + 录屏 + machine-check 留痕)
```

### NFR Coverage Map（bonus, 非工作流强制要求）

```
NFR-01 → Epic 5 (CUDA 路径退化 ≤5%)
NFR-02 → Epic 1 (≤80 行 hard, lint gate Step 1 前置)
NFR-03 → Epic 1 (适配代码可 git revert)
NFR-04 → Epic 5 (rebase 演练 ≤5 工作日)
NFR-05 → Epic 5 (CUDA 路径行为不变)
NFR-06 → Epic 5 (Python 3.8/3.9/3.10 三版本矩阵)
NFR-07 → Epic 5 (bit-exact 不要求, 声明性)
NFR-08 → Epic 5 (J1 连续 N≥3 次可重入)
NFR-09 → Epic 2 (NPU 算子阻塞不挟持主线)
NFR-10 → Epic 1 (三类信号机器可解析)
```

## Epic List

实施顺序：**Epic 1 → Epic 3 → Epic 2 → Epic 4 → Epic 5**

### Epic 1: NPU 启动与单卡 multitalk Walking Skeleton (Phase 1a 核心)

**Epic Goal**: 迁移工程师 (A1) 在 910B 上跑通 multitalk 主路径，产出 `out_multitalk.mp4`，并捕获 observability 三信号 (fallback / HBM / wall-clock)。本 epic 同时落地 NFR-02 ≤80 行 lint gate（前置 in Step 1）+ `README-NPU.md` 第一版 + `requirements-npu.txt`。

**FRs covered**: FR-01, FR-03, FR-05, FR-06, FR-07, FR-08, FR-13, FR-14, FR-18, FR-19  
**NFRs covered**: NFR-02 (hard, lint gate 前置), NFR-03, NFR-10  
**Phase**: 1a 核心  
**内部 sequencing (5 步 ordered checklist)**:
1. `requirements-npu.txt` + 环境基线 + lint gate (FR-19, NFR-02 enforce, NFR-10)
2. 设备抽象层 C1 (FR-01, FR-03, FR-18) — 让 tensor 落到 NPU，不碰 attention
3. xfuser 单卡 stub C2 (FR-07) — 单卡路径绕过 distributed init
4. attention adapter C3 (FR-05, FR-06) — 依赖 C1 的设备 dispatch
5. multitalk happy path + observability (FR-08, FR-13, FR-14) — Epic 1 DoD + README-NPU 第一版落地

**DoD**: J1 acceptance 命令在单 910B 上退出码 0；`out_multitalk.mp4` 存在且 ffprobe 验证通过；fallback / HBM / wall-clock 三信号落盘；`README-NPU.md` 第一版入仓；NFR-02 lint gate 在 CI 生效。

---

### Epic 3: Gradio Demo NPU 化 (Phase 1a 末)

**Epic Goal**: POC operator (A2) 用 Gradio web UI 在 910B 上完成一次 multitalk 推理演示，端到端不崩。

**FRs covered**: FR-02, FR-12  
**NFRs covered**: —  
**Phase**: 1a 末  
**依赖**: Epic 1（共享 multitalk 主路径）  
**为什么排在 Epic 2 之前**: Gradio 跑起来会主动触发更多 NPU 算子边界 case，喂给 Epic 2 的 escalation 工作流更丰富的真实样本；同时早期可演示 demo 表面提升信心。

**DoD**: `python app.py --device npu` 在 910B 上启动；Web UI 加载 HTTP 200，所有 tab 无 console error；触发一次 multitalk 推理产出可播放视频。

---

### Epic 2: Vendor Escalation Workflow + Error Diagnostics (Phase 1a 横切)

**Epic Goal**: 迁移工程师 (A1) 将 NPU 算子级阻塞产出为 vendor-ready escalation packet；vendor coordinator (A4) 持久跟踪 known-issue。Acceptance **必须含 ≥1 个来自 Epic 1 / Epic 3 真实捕获的 case**（dogfood 验证，避免空壳工具）。

**FRs covered**: FR-15, FR-16, FR-17  
**NFRs covered**: NFR-09  
**Phase**: 1a 横切  
**依赖**: Epic 1 + Epic 3（需要真实 NPU 触发的错误样本）

**DoD**: 错误翻译层覆盖 `ACL error <code>` → 算子名 + shape；`escalation-packet/<issue-id>/` 目录约定 + manifest.yaml 标准化；`KNOWN_ISSUES.md` 行格式 + 维护流程入仓；演示 1 个真实 escalation 全流程（packet 产出 → vendor 工单 → known-issue 行追加）。

---

### Epic 4: 三模式扩展 + CLI 分发 (Phase 1b 主体)

**Epic Goal**: 迁移工程师 (A1) 跑通 multitalk 之外的 3 个模式 (`image2video` / `text2video` / `first_last_frame2video`)。CLI 分发机制 (C12 决议) 在本 epic 第一条 story 钉死。

**FRs covered**: FR-04, FR-09, FR-10, FR-11  
**NFRs covered**: —  
**Phase**: 1b 主体  
**依赖**: Epic 1（attention adapter 已就位）

**Story 1 关键决策**: C12 — `--task` 扩枚举（方案 A）vs 新增 `--mode {multitalk,i2v,t2v,flf2v}` 与 `--task` 解耦（方案 B），本 story 钉死并落入 README-NPU。

**DoD**: 4 模式各完成至少一次成功推理（FR-08 + FR-09 + FR-10 + FR-11），各自 J5 acceptance 通过。

---

### Epic 5: MVP 收尾（Upstream Sync Drill + Compatibility 验证 + 文档最终化）

**Epic Goal**: POC reviewer (A5) 完成 4 模式 acceptance 留痕；upstream maintainer (A3) 完成一次上游 cherry-pick rebase 演练 (J4)；CUDA 路径相对上游基线退化 ≤5%；Python 3.8/3.9/3.10 三版本矩阵均可执行 J1；三份文档（README-NPU 最终版 / KNOWN_ISSUES / CHANGELOG-NPU）完整化。

**FRs covered**: FR-20, FR-21（完整 closure；第一版已在 Epic 1 落地）, FR-22  
**NFRs covered**: NFR-01, NFR-04, NFR-05, NFR-06, NFR-07, NFR-08  
**Phase**: 1b 收尾  
**依赖**: Epic 1-4 全部完成（本 epic 验证整体 compatibility + 收尾文档）

**包含的 named stories（Step 3 详细化）**:
- **Cross-platform validation gate**: NFR-01 / NFR-05 / NFR-06 / NFR-07 / NFR-08 集合验证
- **Upstream Sync Drill**: J4 演练，cherry-pick 1 个上游 commit + 解决冲突 + 重跑 J1（NFR-04 ≤5 工作日 wall-clock）
- **Documentation Closure**: README-NPU 最终版（含 Migration Guide 速查表）/ CHANGELOG-NPU 维护节奏建立 / KNOWN_ISSUES.md 形式标准化
- **Acceptance Trail**: 4 个模式各一份 PR comment + 录屏 + `quality-check.txt` 留痕（FR-22）

**DoD**: 4 个 `approved: <mode> passed thinnest bar` PR comment；rebase 演练日志完整；CUDA 退化数据落盘；3 个 Python 版本矩阵全部退出码 0；三份文档完整化。

---

## Epic 1: NPU 启动与单卡 multitalk Walking Skeleton

迁移工程师 (A1) 在 910B 上跑通 multitalk 主路径，产出 `out_multitalk.mp4`，并捕获 observability 三信号 (fallback / HBM / wall-clock)。本 epic 同时落地 NFR-02 ≤80 行 lint gate（Step 1 前置）+ `README-NPU.md` 第一版 + `requirements-npu.txt`。

### Story 1.1: 创建 NPU 分支基础设施（requirements-npu.txt + lint gate + ignore-list）

As a Migration Engineer,
I want a separate `requirements-npu.txt` with `torch_npu==2.7.1` pinned and a CI lint gate enforcing ≤80 lines per upstream main file,
So that upstream rebases stay sustainable from day 1 (NFR-02 hard enforcement).

**Acceptance Criteria:**

**Given** the NPU branch repo
**When** CI runs
**Then** files modified beyond 80 lines from upstream baseline (excluding ignore-list) cause CI to fail

**Given** an attempt to commit to a tracked main-path file
**When** pre-commit hook runs
**Then** it warns/blocks if cumulative additions exceed the threshold

**Given** `requirements-npu.txt`
**When** read
**Then** it contains `torch_npu==2.7.1` (exact pin, not `>=`) plus any NPU-only patch deps
**And** upstream `requirements.txt` does not contain `torch_npu`

**Given** the ignore-list
**When** inspected
**Then** it documents pre-existing legacy CUDA files explicitly with rationale (transparent grandfather list)

### Story 1.2: `--device {cuda,npu}` flag 与设备初始化抽象

As a Migration Engineer,
I want a `--device {cuda,npu}` CLI flag that controls device init,
So that CUDA/NPU paths can be switched at the entry layer without leaking device-awareness into pipeline classes.

**Acceptance Criteria:**

**Given** `python generate_infinitetalk.py --device cuda ...` on a CUDA host
**When** run
**Then** `torch.cuda.set_device(local_rank)` is invoked at the equivalent of `:457/:465` (upstream behavior preserved)

**Given** `--device npu` on a 910B host
**When** run
**Then** `torch.npu.set_device(local_rank)` is invoked instead
**And** no `torch.cuda.*` call is hit on the NPU code path

**Given** `--device` is omitted
**When** run
**Then** it defaults to `cuda` for backward compatibility

**Given** any `WanModel` or pipeline class is loaded
**When** inspected for device-aware code
**Then** it has no direct reference to the `--device` flag string (abstraction confined to entry layer)

### Story 1.3: xfuser 单卡桩化（`world_size==1` 短路）

As a Migration Engineer,
I want xfuser sequence parallelism short-circuited when `world_size==1`,
So that single-card NPU inference doesn't crash on distributed framework imports.

**Acceptance Criteria:**

**Given** `world_size == 1`
**When** `get_sequence_parallel_world_size()` is called
**Then** it returns `1` without contacting xfuser

**Given** `world_size == 1`
**When** any code path would otherwise import or use `xFuserLongContextAttention`
**Then** the call is bypassed via import isolation
**And** a runtime assertion confirms no entry into the call graph

**Given** the `usp_*` patches at `wan/multitalk.py:254-263`
**When** `world_size == 1`
**Then** the patches are bypassed (no-op or skipped via guard)

**Given** `world_size > 1` (future Phase 2)
**When** run
**Then** the original xfuser path is preserved (no regression)

### Story 1.4: Attention adapter (device-aware xformers / npu_fusion_attention dispatch)

As a Migration Engineer,
I want a device-aware attention adapter dispatching to either `xformers.ops.memory_efficient_attention` or `torch_npu.npu_fusion_attention`,
So that the same model code runs on CUDA or NPU without bifurcation.

**Acceptance Criteria:**

**Given** `--device npu`
**When** execution reaches `wan/modules/attention.py:263,266,380` or `wan/distributed/xdit_context_parallel.py:540`
**Then** the call routes to `torch_npu.npu_fusion_attention` with appropriate layout (BNSD or TND)

**Given** variable-length attention input (`BlockDiagonalMask` semantics) on NPU
**When** the adapter routes
**Then** it uses `TND` layout with `actual_seq_qlen / actual_seq_kvlen` derived from block boundaries

**Given** `--device cuda`
**When** the same call sites execute
**Then** `xformers.ops.memory_efficient_attention` is invoked unchanged

**Given** either `WanModel` class (`wan/modules/multitalk_model.WanModel` or `wan/modules/model.WanModel`) invokes the adapter
**When** called
**Then** it shares the same dispatch implementation (no class-specific bypass)

### Story 1.5: Multitalk 单卡 NPU happy path 跑通

As a Migration Engineer,
I want the multitalk pipeline running end-to-end on a single 910B,
So that a walking skeleton proves the full inference pipeline works on NPU.

**Acceptance Criteria:**

**Given** `examples/multitalk_demo.json` and `--device npu`
**When** running the canonical multitalk command (PRD § Code Examples)
**Then** `out_multitalk.mp4` is produced
**And** exit code is 0

**Given** the produced file
**When** running `ffprobe out_multitalk.mp4`
**Then** it validates as a legal MP4 stream

**Given** the same input replayed
**When** run twice consecutively
**Then** both runs complete with exit code 0 (reproducibility floor)

### Story 1.6: 观测信号采集（fallback ops / HBM 峰值 / wall-clock）

As a Migration Engineer,
I want the system to capture three observability signals when configured,
So that I have evidence for vendor escalation negotiation and Phase 2 SP necessity decisions.

**Acceptance Criteria:**

**Given** `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1` in environment
**When** an inference run completes
**Then** a host-fallback operator listing is produced at the default path (or `<run_dir>/unsupported_ops.txt`)

**Given** any successful inference run
**When** finished
**Then** peak NPU HBM and end-to-end wall-clock are extractable from logs or a trace file

**Given** any of the three signal output files
**When** read by `awk` or a Python regex
**Then** the format yields parseable structured data (e.g., `(op_name, count)` tuples for fallback list; numeric values with units for HBM/wall-clock)

### Story 1.7: README-NPU.md 第一版落地

As a Migration Engineer,
I want a first version of `README-NPU.md` documenting the walking skeleton setup,
So that future onboarding (or my future self) can reproduce the Phase 1a state.

**Acceptance Criteria:**

**Given** the NPU branch repo
**When** inspected after Epic 1 completes
**Then** `README-NPU.md` exists at the repo root

**Given** `README-NPU.md`
**When** read
**Then** it documents: hardware/CANN/torch_npu prerequisites, installation steps, the canonical multitalk command, known limitations as of Phase 1a

**Given** the document
**When** reviewed
**Then** it explicitly notes that multi-card SP / VACE / TeaCache / int8 are out-of-scope for Phase 1

---

## Epic 2: Vendor Escalation Workflow + Error Diagnostics

迁移工程师 (A1) 将 NPU 算子级阻塞产出为 vendor-ready escalation packet；vendor coordinator (A4) 持久跟踪 known-issue。Acceptance 必须含 ≥1 个来自 Epic 1 / Epic 3 真实捕获的 case。

### Story 2.1: NPU 错误码翻译层

As a Migration Engineer,
I want NPU error codes translated to operator-name + input-shape locator strings,
So that I can debug NPU failures without spelunking into CANN error tables.

**Acceptance Criteria:**

**Given** an unsupported-operator runtime error on NPU
**When** surfaced to the user
**Then** the error message contains the offending operator name and the input tensor shapes

**Given** an `ACL error <code>` raw string
**When** the translation layer intercepts
**Then** it adds context (op + shape)
**And** preserves the original code for vendor reference

**Given** a non-NPU error (CUDA path or upstream error)
**When** surfaced
**Then** the upstream error path is preserved unchanged

### Story 2.2: Escalation packet 产出

As a Migration Engineer,
I want a vendor-ready escalation packet generated from any NPU operator-level blocker,
So that the 910B engineer can reproduce the issue without hand-holding.

**Acceptance Criteria:**

**Given** an NPU operator-level blocker (one of `OOM` / `op-not-implemented` / `dtype-mismatch` / `numerical-divergence`)
**When** the engineer collects diagnostics
**Then** `escalation-packet/<issue-id>/` is produced containing: input json, `env.txt`, full traceback, `unsupported_ops.txt`, and a `manifest.yaml` naming the blocker type

**Given** the packet
**When** handed to a third party with a comparable 910B host
**Then** the third party can re-run the input and reproduce the same blocker

**Given** the `manifest.yaml`
**When** parsed
**Then** it includes blocker type from the 4-enum, timestamp, and `torch_npu` / CANN versions

### Story 2.3: KNOWN_ISSUES.md 跟踪 + dogfood 验证

As a Vendor Escalation Coordinator,
I want a `KNOWN_ISSUES.md` tracking known NPU blockers across PRs, validated end-to-end with ≥1 real captured case,
So that recurring escalations stay visible and the workflow itself is dogfood-proven.

**Acceptance Criteria:**

**Given** a new escalation
**When** the coordinator updates `KNOWN_ISSUES.md`
**Then** a new line in format `<issue-id> | <op/blocker type> | <workaround> | <vendor ticket URL>` is committed

**Given** a vendor fix delivered
**When** the issue is closed
**Then** the corresponding line is removed from `KNOWN_ISSUES.md`

**Given** a real escalation case captured during Epic 1 / Epic 3 (dogfood requirement)
**When** used as the validation case for this epic
**Then** the full flow runs end-to-end (packet → ticket → KNOWN_ISSUES line → workaround unblocks main line)

**Given** the engineer hits an NPU blocker mid-sprint
**When** triggering escalation
**Then** the MVP main-line work continues via temporary workaround
**And** the blocker does not become a sprint-blocker (NFR-09 enforced)

---

## Epic 3: Gradio Demo NPU 化

POC operator (A2) 用 Gradio web UI 在 910B 上完成一次 multitalk 推理演示，端到端不崩。

### Story 3.1: `app.py` 添加 `--device {cuda,npu}` flag

As a POC Operator,
I want `app.py` to accept a `--device` flag,
So that I can launch Gradio on NPU without modifying the script.

**Acceptance Criteria:**

**Given** `python app.py --device npu` on a 910B host
**When** started
**Then** HTTP 200 returns on home page
**And** all visible tabs mount without browser console JS error

**Given** `python app.py` (no flag)
**When** started
**Then** the default `cuda` path applies for backward compatibility

**Given** `python app.py --device cuda`
**When** started
**Then** upstream Gradio behavior is preserved

### Story 3.2: Gradio multitalk 推理端到端

As a POC Operator,
I want Gradio's multitalk path to invoke the same CLI inference backend,
So that the demo doesn't drift from the validated multitalk path.

**Acceptance Criteria:**

**Given** Gradio loaded with `--device npu`
**When** the user uploads reference image + audio and clicks "Generate"
**Then** the backend invokes the same multitalk inference path as Story 1.5

**Given** the inference completes
**When** the response returns
**Then** the video file URL is delivered to the frontend
**And** the embedded `<video>` element plays it without error

**Given** the inference time
**When** measured
**Then** it does not exceed 1.5× the wall-clock recorded in Story 1.6 (sanity guard against Gradio path overhead)

**Given** the backend logs
**When** inspected post-run
**Then** no `ERROR`-level records exist

---

## Epic 4: 三模式扩展 + CLI 分发

迁移工程师 (A1) 跑通 multitalk 之外的 3 个模式 (`image2video` / `text2video` / `first_last_frame2video`)。CLI 分发机制 (C12 决议) 在本 epic 第一条 story 钉死。

### Story 4.1: C12 决议 — CLI 任务分发机制选定

As a Migration Engineer,
I want a definitive decision between extending `--task` enumeration (Plan A) or adding a new `--mode` flag (Plan B),
So that the CLI surface is consistent across all 4 modes.

**Acceptance Criteria:**

**Given** the C12 decision is made
**When** documented
**Then** `README-NPU.md` contains the chosen flag scheme with a one-paragraph rationale

**Given** the chosen scheme
**When** implemented
**Then** the CLI dispatch logic at `generate_infinitetalk.py:521`-equivalent supports all 4 modes (`infinitetalk-14B / image2video / text2video / first_last_frame2video`)
**And** routes to the corresponding pipeline class (`InfiniteTalkPipeline / WanI2V / WanT2V / WanFLF2V`)

**Given** an unknown mode value
**When** invoked
**Then** the CLI exits non-zero with a clear error listing valid mode names

### Story 4.2: i2v 模式 NPU 跑通

As a Migration Engineer,
I want `image2video` pipeline (`WanI2V`) running end-to-end on a single 910B,
So that the i2v mode is validated under NPU.

**Acceptance Criteria:**

**Given** valid `examples/i2v_demo.json` and the chosen mode flag (Story 4.1)
**When** running with `--device npu`
**Then** `out_i2v.mp4` is produced
**And** `ffprobe`-valid

**Given** the i2v pipeline (`WanI2V`)
**When** invoked
**Then** it uses the same attention adapter as Story 1.4 (no class-specific dispatch bypass)

**Given** the run
**When** complete
**Then** exit code is 0
**And** the J5 machine-check proxy passes (frame variance OR face-detector bbox in ≥50% frames)

### Story 4.3: t2v 模式 NPU 跑通

As a Migration Engineer,
I want `text2video` pipeline (`WanT2V`) running end-to-end on a single 910B,
So that the t2v mode is validated under NPU.

**Acceptance Criteria:**

**Given** valid `examples/t2v_demo.json` and the chosen mode flag
**When** running with `--device npu`
**Then** `out_t2v.mp4` is produced
**And** `ffprobe`-valid

**Given** the t2v pipeline (`WanT2V`)
**When** invoked
**Then** it uses the same attention adapter as Story 1.4

**Given** the run
**When** complete
**Then** exit code is 0
**And** the J5 machine-check proxy passes

### Story 4.4: flf2v 模式 NPU 跑通

As a Migration Engineer,
I want `first_last_frame2video` pipeline (`WanFLF2V`) running end-to-end on a single 910B,
So that the flf2v mode is validated under NPU.

**Acceptance Criteria:**

**Given** valid `examples/flf2v_demo.json` and the chosen mode flag
**When** running with `--device npu`
**Then** `out_flf2v.mp4` is produced
**And** `ffprobe`-valid

**Given** the flf2v pipeline (`WanFLF2V`)
**When** invoked
**Then** it uses the same attention adapter as Story 1.4

**Given** the run
**When** complete
**Then** exit code is 0
**And** the J5 machine-check proxy passes

---

## Epic 5: MVP 收尾（Upstream Sync Drill + Compatibility 验证 + 文档最终化）

POC reviewer (A5) 完成 4 模式 acceptance 留痕；upstream maintainer (A3) 完成一次上游 cherry-pick rebase 演练 (J4)；CUDA 路径相对上游基线退化 ≤5%；Python 3.8/3.9/3.10 三版本矩阵均可执行 J1；三份文档（README-NPU 最终版 / KNOWN_ISSUES / CHANGELOG-NPU）完整化。

### Story 5.1: Cross-platform validation gate（CUDA 退化 + Python 矩阵 + 可重入）

As a Migration Engineer,
I want a single validation pass covering CUDA regression, Python version matrix, reproducibility, and bit-exact non-requirement,
So that compatibility commitments are explicitly verified before MVP closure.

**Acceptance Criteria:**

**Given** the NPU branch + `--device cuda` and a fixed `input_json`
**When** comparing wall-clock to upstream main commit baseline (3 runs each, mean)
**Then** the difference is ≤5% (NFR-01)

**Given** Python 3.8, 3.9, 3.10 venvs each with `pip install -r requirements-npu.txt`
**When** the J1 acceptance command runs in each
**Then** exit code is 0 in all three (NFR-06)

**Given** a single fixed input on NPU
**When** the J1 command runs N≥3 consecutive times
**Then** all runs exit 0 (NFR-08)

**Given** the MVP closure document
**When** reviewed
**Then** it explicitly declares that bit-exact CUDA↔NPU output equivalence is NOT a requirement (NFR-07 declarative固化)

### Story 5.2: Upstream Sync Drill（J4 演练）

As an Upstream Rebase Maintainer,
I want to perform a full upstream cherry-pick + conflict resolution + J1 regression drill,
So that NFR-04 (≤5 working days) is validated and the rebase workflow is proven.

**Acceptance Criteria:**

**Given** the current upstream/main commit
**When** running `git fetch upstream` + cherry-pick + conflict resolve + J1 re-run
**Then** the total elapsed wall-clock is ≤5 working days (NFR-04)

**Given** the cherry-pick conflicts encountered
**When** classified
**Then** they only occur on lines shared between upstream and NPU adaptation contexts (no orthogonal NPU file conflicts)

**Given** the J1 re-run after rebase
**When** complete
**Then** exit code is 0 (no regression introduced by rebase)

**Given** a `CHANGELOG-NPU.md` entry
**When** written for this drill
**Then** it documents the upstream commits cherry-picked
**And** notes any adaptation impacts

### Story 5.3: Documentation Closure（README-NPU 最终版 / KNOWN_ISSUES / CHANGELOG-NPU）

As a Migration Engineer,
I want all three documentation deliverables finalized at MVP closure,
So that future maintainers and POC reviewers can audit the migration without external context.

**Acceptance Criteria:**

**Given** the NPU branch repo at MVP closure
**When** inspected
**Then** `README-NPU.md`, `KNOWN_ISSUES.md`, `CHANGELOG-NPU.md` all exist at repo root

**Given** `README-NPU.md` final version
**When** read
**Then** it includes: install steps, 4 canonical mode commands, Migration Guide CUDA→NPU 速查表, known limitations, references to KNOWN_ISSUES.md and CHANGELOG-NPU.md

**Given** `KNOWN_ISSUES.md`
**When** inspected
**Then** its line format matches Story 2.3 spec
**And** any captured escalations have entries
**And** resolved issues have been removed

**Given** `CHANGELOG-NPU.md`
**When** inspected
**Then** it contains at least one entry from Story 5.2 drill
**And** each entry has date and impact summary

### Story 5.4: Acceptance Trail（4 模式 PR comment + 录屏 + machine-check 留痕）

As a POC Reviewer,
I want each of the 4 MVP modes to have an acceptance record on its PR,
So that MVP closure is fully auditable.

**Acceptance Criteria:**

**Given** a completed inference for any MVP mode (multitalk / i2v / t2v / flf2v)
**When** the reviewer accepts it
**Then** a PR comment is left in the form `approved: <mode> passed thinnest bar`

**Given** the same artifact set
**When** the machine-check proxy runs (frame-variance check OR face-detector bbox in ≥50% frames)
**Then** the result is captured at `<run_dir>/quality-check.txt`

**Given** the PR
**When** reviewed
**Then** a screen recording of the inference run is attached (or linked)
**And** the `out_<mode>.mp4` artifact is attached

**Given** all 4 mode acceptance comments collected
**When** checked
**Then** Phase 1 (1a + 1b) closure gate is met

