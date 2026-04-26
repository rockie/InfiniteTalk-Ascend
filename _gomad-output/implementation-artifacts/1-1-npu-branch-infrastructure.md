# Story 1.1: 创建 NPU 分支基础设施（requirements-npu.txt + lint gate + ignore-list）

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Migration Engineer,
I want a separate `requirements-npu.txt` with `torch_npu==2.7.1` pinned and a CI lint gate enforcing ≤80 lines per upstream main file,
so that upstream rebases stay sustainable from day 1（NFR-02 hard enforcement）。

> **NFR-03 关系澄清**：本 story 仅创建基础设施文件（lint 脚本 / CI workflow / pre-commit hook / `requirements-npu.txt` / ignore-list），不产生 NPU 适配代码 (adapter / wrapper / monkey-patch)。NFR-03 ("NPU 适配层可被一组 `git revert` 完全撤回") 是后续 stories（1.2~1.6 等）的结构性目标，并非本 story 的 testable 成功标准；这里只把它列为**动机背景**，不写进 AC。

## Acceptance Criteria

> **来源映射**：Story 1.1 锚定 FR-19 / NFR-02 / NFR-10 (machine-parseable 间接前置)。NFR-03 仅作为下游 stories 的结构性目标背景出现（见 Story 节末尾 NFR-03 关系澄清），不在本 story AC 之内。AC 文本逐字承载 epics.md § Story 1.1 + PRD § FR-19 + § NFR-02。

1. **AC-1（lint gate — 主路径文件超阈值阻断 CI）**
   **Given** the NPU branch repo
   **When** CI runs
   **Then** files where the `added` column of `git diff --numstat <baseline_commit>..HEAD -- <file>` exceeds 80 lines (excluding the documented ignore-list) cause CI to fail with a clear error listing the offending file(s) + the measured added-line count（`added` 列定义见 Dev Notes § 行数计量规则）

2. **AC-2（pre-commit 阻断累计超阈值改动）**
   **Given** an attempt to commit to a tracked main-path file
   **When** pre-commit hook runs
   **Then** it **blocks** the commit (default mode) if cumulative additions on that file vs upstream baseline exceed the 80-line threshold
   **And** blocking mode 必须可被 emergency 旁路（如 `--no-verify`）但 CI gate 仍会拦截（避免 hook bypass 绕过质量门）

3. **AC-3（`requirements-npu.txt` 独立 + 精确 pin + 文件用途头注释）**
   **Given** `requirements-npu.txt`
   **When** read
   **Then** it contains `torch_npu==2.7.1` (exact pin, not `>=`) plus any NPU-only patch deps
   **And** upstream `requirements.txt` does not contain `torch_npu`（separation preserved 验证：grep `torch_npu` `requirements.txt` 必须返回零行）
   **And** 文件顶部含一段 header comment 说明本文件用途及与上游 `requirements.txt` 的分工（不重复上游依赖；仅含 NPU-only 增量）

4. **AC-4（ignore-list 透明化 grandfather 文件）**
   **Given** the ignore-list at the **pinned path** `tools/npu-line-budget-ignore.txt`
   **When** inspected
   **Then** it documents pre-existing legacy CUDA files explicitly with rationale（每行格式：`<file_path> # <reason>`，rationale 必须解释为什么该文件不参与 80 行约束 — 例如"上游已大改的 i18n 文件 / 非 NPU 主路径文件"）
   **And** ignore-list 默认为空或仅含明确论证的条目（不允许"为方便加进去"）

5. **AC-5（lint gate 在 5 个主路径文件上生效）**
   **Given** the lint gate is configured
   **When** inspected
   **Then** the tracked file list explicitly includes 全部 5 个 PRD § NFR-02 钉死的主路径文件：
   - `wan/modules/attention.py`
   - `wan/multitalk.py`
   - `wan/distributed/xdit_context_parallel.py`
   - `generate_infinitetalk.py`
   - `app.py`

   > 说明：本 story scope 内 5 个文件均 zero-touch，但 `app.py` 等文件由后续 stories（1.2~1.7 / 3.x / 4.x）作为 lint gate 的**首批消费者**触发——gate 必须在它们被改动**之前**生效，因此即便本 story 不修改这些文件，AC-5 仍要求它们出现在 tracked 列表里（gate 的正确性由后续 stories 回溯验证）。

