---
docType: architecture-summary
sourcePRD: _gomad-output/planning-artifacts/prd.md
createdAt: '2026-04-26'
projectType: brownfield-migration
note: |
  本文件由 PRD 中嵌入的架构决策提炼，非独立架构设计产物。
  目的：为 gm-create-epics-and-stories 工作流提供必需的 architecture 输入。
  权威来源仍为 prd.md 的 FR / NFR 章节，本文件不应与之冲突。
---

# Architecture Summary - InfiniteTalk 昇腾 NPU 迁移

## Scope Note

本项目是**代码迁移**而非新建产品。无 API contracts / data models / 新基础设施需求；架构决策的承载点是**"NPU 适配代码以何种形态融入既有 InfiniteTalk codebase"**。

上游 codebase 即为事实上的架构基线：
- `wan/__init__.py` 暴露 4 个 pipeline 类（`InfiniteTalkPipeline / WanI2V / WanT2V / WanFLF2V`）
- `generate_infinitetalk.py` 是单一 CLI 入口
- `app.py` 是单一 Gradio 入口
- 共享 attention 底座位于 `wan/modules/attention.py` + `wan/distributed/xdit_context_parallel.py`
- 两套 `WanModel`：`wan/modules/multitalk_model.WanModel`（multitalk）+ `wan/modules/model.WanModel`（i2v/t2v/flf2v）

## Starter Template

**N/A**——本项目是 fork-and-patch 现有上游 InfiniteTalk 仓库，不是从模板初始化。所有 Epic 1 Story 1 类的"项目脚手架"工作不适用；Epic 1 Story 1 应直接从"环境与依赖准备"开始。

## 适配层组织原则（Adaptation Layer Principles）

**核心原则**：所有 NPU 适配代码可被单组 `git revert` commit 完全撤回（NFR-03）。具体落地：

### 1. 设备抽象层（FR-01 / FR-02 / FR-03 / FR-18）

- **入口层**：`generate_infinitetalk.py` 与 `app.py` 新增 `--device {cuda,npu}` flag（默认 `cuda` 向后兼容）
- **设备初始化**：替换硬编码 `torch.cuda.set_device(local_rank)`（`generate_infinitetalk.py:457,465`）为 device-aware dispatch
- **扩散原则**：`--device` 参数仅在 CLI 入口层解析；各 pipeline 类 / `WanModel` 内部**不感知** device 字符串

### 2. xfuser 单卡桩化（FR-07）

- **`world_size==1` 时短路所有 xfuser 调用**：
  - `get_sequence_parallel_world_size()` → 直接返回 1
  - `xFuserLongContextAttention` → import 隔离 + 运行期断言确保不进入调用图
  - `wan/multitalk.py:254-263` 的 `usp_*` 函数 patch → 在 SP=1 时绕开
- 通过条件 import 或独立 stub module 实现，**不修改 xfuser 自身**

### 3. Attention 算子替换（FR-05 / FR-06）

- 在 `wan/modules/attention.py:263,266,380` + `wan/distributed/xdit_context_parallel.py:540` 共 4 处调用点引入 device-aware adapter wrapper
- adapter 在 `--device cuda` 时调用 `xformers.ops.memory_efficient_attention`；在 `--device npu` 时调用 `torch_npu.npu_fusion_attention`
- 变长 attention（`BlockDiagonalMask` 形态）→ NPU 走 TND layout + `actual_seq_qlen/actual_seq_kvlen`
- adapter 必须同时被两套 `WanModel` 共享（无 class-specific bypass）

### 4. CLI 任务分发扩展（FR-04）

- `generate_infinitetalk.py:521` 当前写死 `assert args.task == "infinitetalk-14B"`
- 扩展为分发到 4 个 pipeline 类——具体方案在 epic 1 实施前决议（C12）：
  - 方案 A：扩展 `--task` 枚举为 `infinitetalk-14B / image2video / text2video / first_last_frame2video`
  - 方案 B：新增 `--mode {multitalk, i2v, t2v, flf2v}`，与 `--task` 解耦

### 5. 依赖文件分层（FR-19）

- `requirements-npu.txt` 与上游 `requirements.txt` **完全分离**
- `requirements-npu.txt` 必须 pin `torch_npu==2.7.1`（**不接受** `>=`）
- 上游 `requirements.txt` 不包含 `torch_npu`

### 6. Observability 工具链（FR-13 / FR-14 / NFR-10）

- 三类信号必须以**机器可解析格式**输出：
  - `unsupported_ops.txt`：行格式可被 `awk` / Python 解析为 `(op_name, count)` 元组
  - HBM 峰值：从日志或 trace 文件以正则可提取的形式记录
  - wall-clock：同上
