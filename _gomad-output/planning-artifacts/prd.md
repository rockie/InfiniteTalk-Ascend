---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
completedAt: '2026-04-25'
inputDocuments:
  - README.md
  - requirements.txt
  - https://www.hiascend.com/document/detail/zh/Pytorch/730/ptmoddevg/trainingmigrguide/performance_tuning_0034.html
  - https://ascend.github.io/docs/sources/pytorch/install.html#pytorch
workflowType: 'prd'
targetHardware: 'Ascend Atlas 800 / 910B'
torchNpuVersion: '2.7.1'
documentCounts:
  productBriefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 1
  references: 2
classification:
  projectType: developer_tool
  domain: creative-ai
  complexity: high
  projectContext: brownfield
discoveryNotes:
  scopeDecisions:
    - 多卡 Sequence Parallelism (xfuser 等价路径) 保留为 in-scope；产品环境固定分配 ≥2 张 910B
    - 验收主体：内部 POC（Rockie/团队为第一批用户），非社区合入也非客户 POC
    - 算子级阻塞触发 vendor escalation（联系 910B 工程师做适配），不是 fallback 砍功能
    - 优先尝试无需等待适配的方案，escalation 是 backup 路径
  qualityBar: 主观盲评 - 同 audio+image 输入下 NPU 输出视频需"人眼无明显劣化"（评测样本与盲评 N 待 Step 3 定）
  partyModeConsensus: complexity 从 medium 上修为 high；domain 从 scientific 改为 creative-ai
  knownMigrationHotspots:
    - wan/modules/attention.py:263,266,380（xformers.memory_efficient_attention，含 BlockDiagonalMask varlen）
    - wan/distributed/xdit_context_parallel.py:12,13,539,540（xFuserLongContextAttention + xformers）
    - 11 个文件依赖 xfuser>=0.4.1（主要是 get_sequence_parallel_world_size）
    - optimum-quanto==0.2.6 / decord NPU 兼容性未验证
---

# Product Requirements Document - InfiniteTalk 昇腾 NPU 迁移

**Author:** Rockie
**Date:** 2026-04-25

## Executive Summary

将 **InfiniteTalk**（MeiGen-AI 提出的 audio-driven sparse-frame video dubbing 模型，arXiv:2508.14033）的推理路径从 PyTorch + CUDA 迁移至昇腾 **Atlas 800 / 910B**（`torch_npu 2.7.1` + CANN 2.5.1 + Python 3.8–3.10）。

**目标状态**：在 ≥2 张 910B 上，InfiniteTalk 以与 CUDA 路径**功能等价**的形态完成 audio-driven 视频生成，单次生成可被人眼判定**无明显劣化**。

**验收主体**：内部 POC 团队。**不**做 CUDA↔NPU 性能对标，**不**要求 bit-exact 数值等价。

**核心改造范围**（基于代码静态扫描）：
- `xformers.ops.memory_efficient_attention` 调用 3 处：`wan/modules/attention.py:263,266,380`、`wan/distributed/xdit_context_parallel.py:540`，包含 `BlockDiagonalMask` 变长形态
- `xfuser>=0.4.1` 在 11 个文件中承担 sequence parallelism (`get_sequence_parallel_world_size`) 与 `xFuserLongContextAttention`
- `optimum-quanto==0.2.6`、`decord` 等运行时依赖的 NPU 兼容性需要验证

### What Makes This Special

策略选择：**主动改造，不等 vendor port**。在 xfuser-ascend / MindSpeed 等 GPU 原生分布式推理框架的 NPU 等价物交付到位之前，本项目自行：

- 用 `torch_npu.npu_fusion_attention` (FlashAttentionScore) 替换 attention 主干，覆盖 BNSD 与 TND（变长）布局
- 用 `torch_npu` + HCCL 改写或剥离 `xfuser` 提供的 sequence parallelism 与 long-context attention
- 对 quantization、video decode 等周边链路进行兼容性验证或替换

该策略基于以下事实假设：

1. **FlashAttentionScore 已覆盖单卡 attention 主干** —— 核心算子有官方对等实现
2. **`torch_npu 2.7.1` 的 PyTorch 兼容矩阵足够** —— 无需降级 PyTorch 或换分支
3. **存在 910B 工程师的 vendor escalation 通道** —— 阻塞算子触发 vendor 适配而非范围收缩
4. **整条技术栈开源** —— `xfuser` / `diffusers` / `accelerate` / `optimum-quanto` 全部可 fork-and-patch，无闭源黑盒

附加考量：保留对代码的 ownership，便于跟随上游 InfiniteTalk 主仓的 rebase 演进。

## Project Classification

| 维度 | 值 |
|------|---|
| Project Type | `developer_tool`（Python ML 推理库 + CLI 入口 + Gradio 辅助 UI） |
| Domain | `creative-ai`（生成式多媒体 / audio-driven video generation） |
| Complexity | **`high`** |
| Project Context | `brownfield`（迁移已存在的 InfiniteTalk 代码库，非新建产品） |

**Complexity 判定为 `high` 的依据**：
- `xfuser` 在 11 个文件中承担 SP 与 long-context attention 双重职能，**无公开 NPU 端口**——属于架构级替换而非算子级替换
- `optimum-quanto` 量化路径在 NPU 上未验证
- `diffusers` / `transformers` / `accelerate` 的 NPU 兼容矩阵在 `torch_npu 2.7.1` 仍存在版本敏感的未勘探区域
- 主观盲评质量门槛意味着调试反馈环长（每次生成数分钟级）

## Success Criteria

### User Success

内部 POC 团队（迁移项目的第一批用户）能够：

- 在 1 张 910B 上通过 `generate_infinitetalk.py` CLI 完成 `multitalk`（主路径）+ `image2video` / `text2video` / `first_last_frame2video`（扩展模式）的端到端推理，产出可播放的视频文件
- 启动 `app.py` Gradio Demo 在 910B 上运行，并通过 Web UI 完成至少 `multitalk` 模式的一次推理
- 以最小代码改动遵循上游 InfiniteTalk 主仓的更新（保持 fork-and-patch 工作流，不引入大规模重写）

### Technical Success

- `xformers.ops.memory_efficient_attention` 在 MVP 代码路径（`wan/modules/attention.py`、`wan/distributed/xdit_context_parallel.py`）中**全部**被 `torch_npu.npu_fusion_attention` 替换或封装层替换；CUDA-only 调用在 MVP 路径上为零
- `xfuser` 单卡路径桩化：`world_size == 1` 时 `xFuserLongContextAttention` **不进入调用图**（通过 import 隔离 + 运行期断言保证），`get_sequence_parallel_world_size` 在单卡场景返回 1；`wan/multitalk.py:254-263` 引用的 `usp_*` 函数在 SP=1 时绕开
- 设备抽象层：CLI 新增 `--device {cuda,npu}` flag（或等价机制），消除 `generate_infinitetalk.py:457,465` 对 `torch.cuda.set_device` 的硬编码；`wan/multitalk.py` 内部 cuda 调用同步抽象化
- CLI 任务分发扩展：`generate_infinitetalk.py:521` 现仅 `assert args.task == "infinitetalk-14B"`，需扩展分发逻辑或新增独立入口以驱动 `WanI2V` / `WanT2V` / `WanFLF2V`（暴露于 `wan/__init__.py:2-6`）
- 两套 `WanModel` 的 attention 调用点均完成 audit：`wan/modules/multitalk_model.WanModel`（multitalk 主路径）+ `wan/modules/model.WanModel`（i2v/t2v/flf2v 主路径）
- 代码在 `torch_npu 2.7.1` + CANN 2.5.1 + Python 3.8–3.10 + Atlas 800 / 910B 环境中导入并执行无 ImportError、无 device-mismatch RuntimeError
- `requirements.txt` 增加 `torch_npu==2.7.1` 引导（或独立 `requirements-npu.txt`），并显式声明在 NPU 路径下被 stub 的依赖（如 `xformers`、`xfuser`）

