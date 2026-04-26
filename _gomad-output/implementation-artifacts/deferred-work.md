# 遗留工作清单（Deferred Work Log）

本文件汇集 code review 阶段判定为 **LOW** 严重度、未在当前 story 内即时修复的项目，
等待后续 story 接手或集中清算。每条目格式：

> **[遗留自 <来源 story>]**: <描述> — <严重度>

---

## From Story 1-1 (NPU Branch Infrastructure)

> **[遗留自 1-1-npu-branch-infrastructure]**: `tools/check_npu_line_budget.py` 在 5 个主路径文件被重命名/删除时存在盲区——`git diff --numstat <baseline> -- <old_path>` 对不存在的旧路径返回 `added=0`，新路径下的累积改动会绕过 80 行 budget。理论上 NFR-02 钉死的 5 个路径不应被重命名（重命名本身违反维护性约定），但 lint 脚本未显式 detect 并 fail-loudly。建议未来增加一道"5 个路径必须存在"的健康检查。 — LOW

> **[遗留自 1-1-npu-branch-infrastructure]**: `.github/workflows/npu-line-budget.yml` 未声明 `concurrency:` 与 `timeout-minutes:`。脚本极轻量，超时与并发竞态影响可忽略；属于工作流卫生项。 — LOW

> **[遗留自 1-1-npu-branch-infrastructure]**: `tools/check_npu_line_budget.py:_read_ignore_list()` 用 `line.split("#", 1)[0]` 截断 rationale 时，若文件路径自身包含字面量 `#` 字符会被错误截断。当前 5 个钉死路径无 `#`，且现实工程文件名罕见出现 `#`，此项仅为解析器健壮性遗留。 — LOW