- 不强制 JSON / YAML 容器；强制工具链可消费

### 7. 错误信息翻译层（FR-15 / C11）

- 包装 NPU 错误抛出，将 `RuntimeError: ACL error <code>` 翻译为含**算子名 + 输入 shape** 的字符串
- 仅作用于 NPU 路径；CUDA 路径错误抛出不变

### 8. Vendor Escalation 工作流（FR-16 / FR-17）

- `escalation-packet/<issue-id>/` 是约定的目录形态，含 `manifest.yaml` + 5 类工件（input json / env.txt / traceback / unsupported_ops.txt / 输出片段）
- `KNOWN_ISSUES.md` 是仓内文件，行格式约束：`<issue-id> | <op/blocker type> | <workaround> | <vendor ticket URL>`
- 4 类 blocker 枚举：`OOM` / `op-not-implemented` / `dtype-mismatch` / `numerical-divergence`

## Maintainability 量化约束（NFR-02 / NFR-04）

**对每个上游主路径文件，NPU 适配引入的直接编辑行数 ≤ 80 行（hard 约束，lint gate 前置在 Epic 1 Step 1）**：

适用文件：
- `wan/modules/attention.py`
- `wan/multitalk.py`
- `wan/distributed/xdit_context_parallel.py`
- `generate_infinitetalk.py`
- `app.py`

超出此阈值的工作**必须外置为独立 wrapper 文件**（不计入该文件统计）。

**J4 rebase 演练 wall-clock ≤ 5 工作日**——超出意味着上述模块化失效，触发 NFR-02 / NFR-03 audit。

## 阶段切分（Phase 1a / 1b / Phase 2）

| 阶段 | 范围 | 收尾门槛 |
|------|------|----------|
| **Phase 1a** | multitalk + Gradio + 设备抽象 + xfuser 单卡 stub | J1 + J3 acceptance 通过 |
| **Phase 1b** | 补 i2v/t2v/flf2v + CLI 分发扩展 | 4 模式各自 J5 验收通过 |
| **Phase 2 (Growth)** | 多卡 SP + VACE + TeaCache + int8 | 不在本 epic+stories 范围 |

## 文档交付物结构

| 文件 | 维护节奏 | 形态 |
|------|----------|------|
| `README-NPU.md` | 一次性 + 边界变化时更新 | 安装 / 运行 / 已知限制 / Migration Guide 速查表 |
| `KNOWN_ISSUES.md` | 持续（每次 escalation 触发追加；vendor 修复后删行） | 表格行 |
| `CHANGELOG-NPU.md` | 持续（每次 J4 rebase 完成后追加一段） | 条目追加 |

## Out-of-Scope（架构层面）

- ❌ 新基础设施（PyPI / Docker / CI 自动化套件 / Sphinx 站点）
- ❌ 改变上游模型架构（dtype 约定 / 模型权重格式 / 推理流程）
- ❌ 暴露新外部 API（fork-only，无 import-able 库 surface）
- ❌ 引入新数据模型 / 数据库 / 持久化层
- ❌ 多卡 SP 架构设计（Phase 2 单独立项）

## Integration Points

| 集成对象 | 形态 |
|----------|------|
| **上游 InfiniteTalk 主仓** | `git fetch upstream` + cherry-pick；适配层独立 wrapper 隔离冲突（FR-20） |
| **910B 工程师 vendor escalation** | escalation packet → GitHub Issues / 团队工单系统 → 双向同步到 `KNOWN_ISSUES.md` |
| **CANN / 驱动 / 固件** | 由 Infra/SRE 配置为 J1 prerequisite，PRD 不交付（外部 dependency） |

## 实施顺序约束（Sequencing Constraints — 给 epic 排序用）

1. **设备抽象层（C1）必须先于** attention 替换（C3）—— C3 的 dispatch 依赖 device flag 的存在
2. **xfuser stub（C2）必须先于** 4 模式 happy path（FR-08~11）—— stub 不到位 multitalk 直接挂
3. **CLI 分发扩展（C4）必须先于** i2v/t2v/flf2v 跑通（FR-09~11）—— 当前 CLI 写死 multitalk
4. **Observability 三信号（FR-13/14）应在** 第一次成功跑通前就启用 —— 否则 Phase 2 escalation 缺数据
5. **`README-NPU.md` 第一版必须在 Phase 1a 收尾前** 落地 —— J5 acceptance 依赖文档存在
6. **CUDA 路径回归验证（NFR-05）** 在 Phase 1a 收尾时执行一次，是 MVP acceptance 的硬前置