### Measurable Outcomes

| 指标 | 验收方法 |
|------|---------|
| **MVP Acceptance Command** | 在单张 910B 上执行（具体 flag 以最终设备抽象方案为准）：`ASCEND_RT_VISIBLE_DEVICES=0 LOCAL_RANK=0 python generate_infinitetalk.py --task infinitetalk-14B --input_json <fixed_demo.json> --device npu`，命令返回 0 |
| **MVP 输出可观测信号** | `out.mp4` 文件存在、文件大小 > 0、可被 `ffprobe` 识别为合法 MP4 视频流 |
| **质量门槛（最薄档，testability 补完版）** | 单一固定输入 → 同时通过 **VLC + Chrome `<video>` 标签**播放无报错（"playable"）→ Rockie 本人主观判定"未崩、画面非纯噪声"=过；机器兜底（任选其一）：(a) `ffprobe` 抽帧后逐帧像素方差检查不命中纯噪声分布；(b) 任意现成人脸检测器在 ≥50% 抽样帧中检出 bbox。评审留痕：录屏 + reviewer 在对应 GitHub PR comment 中签字 |
| **四模式覆盖（独立勾选）** | `multitalk` / `image2video` / `text2video` / `first_last_frame2video` **各自独立**完成至少一次成功推理，每个模式独立判定通过/失败，不作为原子目标 |
| **Gradio 可达性** | `app.py` 在 910B 上启动后，Web UI 可加载首页（HTTP 200）并触发一次 `multitalk` 推理生成视频 |
| **算子级 fallback 清单** | MVP 完成态需在文档中落盘一次完整跑通 trace：使用 `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1`（或等价开关）记录的 host-fallback 算子列表 + 数量。这是 Phase 2 vendor escalation 的依据，不抓后面捡不回来 |
| **HBM 峰值与 OOM 边界** | 单次 `multitalk` 推理在 910B 64GB HBM 上的峰值显存占用，以及触发 OOM 的最大输入秒数 / 帧数。这是 Phase 2 SP 必要性的事实依据 |
| **端到端 wall-clock** | 一条 happy-path 推理的端到端耗时（单点数字，非性能对标）。用作 POC 验收节奏与开发者迭代生产力的护栏，不作为优化目标 |

## Product Scope

### MVP - Minimum Viable Product

**硬件配置**：单张 910B（Atlas 800 子单元）

**入口**：
- `generate_infinitetalk.py` CLI（含新增 `--device` flag 与扩展任务分发）
- `app.py` Gradio Demo

**功能模式**：
- `multitalk`（主路径）
- `image2video`
- `text2video`
- `first_last_frame2video`

**核心改造**：
- attention 算子：`torch_npu.npu_fusion_attention`（BNSD + TND 变长），覆盖 `wan/modules/attention.py:263,266,380` 与 `wan/distributed/xdit_context_parallel.py:540` 共 4 处调用点
- 两套 `WanModel` 的 attention 调用点 audit：`wan/modules/multitalk_model.WanModel` + `wan/modules/model.WanModel`
- CLI 设备抽象：`--device {cuda,npu}` flag + `torch.cuda.*` → `torch_npu` 适配层
- CLI 任务分发扩展：解锁 `WanI2V` / `WanT2V` / `WanFLF2V` 三个 pipeline 的可达性
- `xfuser` 单卡路径桩化：`world_size==1` 时 `xFuserLongContextAttention` 不进入调用图（import 隔离 + 运行期断言），SP world size→1，`wan/multitalk.py:254-263` 的 `usp_*` patch 路径在 SP=1 时绕开
- 周边依赖（`optimum-quanto`、`decord`、`accelerate`、`diffusers`、`transformers`）在 NPU 单卡路径上的 import-and-run 兼容性验证（仅验证不崩，不调优）

**Phase 1 内部里程碑切分**（便于进度追踪与 demo）：
- **Phase 1a — 内部可演示门槛**：`multitalk` 单模式跑通 + Gradio 起得来 + 设备抽象 + xfuser 单卡 stub
- **Phase 1b — Phase 1 收尾**：补 `image2video` / `text2video` / `first_last_frame2video` 三模式（含 CLI 分发扩展）

**显式 Out-of-Scope（MVP 阶段）**：
- ❌ 多卡 sequence parallelism（含 xfuser 等价物自研 / 集成）
- ❌ `vace` 模式
- ❌ `TeaCache` 加速
- ❌ `int8` 量化（`optimum-quanto` NPU 路径调通）
- ❌ CUDA ↔ NPU 性能对标
- ❌ Bit-exact 数值等价校验
- ❌ ComfyUI 集成（上游 README 明确 ComfyUI 走独立分支）

### Growth Features (Post-MVP)

按优先级降序，每条单独立 story / sprint：

1. **Multi-Card Sequence Parallelism on NPU**（用户硬约束"产品环境 ≥2 卡"的兑现）
   - 评估并选择路径：(a) 自研 HCCL + Ulysses 等价物；(b) 集成 MindSpeed / xfuser-ascend 若届时已发布
   - 替换 `wan/distributed/xdit_context_parallel.py` 中的 `xFuserLongContextAttention`
   - 使能 `multitalk` 在 ≥2 卡上的长视频生成
2. **VACE 模式**：迁移 `wan/vace.py` 路径
3. **TeaCache 加速**：在 NPU 路径上启用并验证
4. **int8 量化**：`optimum-quanto` NPU 兼容性调通或替换为昇腾原生量化路径

### Vision (Future)

- **完整 CUDA 功能等价**：所有 README "Key Features" 与 "Todo List" 中已实现项均在 NPU 路径上可用
- **可持续 rebase 工作流**：上游 InfiniteTalk 主仓 commit 可通过 fork 自动化或半自动化合入 NPU 分支
- **质量门槛升级**：从最薄档（单输入主观判定 + 机器兜底）演进至中等档（N=5 prompts × M=2 评审，参考 README 官方 demo 集）+ 引入 LSE-D / LSE-C 唇形同步量化指标
- **可选公开发布**：作为昇腾生态可参考的 audio-driven video 生成模型样板（依赖 vendor escalation 反馈与团队意愿，不作硬承诺）

### Risks