6. **AC-6（Task 6 烟测在 PR 描述留痕）**
   **Given** Task 6 的本地烟测（6.1 baseline / 6.2 阻断 / 6.3 ignore-list 生效）
   **When** PR 提交
   **Then** PR 描述中粘贴三个 case 的脚本 stdout 片段（或截图），证据标注哪段对应 6.1 / 6.2 / 6.3，以便 reviewer 不必猜测烟测是否实际执行

7. **AC-7（pre-commit 与 CI 共享同一检查脚本，DRY）**
   **Given** the pre-commit hook (`tools/pre-commit-npu-line-budget.sh`) 与 CI workflow (`.github/workflows/npu-line-budget.yml`)
   **When** 检查实现
   **Then** 二者必须 invoke 同一个 `tools/check_npu_line_budget.py`（同一份算法实现，无双份逻辑 / 无重复 budget 计算分支）

## Tasks / Subtasks

- [x] **Task 1**：建立 upstream baseline 引用机制（AC: #1, #5）
  - [x] 1.1 在 lint gate 主体脚本 `tools/check_npu_line_budget.py` 中**写死初始 baseline commit hash = `fd63149`**（即当前 `main` HEAD）作为对照基线。Bump 时机：每次 J4 rebase 演练（**Story 5.2**）完成后由 maintainer 手动更新该常量（在 PR 描述中说明 bump 的旧/新 hash + 触发的 J4 rebase 链接）。**禁止**使用 `origin/main` 动态引用（会导致 baseline 漂移、80 行约束变成移动靶）。
  - [x] 1.2 列出受跟踪的 5 个主路径文件 constant（PRD § NFR-02 钉死列表）—— 不在该列表的文件不参与 80 行约束
  - [x] 1.3 实现 baseline-vs-HEAD 行数计量：使用 `git diff --numstat <baseline_commit>..HEAD -- <tracked_file>`，**取每个文件 numstat 输出的第 1 列（added 列）**作为该文件的 budget 占用值；deleted 列不计入。说明：`git diff --numstat` 仅有 `<added>\t<deleted>` 两列，并无独立的 "modified" 列——一处修改实际表现为 `1 added + 1 deleted`，故"added 行（column 1）"已等价于"新增 + 修改"行的并集（删除部分被规则排除）。空行 / 注释行计入（保守，避免开发者通过加注释达成"伪减行"）。
  - [x] 1.4 单文件超 80 行 → exit code 非零 + 输出 `[NPU LINE BUDGET] <file>: <N> lines exceed 80-line budget vs <baseline_commit>`

- [x] **Task 2**：创建 ignore-list 文件（AC: #4）
  - [x] 2.1 在 **`tools/npu-line-budget-ignore.txt`**（钉死路径，与脚本同目录、避免根目录污染、与 Project Structure Notes § 新增文件列表一致）创建 ignore-list，格式为每行 `<file_path> # <reason>`
  - [x] 2.2 文件初始内容为空或仅含必要 grandfather 项；首版 expected = empty（无 legacy CUDA 大改文件需要豁免；后续若发现可追加并伴 PR review 论证）
  - [x] 2.3 lint gate 读取该文件并将其中条目从受跟踪文件列表里剔除

- [x] **Task 3**：CI gate 集成（AC: #1）
  - [x] 3.1 新增 `.github/workflows/npu-line-budget.yml`（或合入既有 workflow）—— trigger on `pull_request` + `push`
  - [x] 3.2 步骤序列：checkout NPU 分支 → `git fetch upstream` → 调用 Task 1 的检查脚本 → 失败时 fail CI 并打印 offending files
  - [x] 3.3 **不要**预创建 `README-NPU.md` stub（终版由 Story 1.7 落地，避免 stub-then-extend 隐式依赖污染 Story 1.7）；改为以 **inline workflow YAML comments** + `tools/check_npu_line_budget.py` 模块顶部 docstring 的形式，注明 CI 失败时的修复路径：(a) 将多余代码外置到 NPU wrapper 文件以减少主路径行数；或 (b) 在论证后追加到 ignore-list 并经 PR review

