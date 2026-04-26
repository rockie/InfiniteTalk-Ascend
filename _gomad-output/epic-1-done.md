# Epic 1: NPU 启动与单卡 multitalk Walking Skeleton — 完成日志

本文件汇集 Epic 1 各 story 的完成总结，按时间倒序追加。

---

## 1-3-xfuser-single-card-stub — xfuser 单卡桩化（短路 + 旁路）

**Date:** 2026-04-26

### Story
为 InfiniteTalk 单卡（`world_size==1`）路径短路 xfuser 上下文并行依赖：让 `wan/multitalk.py` 的 `if use_usp:` 分支在单卡时不进入，从而完全规避 `wan/distributed/xdit_context_parallel.py` 的 xfuser top-level imports；同时保留多卡 CUDA 路径与上游字符等价（NFR-05），且所有适配代码集中在 `wan/_npu_adapter/`（NFR-03 单组 git revert 可撤回）。

### Work Done
- 新增 `wan/_npu_adapter/xfuser_stub.py`：导出 2 个公共 helper：
  - `should_short_circuit_xfuser(world_size: int) -> bool`：纯判定，`world_size <= 1` 返回 True，无副作用、无 xfuser import。
  - `get_sequence_parallel_world_size_safe(world_size: int) -> int`：单卡返回 1（不 import xfuser）；多卡 lazy import `xfuser.core.distributed.get_sequence_parallel_world_size` 后透明 passthrough。
- `wan/multitalk.py` (+3 行)：把 `if use_usp:` 改为 `if use_usp and not should_short_circuit_xfuser(_world_size):`；`_world_size = dist.get_world_size() if dist.is_initialized() else 1`（不读 `os.getenv`）；新增 `from wan._npu_adapter.xfuser_stub import …` 在方法体内 lazy。AC-3 物理保证 `use_usp` token 仍是顶层 conjunct，short-circuit 是追加的 `and` term 而非替换。
- 新增 `_gomad-output/implementation-artifacts/smoke_test_1_3_xfuser_stub.py`：5 case dry-run 烟测（无需 xfuser/torch 安装），覆盖 short-circuit True/False、单卡 sys.modules 不污染（AC-1 bright-line 验证 `not any(name.startswith('xfuser') for name in sys.modules)`）、xfuser-absent ImportError 归属、xfuser-present-dist-not-initialized passthrough — 5/5 PASS。
- 留存证据：lint EXIT=0（wan/multitalk.py:6 = Story 1.2 +3 + Story 1.3 +3，命中 +3 lower target，远低 +5 hard cap）；wan/distributed/xdit_context_parallel.py 0/80 zero-touch；`grep "^import xfuser\|^from xfuser" wan/multitalk.py` 0 命中（AC-6 lazy-import 纪律）。

### Known Issues
- 无遗留（0 LOW deferred）。

---

## 1-2-device-flag-and-init-abstraction — 设备 flag 与 init 抽象层

**Date:** 2026-04-26

### Story
为 InfiniteTalk 引入 `--device {cuda,npu}` CLI flag 与设备工厂抽象层，将 NPU 适配代码集中到 `wan/_npu_adapter/`（满足 NFR-03 单组 git revert 可撤回），同时物理保证 CUDA 路径零行为变化（NFR-05），并在 `--device npu + world_size>1` 时 fail-loudly（无 NCCL 静默 fallback）。

### Work Done
- 新增 `wan/_npu_adapter/__init__.py` + `wan/_npu_adapter/device.py`：设备工厂模块，导出 `is_npu / set_device / resolve_torch_device / assert_single_card_or_fail`，集中管理 `torch_npu` lazy import；该目录是 NFR-03 NPU 适配层的物理隔离点。
- `generate_infinitetalk.py` (+12 行)：argparse `--device {cuda,npu}` flag (default=cuda)；启动期调用 `assert_single_card_or_fail` 早于 `dist.init_process_group`，多卡 NPU 抛 `NotImplementedError("Multi-card NPU SP is Phase 2 scope")`；通过工厂调用 `set_device` 替代直接 `torch.cuda.set_device`。
- `wan/multitalk.py` (+3 行)：把 line 157 硬编码 `torch.device(f"cuda:{device}")` 替换为通过 `resolve_torch_device(device_type, device_id)` 工厂解析，保留构造函数 `device: str = "cuda"` 默认（AC-4 显式允许）。
- `tools/check_npu_line_budget.py`：吸收 Story 1.1 LOW #1，新增 5 主路径文件存在性 pre-check — 任一路径被重命名/删除时 EXIT=2 + 清晰错误，杜绝 lint 盲区。
- `_gomad-output/implementation-artifacts/smoke_test_1_2_device_factory.py`：AC-10 dry-run 烟测脚本（无需 NPU 硬件），覆盖 6 个 case：argparse 默认值、CUDA/NPU set_device、torch_npu 缺失友好错误、多卡 NPU 抛错、CUDA 路径不污染 sys.modules['torch_npu']。
- 留存证据：lint gate `EXIT=0`（generate_infinitetalk.py:12 / wan/multitalk.py:3，均远低于 80 行 cap）；`grep "^import torch_npu|^from torch_npu" generate_infinitetalk.py wan/multitalk.py` 0 命中（AC-8 物理保证 lazy import 纪律）；smoke 6/6 PASS；rename smoke EXIT=2。

### Known Issues
- **[LOW]** `wan/_npu_adapter/device.py:_import_torch_npu()` 内有冗余 `import torch` + 误导性注释；功能正确，仅可读性遗留。
- **[LOW]** `Unsupported device '{device}'; expected one of {_VALID_DEVICES}` 错误信息渲染含元组括号；argparse choices 已前置，几乎不可达。
- 已 append 至 `_gomad-output/implementation-artifacts/deferred-work.md` "From Story 1-2" 段。

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