| 风险 | 缓解 |
|------|------|
| attention 算子替换（`xformers`→`npu_fusion_attention`）可能从"换函数名"演变为"重写注意力前向 + 调 shape + 兼容 mask + 排查精度" | 进 sprint 前 2 小时 spike：拿单个 call site 写最小 repro，跑通再估点；spike 失败则拆为"调通 1 site"+"推广 2 site"两条 story |
| `xfuser` 桩化在 11 个文件中存在"看似 no-op 实际改了执行路径"的隐患 | Stub 后跑一次 CUDA 基线 diff（同输入下 CUDA-with-stub vs CUDA-without-stub）防回归 |
| `image2video` / `text2video` / `first_last_frame2video` 当前 CLI 不可达（`generate_infinitetalk.py:521` 写死 multitalk） | MVP 显式包含 CLI 分发扩展工作；估点时按 0.5–1 PD/模式叠加 |

## User Journeys

### J1 — Migration Engineer 跑通 Phase 1a 单卡 multitalk happy path

**Actor**: Migration Engineer (A1) · **Role**: implementer-validator · **Goal**: multitalk 在单卡 910B 跑通且产出可观测 artifact

**Performs**:
1. 在 910B 主机上 clone NPU 适配分支
2. 安装 `torch_npu 2.7.1` + CANN 2.5.1 + Python 3.8–3.10 + `requirements-npu.txt` 增量依赖
3. 设置 `ASCEND_RT_VISIBLE_DEVICES=0` + `LOCAL_RANK=0` + `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1`
4. 执行 MVP Acceptance Command：`python generate_infinitetalk.py --task infinitetalk-14B --device npu --input_json <fixed_demo.json>` 加 CLI 现有的输出路径机制（`--save_file` 等价 flag，最终命名以 C12 决议为准）

**Responds**:
1. CLI 通过 `--device npu` 进入 NPU 设备分支，调用 `torch.npu.set_device(local_rank)`
2. 模型权重加载到 NPU
3. xfuser 单卡 stub 生效（`world_size==1`，`xFuserLongContextAttention` 不进入调用图）
4. attention 调用走 `torch_npu.npu_fusion_attention`（BNSD / TND）
5. 推理完成，进程返回退出码 `0`

**Outcome**（具体 artifact 路径与文件）：
1. `out.mp4` 文件落于命令指定的输出路径，`ffprobe out.mp4` 识别为合法 MP4
2. stdout / stderr 中包含结构化进度日志（无 `ERROR` 级别记录）
3. host-fallback 算子清单落于 `TORCH_NPU_DUMP_UNSUPPORTED_OPS` 默认路径（或重定向至 `<run_dir>/unsupported_ops.txt`）
4. 端到端 wall-clock 时长与 NPU HBM 峰值占用从日志或独立 trace 文件可提取

**Reveals capabilities**: C1 设备抽象、C2 xfuser 单卡桩化、C3 attention 替换、C5 observability 三信号、C9 依赖分层（间接）、C11 错误可读性（间接）、C12 CLI flag（间接）。

---

### J2a — Migration Engineer 遇到 NPU 算子级阻塞，产出 escalation packet

**Actor**: Migration Engineer (A1) · **Role**: implementer-validator · **Goal**: 阻塞被识别 + 产出 vendor-ready 的可复现 bug report 工件

**Performs**:
1. 跑 acceptance command 时进程抛错或 host-fallback 数量超出预设阈值，错误类型属于以下枚举之一：
   - `OOM`（NPU HBM 耗尽）
   - `op-not-implemented`（aten/torch_npu 算子未支持）
   - `dtype-mismatch`（fp16/bf16 不被某算子接受）
   - `numerical-divergence`（输出包含 `NaN` / `Inf` 或与已知合理输出统计偏离过远）
2. 收集最小 repro 包：`<fixed_demo.json>` 输入、`env.txt`（环境变量与 CANN/torch_npu 版本快照）、完整 traceback、`unsupported_ops.txt`、（如有）输出 `out.mp4` 的差异片段

**Responds**:
1. CLI 抛出 NPU 错误并被 C11 错误可读性层翻译为带定位线索的字符串（如 `ACL error 507015` → 显式映射到算子名 + 输入 shape）
2. 退出码非零
3. `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1` 已开启 → 自动落盘算子级 fallback 清单

**Outcome**:
1. 产出一份 `escalation-packet/<issue-id>/` 目录，含上述 5 类工件，可被任意第三方原样复现
2. 阻塞 blocker 类型在该目录的 `manifest.yaml` 中显式标注（属于上述 4 类枚举之一）
3. 不阻塞 Phase 1a 主线推进——A1 可暂时绕过（dtype 切换 / mask 形态调整 / 算子降级到 CPU 路径）继续推进

**Reveals capabilities**: C5 observability、C6 escalation 工作流、C11 错误可读性。

---

### J2b — Vendor Escalation Coordinator 将 packet 转为 vendor 工单与 known-issue 跟踪

**Actor**: Vendor Escalation Coordinator (A4) · **Role**: escalation-handler · **Goal**: escalation packet 被路由到 910B 工程师，且本地有 known-issue 跟踪不被遗忘

**Performs**:
1. 收到 J2a 产出的 `escalation-packet/<issue-id>/`
2. 在 GitHub Issues（或团队工单系统）创建 escalation issue，body 链接到 packet manifest，labels 含 `npu-blocker` + blocker 类型（4 类枚举之一）
3. 在 NPU 适配分支 `KNOWN_ISSUES.md` 追加一行：`<issue-id> | <算子名 / blocker 类型> | <临时绕过路径> | <vendor 工单 URL>`

**Responds**:
1. Issue 进入跟踪系统，与 NPU 工程师 owner 绑定
2. `KNOWN_ISSUES.md` 与代码同仓提交，可在 PR review 中被审计

**Outcome**:
1. 阻塞算子有明确 owner（910B 工程师）+ vendor 工单 URL
2. `KNOWN_ISSUES.md` 是 PR 必读项之一，避免阻塞被遗忘
3. Vendor 适配回填后，可通过 issue 关闭 + `KNOWN_ISSUES.md` 删行回收技术债

**Reveals capabilities**: C6 escalation 工作流。

---

### J3 — POC Operator 启 Gradio Demo 给 stakeholder 演示

**Actor**: POC Operator (A2) · **Role**: demo-presenter · **Goal**: 在 910B 上对 stakeholder 演示一次 multitalk 推理（stakeholder 是 context，不是 actor）

**Performs**:
1. SSH 到 910B 主机，启动 `python app.py --device npu`
2. 浏览器打开 Gradio URL
3. 在 UI 上传 reference image + audio
4. 点击 "Generate"

**Responds**:
1. Gradio 加载首页（HTTP 200），所有可见 tab 全部成功挂载（无 JS console error）
2. submit 后端调用同 `multitalk` MVP 推理路径（共享底座）
3. 后端日志无 `ERROR` 级别记录
4. 推理完成后 Gradio 返回视频 URL，浏览器内嵌 `<video>` 标签自动播放

**Outcome**:
1. 视频文件存在且可被 VLC + Chrome 双客户端播放
2. 单次推理在不超过 J1 wall-clock 数字的 1.5 倍范围内返回（防 Gradio 路径意外引入开销）
3. 后端日志可下载用于事后审计

**Reveals capabilities**: C1 设备抽象、C2 xfuser 单卡桩化、C3 attention 替换、C7 Gradio NPU 兼容、C11 错误可读性。

---

### J4 — Upstream Rebase Maintainer 同步上游 commit

**Actor**: Upstream Rebase Maintainer (A3) · **Role**: fork-keeper · **Goal**: 将上游 InfiniteTalk 主仓新 commit 合入 NPU 分支