- [x] **Task 4**：pre-commit hook（AC: #2, #7）
  - [x] 4.1 新增 `tools/pre-commit-npu-line-budget.sh`（或基于 `pre-commit` 框架的 hook 配置 `.pre-commit-config.yaml` 一项）—— 调用 Task 1 的同一 `tools/check_npu_line_budget.py`（**DRY 硬约束 — AC-7**：CI workflow 与 pre-commit hook 必须 invoke 同一脚本，不允许双份 budget 计算逻辑）
  - [x] 4.2 安装说明以 inline 注释形式记录在 `tools/pre-commit-npu-line-budget.sh` 顶部 docstring（典型命令：`ln -sf ../../tools/pre-commit-npu-line-budget.sh .git/hooks/pre-commit` 或 `pre-commit install`）；**不写入 `README-NPU.md`**（README-NPU.md 由 Story 1.7 创建终版，本 story 不预先 stub）
  - [x] 4.3 hook 模式：**default = block**（与 AC-2 一致）；`--no-verify` 可旁路（开发者紧急修复路径）；CI gate 不被 hook 旁路状态影响（AC-2 第二条要求）

- [x] **Task 5**：`requirements-npu.txt` 创建（AC: #3）
  - [x] 5.1 在仓库根新增 `requirements-npu.txt`，第一条依赖行 = `torch_npu==2.7.1`（exact pin，不可使用 `>=`/`~=`）
  - [x] 5.2 文件顶部添加 header 注释段（**AC-3 强制要求**），至少包含两点：(a) 本文件用途 = NPU-only 依赖增量清单；(b) 与上游 `requirements.txt` 的分工 = 不重复上游依赖、不替换上游版本，仅追加 NPU 路径独有 deps
  - [x] 5.3 验证 `requirements.txt` 内不含 `torch_npu`：执行 `grep -c '^torch_npu' requirements.txt` **必须返回 `0`**；**若返回非零则本 story 直接 fail 并 escalate 给 maintainer**（KNOWN_ISSUES.md 是 Epic 2 / Story 2.3 的交付物，本 story 不依赖也不 fallback 至该文件）。说明：实测当前上游 `requirements.txt` 不含 `torch_npu`，此项预期一次通过

- [x] **Task 6**：自检脚本本地烟测（AC: #1, #2, #5, #6）
  - [x] 6.1 在不修改任何主路径文件的情况下，本地运行 lint 脚本 → 应 exit 0（baseline 状态）
  - [x] 6.2 故意在 `wan/modules/attention.py` 末尾追加 90 行注释 → 应 exit 非零并打印 offending file（验证阻断逻辑）；测试后**必须 revert**
  - [x] 6.3 在某文件追加 50 行 + 将该文件加入 ignore-list → 应 exit 0（验证 ignore-list 生效）；测试后必须 revert
  - [x] 6.4 **将 6.1 / 6.2 / 6.3 三个 case 的脚本 stdout 片段（或截图）粘贴到 PR 描述中**，每段标注对应的子任务编号（AC-6 evidence retention）

## Dev Notes

> **核心定位**：本 story 是 Epic 1 的**前置守门员**——所有后续 story（1.2~1.7、3.x、2.x、4.x、5.x）的代码改动都必须穿过本 story 建立的 lint gate。如果本 story 实现错误（例如 budget 算法不对、baseline 锚定漂移），整个 Epic 1 的 maintainability 承诺（NFR-02 / NFR-03）将悄悄失效。

### 关键架构约束（来自 architecture-summary.md § Maintainability 量化约束）

- **NFR-02 受跟踪文件白名单（5 个，钉死）**：
  - `wan/modules/attention.py`
  - `wan/multitalk.py`
  - `wan/distributed/xdit_context_parallel.py`
  - `generate_infinitetalk.py`
  - `app.py`
- **行数计量规则（载重技术细节，pin 死）**：每个受跟踪文件的 budget 占用值 = `git diff --numstat <baseline_commit>..HEAD -- <file>` 输出**第 1 列（added 列）**之和。
  - `git diff --numstat` 仅有 `<added>\t<deleted>` 两列，**没有独立的 "modified" 列**；一处修改在 numstat 输出里表现为 `1 added + 1 deleted`。
  - 由于本规则明确"删除行不计入 budget"，所谓"added + modified" 实际上等价于"added 列"——不再保留有歧义的 "added + modified" 措辞。
  - 删除行：不计入 budget。
  - 空行 / 注释行：计入 budget（保守，避免开发者通过加注释达成"伪减行"）。
  - 多文件 budget 各自独立判定（每个 tracked 文件的 added 行独立 ≤ 80），不做跨文件汇总
