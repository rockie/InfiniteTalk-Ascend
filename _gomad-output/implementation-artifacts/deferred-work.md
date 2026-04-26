# 遗留工作清单（Deferred Work Log）

本文件汇集 code review 阶段判定为 **LOW** 严重度、未在当前 story 内即时修复的项目，
等待后续 story 接手或集中清算。每条目格式：

> **[遗留自 <来源 story>]**: <描述> — <严重度>

---

## From Story 1-1 (NPU Branch Infrastructure)

> **[遗留自 1-1-npu-branch-infrastructure]**: `tools/check_npu_line_budget.py` 在 5 个主路径文件被重命名/删除时存在盲区——`git diff --numstat <baseline> -- <old_path>` 对不存在的旧路径返回 `added=0`，新路径下的累积改动会绕过 80 行 budget。理论上 NFR-02 钉死的 5 个路径不应被重命名（重命名本身违反维护性约定），但 lint 脚本未显式 detect 并 fail-loudly。建议未来增加一道"5 个路径必须存在"的健康检查。 — LOW

> **[遗留自 1-1-npu-branch-infrastructure]**: `.github/workflows/npu-line-budget.yml` 未声明 `concurrency:` 与 `timeout-minutes:`。脚本极轻量，超时与并发竞态影响可忽略；属于工作流卫生项。 — LOW

> **[遗留自 1-1-npu-branch-infrastructure]**: `tools/check_npu_line_budget.py:_read_ignore_list()` 用 `line.split("#", 1)[0]` 截断 rationale 时，若文件路径自身包含字面量 `#` 字符会被错误截断。当前 5 个钉死路径无 `#`，且现实工程文件名罕见出现 `#`，此项仅为解析器健壮性遗留。 — LOW

## From Story 1-2 (Device Flag and Init Abstraction)

> **[遗留自 1-2-device-flag-and-init-abstraction]**: `wan/_npu_adapter/device.py:_import_torch_npu()` 内部第二行 `import torch` 实际为 no-op（torch 已在模块顶层 import，cache 命中）。让 `torch.npu` 属性出现的真实机制是 `import torch_npu` 的 monkey-patch side-effect；当前注释"再次 import torch 以确保 `torch.npu` 属性已注入（顺序敏感）"会让后续维护者误判语义。建议未来 cleanup：删除冗余的第二行 `import torch` 与误导性注释，或改写注释明确"`import torch_npu` 触发 monkey-patch；`torch.npu` 即被注入"。功能正确，无运行期影响。 — LOW

> **[遗留自 1-2-device-flag-and-init-abstraction]**: `wan/_npu_adapter/device.py` 中 `set_device` / `resolve_torch_device` 的非法 device 错误信息 `f"Unsupported device '{device}'; expected one of {_VALID_DEVICES}"` 会渲染成 `expected one of ('cuda', 'npu')`（带元组括号与引号）；可读性轻微下降。argparse `choices` 已在 CLI 入口前置防御，本错误几乎不会被用户看到（仅 internal misuse 场景）。建议未来 cleanup：改为 `expected one of: cuda, npu`。 — LOW