**Performs**:
1. `git fetch upstream` + 检视 diff（动作粒度：cherry-pick patch set，按 commit 颗粒度合入；非 `merge upstream/main`）
2. 在 NPU 分支上 cherry-pick 对应 commit
3. 解决冲突（重点在 `wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` 等已 NPU 化的文件）
4. 重跑 J1 路径验证回归

**Responds**:
1. NPU 适配层（device 抽象 / xfuser stub / attention wrapper）以独立 wrapper 形态隔离，冲突仅在共享行
2. `requirements-npu.txt` 独立维护，避免与上游 `requirements.txt` 主分支竞争
3. J1 acceptance 回归通过，退出码 `0`

**Outcome**:
1. NPU 分支与上游同步至所选 commit 范围
2. 一次 rebase 演练在 ≤1 周内完成
3. 无需大规模重写或推翻已有 NPU 适配代码

**Reveals capabilities**: C1 设备抽象（间接，影响合入难度）、C8 适配层模块化、C9 依赖分层。

> 📌 **对应 NFR**：本 journey 由 NFR-02（每文件适配行数 ≤ 80）、NFR-03（适配代码可被 git revert 完全撤回）、NFR-04（rebase 演练 ≤ 5 工作日）形式化。

---

### J5 — POC Reviewer 主观验收 + PR comment 留痕

**Actor**: POC Reviewer (A5 = Rockie，Step 3 钉死的 single reviewer) · **Role**: acceptance-judge · **Goal**: 4 模式各完成一次 MVP 验收并留痕

**Performs**:
1. 在 GitHub PR 中查看 migration engineer 提交的 4 个录屏 + 4 个 `out.mp4` artifact（4 模式各一）
2. 每个 `out.mp4` 在 VLC + Chrome 各播放一次
3. 对每个 `out.mp4` 跑机检 proxy（任选其一作为 "not pure noise" 的 gate）：
   - (a) `ffprobe` 抽帧后逐帧像素方差落于 `[var_min, var_max]` 区间（避免纯噪声 / 全黑 / 全白）
   - (b) 任意现成人脸检测器在 ≥50% 抽样帧中检出 bbox
4. 在对应 PR comment 中签字 `approved: <mode> passed thinnest bar`

**Responds**:
1. PR diff + 录屏 artifact 可下载
2. 每个 `out.mp4` 在两种播放器均无报错（"playable" 客观判定）
3. 机检 proxy 的判定结果落于 `<run_dir>/quality-check.txt`（"not pure noise" 客观判定）
4. PR comment 与 stepsCompleted（或对应 milestone）关联

**Outcome**:
1. 4 个 mode 各一条 approved comment + 一份 quality-check.txt
2. Phase 1（含 1a + 1b）收尾门槛达到
3. 验收过程完全可被审计（comment + 录屏 + artifact + quality-check 留存）

> 📌 **澄清"主观 vs 客观"**：本 journey 中**唯一主观的判定**是 reviewer "未崩、画面非纯噪声"的整体观感盖章；所有客观信号（playable、不命中纯噪声分布、人脸检出率）都是机检 proxy。Coding agent 应将上述客观信号作为可生成测试断言的位置，主观盖章仅作为 PR comment 留痕。

**Reveals capabilities**: C4 CLI 任务分发扩展（4 模式可达性）、C10 验收留痕、C12 CLI flag 一致性。

### Journey Requirements Summary（Capability × Journey 矩阵）

下表汇总 12 个能力区域与 6 条 journey 的覆盖关系。● = primary 来源（FR 主要锚点），○ = secondary 来源（FR 辅助锚点）。Step 9 Functional Requirements 据此推导。

| Capability | J1 | J2a | J2b | J3 | J4 | J5 |
|------------|:--:|:---:|:---:|:--:|:--:|:--:|
| **C1** 设备抽象层（`--device {cuda,npu}` flag + `torch.cuda.*` 适配） | ● | ○ |  | ● | ○ |  |
| **C2** xfuser 单卡桩化（`world_size==1` 安全短路 + import 隔离 + 运行期断言） | ● |  |  | ● | ○ |  |
| **C3** Attention 算子替换（`npu_fusion_attention`，BNSD + TND） | ● | ○ |  | ● | ○ |  |
| **C4** CLI 任务分发扩展（4 模式各自可达） |  |  |  |  |  | ● |
| **C5** Observability（算子 fallback 清单 / HBM 峰值 / wall-clock） | ● | ● |  |  |  |  |
| **C6** Escalation 工作流（packet → vendor ticket → KNOWN_ISSUES.md） |  | ● | ● |  |  |  |
| **C7** Gradio NPU 兼容（`app.py --device npu`） |  |  |  | ● |  |  |
| **C8** 适配层模块化（独立 wrapper / monkey-patch 不与上游主路径耦合） |  |  |  |  | ● |  |
| **C9** 依赖文件分层（`requirements-npu.txt` 独立） | ○ |  |  |  | ● |  |
| **C10** 验收留痕（录屏 + 双播放器 + 机检 proxy + PR comment） |  |  |  |  |  | ● |
| **C11** 错误信息可读性（NPU 错误码 → 算子 + shape 翻译层） | ○ | ● |  | ○ |  |  |
| **C12** CLI flag 一致性（`--task` 扩枚举 vs 新增 `--mode` 决议） | ○ |  |  |  |  | ● |

**矩阵观察**：
- 每个 capability 至少有一个 primary 来源——无能力孤悬
- 每条 journey 至少 reveals 1 个 primary capability——无 ceremony journey
- C2 / C7 仅有 J1+J3 来源，且 J3 是 J1 的 superset（共享底座）——这是设计预期，**不是覆盖空洞**
- C8 仅 J4 来源——这是真正的"架构原则"型 capability，Step 10 NFR 会回填

## Domain-Specific Requirements

### 适用范围声明

本 PRD 的范围是 **InfiniteTalk 推理路径从 CUDA 到 Ascend NPU 910B 的硬件平台迁移**。本工作不引入新的生成能力，不改变模型的输入/输出语义，不放大或收紧上游 InfiniteTalk 仓库的内容安全或合规姿态。验收主体为内部 POC 团队，不面向终端用户公开发布。

### 继承自上游

以下 `creative-ai` 域的常规关切均**继承自上游 InfiniteTalk 主仓**，本 migration 不修改：

- 肖像 / 声音 consent 模型
- Deepfake 检测 / 输出 provenance
- 内容安全过滤（输入输出审核）
- 训练数据与生成物的版权归属

### Deferred Concerns（仅在 Vision 阶段公开发布时才需要重新评估）

| 关切 | 仅当 Vision § "可选公开发布" 兑现时需评估 |
|------|--------------------------------------|
| 部署侧水印 / C2PA 嵌入 | 是 |
| 用户上传素材的存储 / 删除策略 | 是 |
| NSFW / 滥用过滤的运行时实现 | 是 |
| 跨境数据合规（如对外提供服务） | 是 |

> 📌 **说明**：本节为占位声明，不构成本 MVP / Growth 阶段的工程任务。Phase 2（多卡 SP）与 Vision（公开发布）若被激活，需重新打开本节并详化。

### 工程性 High Complexity 的真实承载