- **超阈值的处理路径**（架构权威决策，**非本 story 实现项**，但 Dev Notes 必须 surface 给后续实施者）：
  - 主路径文件超过 80 行的工作**必须外置为独立 wrapper / monkey-patch 文件**（不计入该文件统计）
  - 这是 NFR-03（独立 wrapper / 条件 import / monkey-patch 形态隔离，可被一组 git revert 完全撤回）的对偶约束

### 上游 baseline 锚定（关键工程决策 — pin 死 day-1 决策）

`origin = https://github.com/MeiGen-AI/InfiniteTalk.git` 即为 upstream（fork-only 模式，无独立 upstream remote）。本 story 实施时：

- **初始 baseline commit hash = `fd63149`**（当前 `main` HEAD，PRD 编写时间快照），写死在 `tools/check_npu_line_budget.py` 顶部常量中。
- **Bump 流程（明确归属 Story 5.2 = J4 Upstream Sync Drill）**：每次 J4 rebase 演练完成、上游 cherry-pick 合入后，由 maintainer 在该 PR 中手动更新此常量为新的 upstream HEAD hash，并在 `CHANGELOG-NPU.md`（Story 5.3 维护节奏）记录 bump 的旧→新 hash。
- **禁止**使用 `origin/main` 动态引用——会导致 baseline 随上游漂移，本 story 的"≤80 行"约束变成移动靶。

### 主路径文件当前行数（baseline 参考）

来自 `wc -l` 实测（截至 commit `fd63149`）：

| 文件 | 当前行数 |
|------|---------|
| `wan/modules/attention.py` | 392 |
| `wan/multitalk.py` | 855 |
| `wan/distributed/xdit_context_parallel.py` | 549 |
| `generate_infinitetalk.py` | 663 |
| `app.py` | 819 |

> 这些是 baseline 行数，**不是** budget。budget 是相对 baseline 的 `git diff --numstat` added 列计数 ≤ 80（见 § 行数计量规则）。

### 与 NFR-10（机器可解析观测格式）的弱依赖

本 story 是 lint gate / 文件骨架建设，**不**直接产出观测信号；但 lint 脚本的 stdout 应该是机器可解析的（每行 `<file>:<count>` 格式），方便未来 J5 acceptance 留痕脚本消费。

### 关于 `xfuser` / `optimum-quanto` 在 `requirements.txt` 的存在

实测 `requirements.txt` 包含 `xfuser>=0.4.1` 与 `optimum-quanto==0.2.6` —— 这些是 **CUDA 路径** 的依赖。本 story **不要修改它们**（NFR-05：`--device cuda` 路径行为不变）。`xfuser` 在 NPU 路径会通过 Story 1.3 的单卡 stub 短路；不需要从 `requirements.txt` 删除。

### Project Structure Notes

- **新增文件**（本 story 唯一允许的写入位置）：
  - `requirements-npu.txt`（仓库根）
  - `.github/workflows/npu-line-budget.yml`（或类似路径，CI 配置）
  - `tools/check_npu_line_budget.py`（lint 脚本主体；Python 实现以保持跨平台）
  - `tools/pre-commit-npu-line-budget.sh`（pre-commit hook 包装）
  - `tools/npu-line-budget-ignore.txt`（ignore-list；钉死路径，见 Task 2.1 / AC-4）
- **禁止修改**：5 个主路径文件中任意一个（本 story scope 内 zero touch）
- **禁止修改**：上游 `requirements.txt`（保持 NFR-05 的纯净）
- 本 story 可视为"basis story" — 它建立的脚本和 budget 规则是其他 6 个 Epic 1 stories 的硬约束

### Story DoD（仅本 story 对 Epic 1 DoD 的贡献项）

epics.md § Epic 1 DoD 含 5 项，但**仅最后 1 项**属于本 story scope。明确列出本 story 的 DoD 边界，防止 dev agent 越界 implement 邻近 stories 的工作：

| Story 1.1 DoD 项 | 验证方式 |
|------------------|----------|
| `requirements-npu.txt` 入仓且含 `torch_npu==2.7.1` exact pin + header 注释 | AC-3 |
| NFR-02 lint gate 在 CI 生效（`.github/workflows/npu-line-budget.yml` 接 PR + push trigger） | AC-1 |
| pre-commit hook 默认 block 模式生效 + `--no-verify` 旁路 + CI gate 不被旁路影响 | AC-2 |
| ignore-list 文件 (`tools/npu-line-budget-ignore.txt`) 入仓（首版 expected = empty） | AC-4 |
| pre-commit 与 CI workflow DRY 共享同一检查脚本 | AC-7 |
| Task 6 三 case 烟测 stdout 在 PR 描述留痕 | AC-6 |

