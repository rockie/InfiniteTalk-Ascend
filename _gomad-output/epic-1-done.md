# Epic 1: NPU 启动与单卡 multitalk Walking Skeleton — 完成日志

本文件汇集 Epic 1 各 story 的完成总结，按时间倒序追加。

---

## 1-1-npu-branch-infrastructure — 创建 NPU 分支基础设施（requirements-npu.txt + lint gate + ignore-list）

**Date:** 2026-04-26

### Story
为 NPU 分支建立 NFR-02 行预算 lint gate（CI + pre-commit 共用）、独立的 `requirements-npu.txt` 与透明化 ignore-list，确保从 day 1 起对 5 个主路径文件强制 ≤80 行增量预算，使后续上游 rebase 可持续。

### Work Done
- 新增 `tools/check_npu_line_budget.py`：单一来源的 NFR-02 行预算检查器，使用 `git diff --numstat <baseline> -- <file>` 第 1 列 (added) 度量；baseline 钉死至 `fd631497254e065777f2b2d0642de3600d674e24`；CI 与 pre-commit 共用此脚本以满足 AC-7 DRY。
- 新增 `tools/npu-line-budget-ignore.txt`：透明化豁免清单（首版仅含说明性头注释，无实际豁免条目；格式 `<file_path> # <rationale>`）。
- 新增 `tools/pre-commit-npu-line-budget.sh`：pre-commit hook 包装脚本，default block 模式，支持 `--no-verify` 紧急旁路（CI gate 仍作为最后防线）。
- 新增 `.github/workflows/npu-line-budget.yml`：CI gate workflow，trigger = `pull_request` + `push`；`fetch-depth: 0` 以保证 `git diff` 可见 baseline。
- 新增 `requirements-npu.txt`：含文件用途头注释 + `torch_npu==2.7.1` 精确 pin；上游 `requirements.txt` 不含 `torch_npu`（已 grep 验证 0 行）。
- AC-5 钉死的 5 个主路径文件 (`wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` / `generate_infinitetalk.py` / `app.py`) 已写入 lint gate 的 tracked 列表，本 story 内 zero-touch；后续 stories (1.2~1.7 / 3.x / 4.x) 为首批消费者。
- 本地烟测三 case 全部通过：6.1 baseline `EXIT=0`；6.2 attention.py +90 行 `EXIT=1` 并打印 fix-paths 提示；6.3 ignore-list 命中后 `EXIT=0`。所有临时改动已 revert，工作树洁净。

### Known Issues
- **[LOW]** `tools/check_npu_line_budget.py` 在 5 个主路径文件被重命名/删除时存在盲区——`git diff --numstat` 对消失旧路径返回 `added=0`，新路径累积改动会绕过 80 行 budget。建议未来加一道"5 个路径必须存在"的健康检查。（已记录 `_gomad-output/implementation-artifacts/deferred-work.md`）
- **[LOW]** `.github/workflows/npu-line-budget.yml` 未声明 `concurrency:` 与 `timeout-minutes:`（卫生项，非功能性）。
- **[LOW]** `_read_ignore_list()` 解析器若 ignore 行的 file_path 自身含字面量 `#` 会被错误截断；当前 5 个钉死路径无 `#`，仅为解析器健壮性遗留。