PRD Step 2 中 `complexity=high` 的判定**不是来自合规要求**，而是来自以下工程性因素，已在 Step 3 / 4 的 Risks 与 Capabilities 章节中详化：

- `xfuser` 在 11 个文件中承担 SP 与 long-context attention 双重职能（无公开 NPU 端口）
- `optimum-quanto` 量化路径在 NPU 上未验证
- `diffusers` / `transformers` / `accelerate` 的 NPU 兼容矩阵未勘探
- 主观盲评质量门槛导致调试反馈环长

本步骤不重复，仅指明承载位置。

## Developer-Tool Specific Requirements

### Project-Type Overview

InfiniteTalk-NPU 作为 `developer_tool` 子类 = **可运行的 Python 研究代码仓库**，不是可嵌入第三方项目的库 / SDK / 包。分发模式：**fork-only**（GitHub 分支），用户通过 `git clone` 获取并在本地按文档配置环境运行。

显式不适用：
- IDE 集成（项目不暴露被 `import` 的 API surface 给外部 Python 项目）
- `visual_design` / `store_compliance`（CSV `skip_sections`）

### Technical Architecture Considerations

- 适配层与上游主路径**模块化隔离**——独立 wrapper / 条件 import，不直接侵入 `wan/modules/attention.py` 等共享文件超过受限行数（具体上限在 Step 10 NFR 落定）
- `--device` 参数仅在 CLI 入口层解析，各 pipeline 类内部不感知 device 字符串（避免 device-aware 代码扩散到模型层）
- `requirements-npu.txt` 与上游 `requirements.txt` 分离维护，避免与上游分支演进冲突

### Language Matrix

| 维度 | 约束 |
|------|------|
| 语言 | Python（唯一） |
| Python 版本 | **3.8 / 3.9 / 3.10**（由 torch_npu 2.7.1 安装文档约束） |
| OS 架构 | x86-64 / aarch64（torch_npu 2.7.1 双架构支持；Atlas 800 通常为 aarch64） |
| 设备后端 | CUDA 路径（保留，向后兼容）+ NPU 路径（本 PRD 引入），由 `--device` flag 切换 |

### Installation Methods

**Fork-only 分发模式**步骤：

1. `git clone <NPU 分支 URL>`
2. 主机就绪：Atlas 800 / 910B + CANN 2.5.1 + 驱动/固件（由 Infra/SRE 配置，不在 PRD 范围；J1 prerequisite）
3. 创建 Python 3.8–3.10 venv / conda env
4. `pip install -r requirements.txt`（上游主依赖）
5. `pip install -r requirements-npu.txt`（NPU 增量：`torch_npu==2.7.1` + NPU 路径独占的 patch 包）
6. （首次跑通时）设置 `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1` 收集 fallback 清单（J1 Outcome）

**显式 Out-of-Scope（分发侧）**：
- ❌ PyPI 公开发布
- ❌ 内部私有 PyPI / mirror
- ❌ Docker 镜像（Phase 2 后再评估）

### API Surface

**Public Python API**（暴露给 git-clone 用户，本 migration 不修改其接口签名）：

| Class | 文件 | 用途 |
|-------|------|------|
| `InfiniteTalkPipeline` | `wan/multitalk.py` | multitalk 主路径 |
| `WanI2V` | `wan/image2video.py` | image-to-video |
| `WanT2V` | `wan/text2video.py` | text-to-video |
| `WanFLF2V` | `wan/first_last_frame2video.py` | first-last-frame-to-video |

**Public CLI Surface**：

`generate_infinitetalk.py`：
- **现有 flags（继承上游，不修改）**：`--task / --size / --ckpt_dir / --offload_model / --t5_cpu / --mode / --audio_mode / --input_json / --save_file / ...`
- **本 PRD 新增**：`--device {cuda,npu}`（默认 `cuda` 保持向后兼容）
- **本 PRD 新增枚举 / flag**（C12 决议待 Step 9 钉死）：
  - 方案 A：扩展 `--task` 枚举为 `infinitetalk-14B / image2video / text2video / first_last_frame2video`
  - 方案 B：新增 `--mode {multitalk, i2v, t2v, flf2v}`，与 `--task` 解耦

`app.py`（Gradio）：
- **本 PRD 新增**：`--device {cuda,npu}` flag

**API 兼容性原则**：CUDA 路径的所有现有调用契约保持不变；NPU 路径通过显式 `--device npu` opt-in。

### Code Examples（Canonical 用法）

每个 MVP 模式的 acceptance command 即为 canonical example，由 J5 PR comment + 录屏 artifact 背书。

```bash
# 模式 1: multitalk（主路径）
ASCEND_RT_VISIBLE_DEVICES=0 LOCAL_RANK=0 \
  python generate_infinitetalk.py \
    --task infinitetalk-14B \
    --device npu \
    --input_json examples/multitalk_demo.json \
    --save_file out_multitalk.mp4

# 模式 2 / 3 / 4: image2video / text2video / first_last_frame2video
# 同上替换 --task（具体 flag 命名以 C12 决议为准）

# Gradio
python app.py --device npu
# 浏览器打开 Gradio 提示的 URL
```

**Canonical examples 入仓位置**：
- 输入 JSON 模板落于 `examples/`（已有目录，扩展即可）
- 命令脚本可作为 `scripts/run_npu_<mode>.sh` 入仓（可选）

### Migration Guide（CUDA 分支 → NPU 分支，落于 `README-NPU.md`）

**目标读者**：已经在 CUDA 路径上跑 InfiniteTalk 的内部用户，需要切换到 NPU。

**关键差异速查表**：

| 维度 | CUDA 路径 | NPU 路径 |
|------|----------|----------|
| 设备启动 | `CUDA_VISIBLE_DEVICES=0` | `ASCEND_RT_VISIBLE_DEVICES=0` |
| Python 版本 | 上游约束 | **必须 3.8–3.10**（torch_npu 2.7.1 约束） |
| Attention 后端 | `xformers` | `torch_npu.npu_fusion_attention`（隐藏在 wrapper 后） |
| 多卡 SP | `xfuser` USP / Ulysses | **MVP 不支持**（Phase 2 兑现） |
| `int8` 量化 | `optimum-quanto` | **MVP 不支持**（Phase 2 兑现） |
| VACE / TeaCache | 支持 | **MVP 不支持**（Growth 阶段） |
| 错误信息形态 | `RuntimeError: CUDA error: ...` | `RuntimeError: ACL error ...`（C11 翻译层包装为算子名 + shape） |

### Documentation Deliverables

本 PRD 的 MVP 收尾必须产出以下三份文档：

| 文件 | 内容 | 维护节奏 |
|------|------|----------|
| `README-NPU.md` | NPU 分支的安装步骤、运行示例、已知限制、上述 Migration Guide 速查表 | Phase 1a 收尾时落第一版；后续仅在交付物边界变化时更新 |
| `KNOWN_ISSUES.md` | NPU 算子级阻塞跟踪（J2b 产出格式：`<issue-id> \| <算子名/blocker 类型> \| <临时绕过路径> \| <vendor 工单 URL>`） | 持续——每次 vendor escalation 触发追加；vendor 修复后删行 |
| `CHANGELOG-NPU.md` | 每次上游 InfiniteTalk 主仓 rebase（J4）后的 NPU 适配增量记录 | 持续——每次 J4 完成后追加一段 |