**不属于本 story DoD（避免越界实施）**：J1 acceptance 命令 / `out_multitalk.mp4` / fallback / HBM / wall-clock 三信号 / `README-NPU.md` 第一版 —— 这些是 Story 1.2~1.7 的 DoD。

### Testing Standards Summary

PRD § OOS-12 明确："单元测试 / CI 自动化套件"在 MVP 阶段不是验收前置。但**本 story 例外**——它本身就是建 CI gate 的 story，因此 Task 6 的本地烟测是必须的（AC-1 / AC-2 阻断逻辑必须被验证生效）。

烟测形式：手工跑 + 在 PR 描述中粘贴脚本 stdout 截图即可，不需要建 pytest。

### References

- [Source: _gomad-output/planning-artifacts/epics.md#Story-1.1] — AC 文本来源
- [Source: _gomad-output/planning-artifacts/prd.md#FR-19] — `requirements-npu.txt` + `torch_npu==2.7.1` exact pin
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-02] — ≤80 行 hard 约束 + 5 个主路径文件钉死列表
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-03] — 适配层可 git revert 完全撤回的对偶约束
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#Maintainability-量化约束] — 主路径文件白名单 + 外置 wrapper 处理路径
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#5-依赖文件分层] — `requirements-npu.txt` 与 `requirements.txt` 完全分离
- [Source: _gomad-output/planning-artifacts/prd.md#J4-Upstream-Rebase-Maintainer] — lint gate 服务于 J4 rebase 工作流的可持续性

## Dev Agent Record

### Agent Model Used

Amelia（Senior Developer，Claude Opus 4.7 1M）— gm-dev-story 工作流，2026-04-26

### Debug Log References

- 烟测 6.1（baseline）：`python3 tools/check_npu_line_budget.py` → EXIT=0
- 烟测 6.2（+90 行 `wan/modules/attention.py`）：脚本输出 `[NPU LINE BUDGET] wan/modules/attention.py: 90 lines exceed 80-line budget vs fd63149`，EXIT=1；之后立即 revert，`wc -l` 回到 baseline 392 行。
- 烟测 6.3（+50 行 + ignore-list 命中）：脚本短路掉 attention.py 报告，EXIT=0；之后同步 revert `wan/modules/attention.py` 与 `tools/npu-line-budget-ignore.txt`。
- 最终 baseline 复测：`python3 tools/check_npu_line_budget.py` → EXIT=0，全部 5 个主路径文件 added=0。
- pre-commit hook 自检：`bash tools/pre-commit-npu-line-budget.sh` → EXIT=0（baseline 状态）。
- YAML 语法校验：`python3 -c "import yaml; yaml.safe_load(open('.github/workflows/npu-line-budget.yml'))"` 通过；`on:` 已加引号防 YAML 1.1 boolean 歧义。
- 上游分离精确校验：`grep -c '^torch_npu' requirements.txt` = 0（AC-3 通过，无需 escalate）。

### Completion Notes List

- **算法实现重要决策（已在脚本 docstring 内逐字论证）**：`_added_lines()` 使用 `git diff --numstat <baseline> -- F`（无 `..HEAD`）的工作树形态，而非 AC-1 字面写的 `<baseline_commit>..HEAD`。
  - 在 CI 场景，工作树 == HEAD，二者数学等价（AC-1 字面要求被覆盖）。
  - 在 pre-commit 场景，要committed 的改动**已 staged 但还未进 HEAD**——若按字面 `..HEAD` 形态，hook 会漏掉本次提交内容，直接破坏 AC-2。
  - 用同一公式服务两条入口（CI + pre-commit）正是 AC-7（DRY、单脚本）的物理前提；用字面 `..HEAD` 形态会强迫两份分支逻辑，违反 AC-7。
  - 该决策与 PRD § NFR-02 的"删除行不计入 budget、added 列覆盖添加+修改"语义保持一致——工作树形态只是把比较的右端点从 HEAD 推到 working tree，不改变行计量规则。
- **README-NPU.md 留给 Story 1.7**：CI workflow 与 pre-commit hook 都把"超阈值修复路径"写进 inline 注释（workflow YAML 头部 + `tools/check_npu_line_budget.py` 模块 docstring + hook 脚本 docstring），未预创建 stub README-NPU.md，避免 stub-then-extend 污染 Story 1.7（Task 3.3 / 4.2 严格要求）。
- **DRY 硬约束（AC-7）已物理保证**：CI workflow 仅一行 `python3 tools/check_npu_line_budget.py`；pre-commit hook 包装层只调同一脚本并加 `--no-verify` 友好提示，没有任何 budget 计算逻辑外泄。
- **Ignore-list 首版为空**：仅含说明性注释，符合 Task 2.2 "首版 expected = empty" 的约束；未来追加条目须经 PR review 论证。
- **本地烟测三 case 完整证据**已粘在下方 PR 描述片段，标注对应 6.1 / 6.2 / 6.3，满足 AC-6。
- **5 个主路径文件 zero-touch**：本 story 范围内未修改 `wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` / `generate_infinitetalk.py` / `app.py` 任意一个；上游 `requirements.txt` 同样未改。
- **Baseline 锚定 = `fd631497254e065777f2b2d0642de3600d674e24`**（即 `fd63149`），与 Task 1.1 / Dev Notes "上游 baseline 锚定" 节钉死的 PRD 编写时间快照一致。

### Smoke Test Evidence (AC-6, paste into PR description)

**Case 6.1 — baseline state, expect EXIT=0**

```
$ python3 tools/check_npu_line_budget.py
wan/modules/attention.py:0
wan/multitalk.py:0
wan/distributed/xdit_context_parallel.py:0
generate_infinitetalk.py:0
app.py:0
EXIT=0
```

**Case 6.2 — append 90 lines to `wan/modules/attention.py`, expect EXIT≠0; reverted afterwards**

```
$ python3 tools/check_npu_line_budget.py
[NPU LINE BUDGET] wan/modules/attention.py: 90 lines exceed 80-line budget vs fd63149
[NPU LINE BUDGET] Fix paths: (a) externalize code into a wrapper/monkey-patch file off the main-path list, or (b) add the file to tools/npu-line-budget-ignore.txt with explicit rationale + PR review.
wan/modules/attention.py:90
wan/multitalk.py:0
wan/distributed/xdit_context_parallel.py:0
generate_infinitetalk.py:0
app.py:0
EXIT=1

# revert verification:
$ wc -l wan/modules/attention.py
     392 wan/modules/attention.py   # back to baseline
```

**Case 6.3 — append 50 lines AND add `wan/modules/attention.py` to ignore-list, expect EXIT=0; both reverted afterwards**

```
$ python3 tools/check_npu_line_budget.py
wan/multitalk.py:0
wan/distributed/xdit_context_parallel.py:0
generate_infinitetalk.py:0
app.py:0
EXIT=0
# (note: attention.py absent from output because it was filtered out by the
#  ignore-list — exactly the behaviour AC-4 mandates)

# revert verification:
$ wc -l wan/modules/attention.py
     392 wan/modules/attention.py   # back to baseline
$ git diff --stat tools/npu-line-budget-ignore.txt
# (empty — ignore-list back to original)
```

### File List

新建文件（无任何现有文件被修改 — 5 个主路径文件 + `requirements.txt` 全部 zero-touch）：

- `tools/check_npu_line_budget.py` — NFR-02 行预算 lint 主脚本（CI + pre-commit 共用，AC-7 DRY 唯一来源）
- `tools/npu-line-budget-ignore.txt` — 行预算豁免清单（首版仅含说明性注释，无实际豁免条目）
- `tools/pre-commit-npu-line-budget.sh` — pre-commit hook 包装（chmod +x，default block，调用同一 Python 脚本）
- `.github/workflows/npu-line-budget.yml` — CI gate（trigger: pull_request + push，fetch-depth: 0 以保证 baseline 可达）
- `requirements-npu.txt` — NPU-only 依赖增量（含 header + `torch_npu==2.7.1` exact pin）

### Change Log

| 日期 | 作者 | 变更 |
|------|------|------|
| 2026-04-26 | Amelia (Dev Agent) | 实施 Story 1.1：建立 NPU 分支基础设施（lint 脚本 / ignore-list / CI workflow / pre-commit hook / `requirements-npu.txt`），全部 6 个 task 完成，本地三 case 烟测通过，Status: ready-for-dev → review。|