**显式 Out-of-Scope（文档侧）**：
- ❌ Sphinx / mkdocs 静态站点
- ❌ API 自动生成文档（无外部 API surface）
- ❌ 视频教程
- ❌ `MIGRATION-FROM-CUDA.md` 独立文件（速查表合入 `README-NPU.md` 即可，不单列）

### Implementation Considerations

- **测试策略锚点（不在本节钉死，详见 Step 9 / Step 10）**：MVP 阶段无单元测试硬性要求；以 J5 acceptance + J1 happy-path 端到端跑通为主；算子级 2h spike 是 sprint 前置，不属于持续测试套件
- **代码组织约束（已落 NFR-03 / NFR-18）**：所有 NPU 适配代码必须可被 `--device cuda` 路径完全旁路（runtime 无副作用）
- **依赖版本锁定**：`requirements-npu.txt` 必须 pin 到 `torch_npu==2.7.1`（不接受 `>=`），避免上游 torch_npu 更新引入兼容性回归

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach**: **Problem-solving MVP**——验证单一命题："InfiniteTalk 推理路径能在 ≥1 张 910B 上以已声明的功能完整度跑起来"。无 experience / platform / revenue 维度。

**Coding-Agent 核心原则**（继承自 PRD purpose §`Coding-Agent Consumer Mindset`）：
- MVP scope **push UP, not down**——纳入 4 模式 + Gradio + 设备抽象 + CLI 分发扩展，是 aggressive 而非 minimal 的 scope
- 风险隔离通过 Step 3 Phase 1a / 1b 内部里程碑实现，无需依赖人力分摊估算

### MVP Feature Set (Phase 1)

**指针引用**：完整列表见 `## Product Scope > MVP - Minimum Viable Product`（Step 3）。本节不重复，仅锚定 phase 收尾门槛：
- **Phase 1a**：multitalk 单模式跑通 + Gradio 起 + 设备抽象 + xfuser 单卡 stub（J1 + J3 acceptance 通过）
- **Phase 1b**：i2v / t2v / flf2v 三模式可达，各自 J5 验收通过

**核心 user journeys 支撑**：J1 / J2a / J2b / J3 / J5 在 MVP 内全部启用；J4（rebase）属于持续维护流程，MVP 收尾时一次"演练通过"即可。

### Post-MVP Features

**指针引用**：完整列表见 `## Product Scope > Growth Features (Post-MVP)` 与 `## Product Scope > Vision (Future)`（Step 3）。

阶段映射：
- **Phase 2 (Growth)** = 多卡 SP + VACE + TeaCache + int8 量化。**多卡 SP 是用户 ≥2 卡产品环境硬约束的兑现，Growth 最高优先级。**
- **Phase 3 (Vision)** = 完整 CUDA 功能等价 + rebase 工作流自动化 + 质量门槛升级到中等档（N=5 × M=2）

### Risk Mitigation Strategy

**Technical Risks**（**本项目唯一显著的 risk surface**）：
- 详见 `## Product Scope > Risks` 表（Step 3）已列 3 条：attention 算子替换语义偏差 / xfuser 桩化执行路径回归 / i2v/t2v/flf2v CLI 不可达
- 本节补充：**算子级阻塞的 escalation 路径**已通过 J2a + J2b 工作流化，构成 known-issue 跟踪 + vendor 工单双通道 fallback。Coding agent 遇到 NPU 算子级阻塞时**直接走 J2a 输出 escalation packet 流程**，不发明新 fallback 逻辑

**Market Risks**：**N/A**。验收主体为内部 POC 团队（Step 2c 锚定），不面向市场。如 Vision § "可选公开发布"被激活，本节需重新打开。

**Capacity & Dependency Risks**（非人力维度）：
- **910B 硬件可达性**：MVP 验证依赖 ≥1 张可用 910B + CANN 2.5.1 + 驱动/固件就绪。硬件不可达期间 coding agent **不应**尝试在 CUDA 路径上模拟 NPU 行为；改为推进非依赖硬件的工作（适配层代码组织、文档骨架、CLI flag 重构）
- **Vendor escalation 响应延迟**：vendor 工单未及时回填时，**优先**通过临时绕过（dtype 切换 / mask 形态调整 / 算子降级到 CPU 路径）解锁 MVP 主线；**不以 vendor 修复时间线作为 sprint 关键路径依赖**
- **Phase 2 SP 自研失败**：若 HCCL + Ulysses 等价物自研难度超预期，回退方案为**等候 MindSpeed / xfuser-ascend 公开版本**——这是 Phase 2 的可接受退路，**不影响 MVP 边界**

## Functional Requirements

### Device Abstraction & CLI Surface

- FR-01: Migration Engineer can select compute device via CLI `--device {cuda,npu}` flag on `generate_infinitetalk.py`
    - AC: Given a CUDA-capable host, when running `python generate_infinitetalk.py --device cuda --task infinitetalk-14B ...`, then the pipeline executes on CUDA exactly as the upstream baseline
    - AC: Given a 910B-equipped host with `torch_npu 2.7.1` installed, when running `--device npu`, then the pipeline executes on NPU and produces the configured output file
    - AC: Given any host, when `--device` is omitted, then the CLI defaults to `cuda` to preserve upstream behavior

- FR-02: POC Operator can select compute device via CLI `--device {cuda,npu}` flag on `app.py` (Gradio)
    - AC: Given `python app.py --device npu` on a 910B host, when the user accesses the home page, then HTTP 200 is returned and all visible tabs mount without browser JS console error
    - AC: Given Gradio launched without `--device`, when started, then the default `cuda` path applies for backward compatibility

- FR-03: System replaces hard-coded `torch.cuda.set_device` with device-aware initialization at all entry points
    - AC: Given `--device npu`, when `generate_infinitetalk.py:457,465` executes, then `torch.npu.set_device(local_rank)` is invoked instead of `torch.cuda.set_device`
    - AC: Given `--device cuda`, when the same call executes, then the upstream CUDA init path runs unchanged

- FR-04: System supports per-mode dispatch via either extended `--task` enumeration or new `--mode` flag (C12 decision)
    - AC: Given the dispatch mechanism in place, when the user invokes any of `multitalk / image2video / text2video / first_last_frame2video`, then the corresponding pipeline class (`InfiniteTalkPipeline / WanI2V / WanT2V / WanFLF2V`) loads and runs
    - AC: Given an unknown mode value, when invoked, then the CLI exits non-zero with a clear error listing valid mode names

### Attention & xfuser Adaptation

- FR-05: System replaces `xformers.ops.memory_efficient_attention` calls with `torch_npu.npu_fusion_attention` on the NPU path
    - AC: Given `--device npu`, when execution reaches `wan/modules/attention.py:263,266,380` or `wan/distributed/xdit_context_parallel.py:540`, then the call routes to `torch_npu.npu_fusion_attention` with appropriate layout (`BNSD` or `TND`)
    - AC: Given variable-length attention input (`BlockDiagonalMask` semantics), when routed on NPU, then the call uses `TND` layout with `actual_seq_qlen` / `actual_seq_kvlen` derived from block boundaries
    - AC: Given `--device cuda`, when the same call sites execute, then `xformers.ops.memory_efficient_attention` is invoked unchanged

- FR-06: System routes attention through both `WanModel` classes without divergent code paths
    - AC: Given any of the 4 modes on NPU, when its corresponding `WanModel` class (`wan/modules/multitalk_model.WanModel` for multitalk; `wan/modules/model.WanModel` for i2v/t2v/flf2v) executes attention layers, then the device-aware attention adapter is invoked
    - AC: Given the adapter layer, when called from either `WanModel` class, then no class-specific attention bypass exists

- FR-07: System short-circuits xfuser sequence parallelism when `world_size == 1`
    - AC: Given `world_size == 1`, when any code path would access `xFuserLongContextAttention`, then the call is bypassed via import isolation and a runtime assertion confirms it
    - AC: Given `world_size == 1`, when `get_sequence_parallel_world_size()` is invoked, then it returns `1` without contacting xfuser
    - AC: Given the `usp_*` patches at `wan/multitalk.py:254-263`, when `world_size == 1`, then the patches are bypassed (no-op or skipped via guard)

### Pipeline Mode Coverage

- FR-08: Migration Engineer can run `multitalk` mode end-to-end on a single 910B
    - AC: Given valid `examples/multitalk_demo.json` and `--device npu`, when the canonical multitalk command (Step 7 § Code Examples) is executed, then `out_multitalk.mp4` is produced, exit code is 0, and `ffprobe` validates the file as MP4
    - AC: Given the same input replayed, when run twice, then both runs complete with exit code 0 (reproducibility floor)

- FR-09: Migration Engineer can run `image2video` mode end-to-end on a single 910B
    - AC: Given valid `examples/i2v_demo.json` and `--device npu`, when the canonical i2v command runs, then `out_i2v.mp4` is produced and `ffprobe`-valid
    - AC: Given the i2v pipeline (`WanI2V`), when invoked, then it shares the same attention adapter as FR-05

- FR-10: Migration Engineer can run `text2video` mode end-to-end on a single 910B
    - AC: Given valid `examples/t2v_demo.json` and `--device npu`, when the canonical t2v command runs, then `out_t2v.mp4` is produced and `ffprobe`-valid
    - AC: Given the t2v pipeline (`WanT2V`), when invoked, then it shares the same attention adapter as FR-05

- FR-11: Migration Engineer can run `first_last_frame2video` mode end-to-end on a single 910B
    - AC: Given valid `examples/flf2v_demo.json` and `--device npu`, when the canonical flf2v command runs, then `out_flf2v.mp4` is produced and `ffprobe`-valid
    - AC: Given the flf2v pipeline (`WanFLF2V`), when invoked, then it shares the same attention adapter as FR-05

### Gradio NPU Compatibility

- FR-12: POC Operator can launch Gradio Demo on 910B and trigger one `multitalk` inference end-to-end
    - AC: Given Gradio launched as `python app.py --device npu`, when the operator opens the URL, then HTTP 200 returns and all visible tabs mount without browser console error
    - AC: Given the home page loaded, when the user uploads reference image + audio and clicks "Generate", then the backend invokes the same multitalk inference path as FR-08, the video file is returned to the frontend, and the embedded `<video>` element plays it

### Observability, Diagnostics & Escalation

- FR-13: System emits unsupported-operator fallback inventory when configured
    - AC: Given `TORCH_NPU_DUMP_UNSUPPORTED_OPS=1` in environment, when an inference run completes, then a host-fallback operator listing is produced at the default path (or `<run_dir>/unsupported_ops.txt`)
    - AC: Given the file produced, when read, then it lists each operator name plus its trigger count over the run

- FR-14: System records peak NPU HBM usage and end-to-end wall-clock per run
    - AC: Given any successful inference run, when the run finishes, then peak HBM usage and total wall-clock are extractable from logs or a trace file
    - AC: Given multiple successful runs, when their metrics are read, then both metrics use stable units (HBM in bytes, wall-clock in seconds)

- FR-15: System translates raw NPU error codes into operator-name + input-shape locator messages
    - AC: Given an unsupported-operator runtime error on NPU, when the error is surfaced to the user, then the message string contains the offending operator name and the input tensor shapes (not just `ACL error <code>`)
    - AC: Given a non-NPU error, when surfaced, then the upstream error path is preserved unchanged

- FR-16: Migration Engineer can produce a vendor-ready escalation packet from any blocker reproduction
    - AC: Given an NPU operator-level blocker (one of `OOM` / `op-not-implemented` / `dtype-mismatch` / `numerical-divergence`), when the engineer collects diagnostic artifacts, then `escalation-packet/<issue-id>/` contains: input json, `env.txt`, full traceback, `unsupported_ops.txt`, and a `manifest.yaml` naming the blocker type
    - AC: Given the packet, when handed to a third party, then the third party can re-run on a comparable 910B host and reproduce the same blocker

- FR-17: Vendor Escalation Coordinator can record a known-issue entry that survives across PRs
    - AC: Given a new escalation, when the coordinator updates `KNOWN_ISSUES.md`, then a new line in the format `<issue-id> | <op/blocker type> | <workaround> | <vendor ticket URL>` is committed
    - AC: Given a vendor fix delivered, when the coordinator closes the escalation, then the corresponding line is removed from `KNOWN_ISSUES.md`

### Adaptation Layer, Distribution & Documentation

- FR-18: System keeps NPU adaptation code modular such that `--device cuda` runtime is unaffected
    - AC: Given `--device cuda`, when any code path executes, then no NPU-specific runtime code path is entered (verifiable by import-time guards or runtime tracing)
    - AC: Given a synthetic toggle of the adapter layer, when switched by `--device`, then both branches operate independently

- FR-19: System ships a separate `requirements-npu.txt` pinned to `torch_npu==2.7.1`
    - AC: Given the NPU branch repo, when `requirements-npu.txt` is read, then it contains `torch_npu==2.7.1` (exact pin, not `>=`) as a top-level dependency
    - AC: Given the NPU branch repo, when upstream `requirements.txt` is read, then `torch_npu` does not appear there (separation preserved)

- FR-20: Upstream Rebase Maintainer can merge upstream commits with conflicts limited to shared lines
    - AC: Given an upstream commit, when cherry-picked into the NPU branch, then conflicts only arise on lines that exist in both upstream and NPU adaptation contexts (no orthogonal NPU file conflicts)
    - AC: Given conflicts resolved, when the J1 acceptance command is re-run, then the run succeeds with exit code 0

- FR-21: System ships three documentation deliverables maintained per the documented cadence
    - AC: Given the NPU branch repo, when inspected, then `README-NPU.md`, `KNOWN_ISSUES.md`, `CHANGELOG-NPU.md` exist at the repo root
    - AC: Given a vendor-escalation event (J2b) or rebase event (J4), when the corresponding workflow completes, then the relevant document is updated in the same commit

- FR-22: POC Reviewer can record acceptance verdict for each MVP mode with auditable artifacts
    - AC: Given a completed inference for any of the 4 modes, when the reviewer accepts it, then a PR comment is left in the form `approved: <mode> passed thinnest bar`, accompanied by the recording and `out.mp4` artifact attached to the PR
    - AC: Given the same artifact set, when the machine-check proxy runs (frame-variance check OR face-detector bbox in ≥50% frames), then the result is captured at `<run_dir>/quality-check.txt`

## Out of Scope

- **OOS-01**: 多卡 sequence parallelism — Reason: Phase 2 (Growth) 兑现；MVP 单卡足以验证主路径
- **OOS-02**: `vace` 模式 — Reason: 非主路径功能；Growth 阶段
- **OOS-03**: `TeaCache` 加速 — Reason: 优化项非必要功能；Growth 阶段
- **OOS-04**: `int8` 量化（`optimum-quanto` NPU 路径） — Reason: 量化路径在 NPU 上未验证；Growth 阶段单独立项验证
- **OOS-05**: CUDA ↔ NPU 性能对标 — Reason: 验收主体明确不要求（Step 2c）
- **OOS-06**: bit-exact 数值等价校验 — Reason: FA 算子与 dtype 路径在不同硬件上不可能 bit-exact，常识性工程让步
- **OOS-07**: ComfyUI 集成 — Reason: 上游 README 明确 ComfyUI 走独立分支
- **OOS-08**: PyPI / 私有 PyPI / Docker 镜像分发 — Reason: fork-only 分发模式（Step 7 § Project-Type Overview）
- **OOS-09**: Sphinx / mkdocs 静态站点 + API 自动文档 + 视频教程 — Reason: 三份 markdown 文档已覆盖文档需求面
- **OOS-10**: IDE 集成 / 外部 import-able API — Reason: 项目是可运行代码仓库，不暴露 import-able 库 API
- **OOS-11**: 部署侧水印 / C2PA 嵌入 / NSFW 过滤运行时 / 跨境数据合规 — Reason: 仅在 Vision § "可选公开发布" 兑现时评估（Step 5 Deferred Concerns）
- **OOS-12**: 单元测试 / CI 自动化套件 — Reason: MVP 阶段以 J1 + J5 端到端验收为主；自动化测试不是验收前置（Phase 2 后再评估）

## Non-Functional Requirements

### Performance

- NFR-01: 启用 `--device cuda` 时，CUDA 推理路径的端到端 wall-clock 相对上游基线退化 ≤ 5%
    - 测量：固定 `input_json` + 固定上游 commit hash + 同一 GPU 主机，NPU 分支 `--device cuda` vs 直接 checkout 上游主仓 commit，运行 J1 命令各 3 次取均值
    - 适用：MVP 收尾时一次性验证（CUDA 路径无回归 floor）

> 📌 **MVP 范围内 NPU 路径不设性能 SLO**——OOS-05 已声明不做 CUDA↔NPU 性能对标。NPU wall-clock 与 HBM 仅作为 observability 信号（FR-14）采集，不是验收门槛。Phase 2 若激活，单独定义。

### Maintainability

- NFR-02: NPU 适配代码对每个上游主路径文件（`wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` / `generate_infinitetalk.py` / `app.py`）的直接编辑行数 ≤ 80 行
    - 测量：对 NPU 分支 vs 上游 main 的 `git diff --stat`，按文件统计 added + modified 行数（不含纯 wrapper 文件）
    - 强制原因：该约束是 J4 rebase 工作流可持续的硬性条件；超出阈值意味着上游每次大改都会撞 NPU 适配代码

- NFR-03: NPU 适配引入的代码以独立 wrapper / 条件 import / monkey-patch 形态隔离，可被一组 git revert commit 完全撤回
    - 测量：在 NPU 分支上 revert NPU 适配 commit set 后，CUDA 路径 acceptance 命令仍然可执行成功且输出与未引入适配前等价
    - 强制原因：保障可逆性，降低"回不去"的技术债风险

- NFR-04: J4 rebase 演练（cherry-pick 上游 1 个 commit + 解决冲突 + 重跑 J1）的端到端 wall-clock ≤ 5 个工作日
    - 测量：MVP 收尾时执行一次对当前上游 HEAD 的 rebase 演练，记录从 `git fetch upstream` 到 J1 acceptance 通过的总时长
    - 注：5 个工作日内未完成会触发 NFR-02 / NFR-03 的 audit——通常意味着适配层模块化失效

### Compatibility

- NFR-05: 启用 `--device cuda` 时，所有上游 CUDA 路径的现有 acceptance 行为保持不变
    - 测量：在 NPU 分支 + `--device cuda` 路径，运行上游主仓提供的现有验收用例（如有）；运行 J1/FR-08 的 CUDA 等价命令，输出文件 `ffprobe`-stream-equivalent 于上游主仓输出
    - 适用：MVP 收尾必须验证一次

- NFR-06: NPU 路径在 `torch_npu==2.7.1` + CANN 2.5.1 + **Python 3.8 / 3.9 / 3.10** 三个版本上均可执行 J1 acceptance 命令
    - 测量：在 3 个独立 Python venv 中分别 `pip install -r requirements-npu.txt` + 运行 J1 命令，全部退出码 0
    - 注：本 NFR 是 torch_npu 2.7.1 安装文档（Python 3.8–3.10 约束）的直接兑现

- NFR-07: NPU 路径**不要求**与 CUDA 路径的输出 bit-exact 等价
    - 测量：N/A——声明性 NFR，等同 OOS-06 的形式化固化
    - 强制原因：FA 类算子 + fp16/bf16 在不同硬件上不可能 bit-exact，工程常识。显式 NFR 化避免下游 agent 试图"修复"非 bit-exact 输出

### Reliability

- NFR-08: J1 acceptance 命令在同一固定输入下连续运行 N 次（N ≥ 3）全部退出码 0
    - 测量：MVP 收尾时执行；每次间不重启进程外的环境
    - 注：本 NFR 是 FR-08 第二条 AC（reproducibility floor）的形式化

- NFR-09: J2a 触发的 NPU 算子级阻塞**不**阻塞 MVP 主线推进
    - 测量：发现 escalation 候选时，A1 通过临时绕过路径（dtype 切换 / mask 形态 / CPU 算子降级）应能继续推进 J1 happy path；packet 提交不构成 sprint blocker
    - 强制原因：兑现 Step 3 + Step 8 的"vendor escalation 是 fallback 而非范围收缩"决策

### Observability

- NFR-10: NPU 路径三类观测信号（fallback ops / HBM 峰值 / wall-clock）须以**机器可解析格式**输出
    - 测量：FR-13 输出文件可被 `awk` / Python 脚本解析为 `(op_name, count)` 元组列表；FR-14 的 HBM 与 wall-clock 可从日志或 trace 文件以正则提取
    - 不强制 JSON / YAML 格式，强制"工具链可消费"
    - 强制原因：观测信号要支撑 Phase 2 vendor escalation 谈判，必须能被工具链直接吃

### 不适用类别（显式声明，避免下游 agent 误以为遗漏）

- **Security**: N/A——验收主体内部 POC，不处理 sensitive data，不暴露公网服务
- **Scalability**: N/A（MVP 范围）——多卡 SP 在 Phase 2 (Growth) 单独定义；MVP 单卡推理不存在 scale 维度
- **Accessibility**: N/A——内部 POC 不面向公众；Gradio 仅 A2 演示用，不进入需可达性评估的用户面
- **Integration**: 已在 FR-17（vendor 工单跟踪）+ FR-20（上游 rebase 兼容性）显式覆盖，本节不重复 NFR 化
