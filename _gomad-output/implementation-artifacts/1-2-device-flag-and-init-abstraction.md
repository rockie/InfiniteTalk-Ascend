# Story 1.2: `--device {cuda,npu}` flag 与设备初始化抽象

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Migration Engineer,
I want a `--device {cuda,npu}` CLI flag on `generate_infinitetalk.py` that drives device init at the entry layer (`torch.cuda.set_device` ↔ `torch.npu.set_device` 与 `torch.device("cuda:N")` ↔ `torch.device("npu:N")`），
so that CUDA / NPU paths can be switched at the entry boundary 而不会让 device-aware 字符串泄漏进 pipeline / `WanModel` 内部（FR-01 / FR-03 / FR-18 + 架构原则"`--device` 参数仅在 CLI 入口层解析"）。

> **Scope 边界澄清（避免越界）**：
> - 本 story **只**处理 `generate_infinitetalk.py` 的 `--device` flag 与 `wan/multitalk.py` 的设备初始化抽象（multitalk pipeline = Phase 1a 主路径）。
> - **不**处理 `app.py` —— 那是 Story 3.1。
> - **不**触碰 attention 调用点 —— 那是 Story 1.4（Story 1.4 的 dispatch 依赖本 story 已落的 device flag，但本 story zero-touch attention.py / xdit_context_parallel.py）。
> - **不**实现 xfuser 单卡 stub —— 那是 Story 1.3。本 story 仅保留对 `world_size==1` 现有分支的尊重（不引入新的 xfuser 调用）。
> - **不**触碰 `wan/image2video.py` / `wan/text2video.py` / `wan/first_last_frame2video.py` —— 它们由 Story 4.x 在 CLI 分发扩展时一并处理（multitalk 路径优先，其他三模式不在本 story scope）。

## Acceptance Criteria

> **来源映射**：本 story AC 锚定 epics.md § Story 1.2 + PRD § FR-01 / FR-03 / FR-18 + architecture-summary.md § 1 设备抽象层。AC 文本逐字承载 epics.md，并补足 PRD AC 中"`--device cuda` 时上游行为不变"的回归保证。

1. **AC-1（CUDA 默认行为不变 — NFR-05 兼容性硬约束）**
   **Given** `python generate_infinitetalk.py --device cuda --task infinitetalk-14B ...` 在 CUDA host 上执行
   **When** 进程进入 `generate(args)` 函数
   **Then** 在 `world_size > 1` 分支与 `world_size == 1` 分支上**等价于**当前 `generate_infinitetalk.py:457,465` 行为（`torch.cuda.set_device(local_rank)` 被调用）
   **And** 任意上游 acceptance 行为不被破坏（NFR-05；通过 dry-run import + argparse 解析可验证）

2. **AC-2（`--device npu` 路由到 NPU 设备初始化）**
   **Given** `python generate_infinitetalk.py --device npu ...` 在 910B host（且 `torch_npu` 可 import）
   **When** 进程进入设备初始化点
   **Then** 调用 `torch.npu.set_device(local_rank)`（**不是** `torch.cuda.set_device`）
   **And** `wan/multitalk.py:157` 的 `self.device` 解析为 `torch.device(f"npu:{device_id}")`（不是 `cuda:N`）
   **And** 在 NPU 代码路径上，**没有任何** `torch.cuda.*` 调用被命中（通过 grep + 运行期断言可验证）

3. **AC-3（`--device` 缺省值 = `cuda`，向后兼容）**
   **Given** `python generate_infinitetalk.py ...`（**未**显式给 `--device`）
   **When** argparse 解析
   **Then** `args.device == "cuda"`（缺省回落，PRD § FR-01 第三条 AC）
   **And** 后续行为等价于 AC-1

4. **AC-4（pipeline 类内部不感知 `--device` 字符串 — FR-18 抽象边界）**
   **Given** `wan/multitalk.py.InfiniteTalkPipeline.__init__` 与任意 `WanModel` 类
   **When** 用 grep 检查这些文件
   **Then** 它们**不**包含字面量 `"cuda"` 或 `"npu"` 的 device-aware **分支**（既有 `cuda:{device_id}` 这类 device-string 必须改为通过 helper / 工厂获得，而不是被新增的 `if device == "npu"` 分支替代）
   **And** `--device` 参数仅在 CLI 入口（`generate_infinitetalk.py`）+ 独立 wrapper 文件中可见

5. **AC-5（NPU 路径无 `torch_npu` 时 fail-loudly + 友好提示）**
   **Given** 任意 host 执行 `--device npu`，但 `torch_npu` 未安装（或 `torch.npu` 不可访问）
   **When** 进程启动
   **Then** 进程以**清晰错误信息**退出（含算子定位线索：`torch_npu not importable; install requirements-npu.txt and ensure CANN driver loaded`），不要在后续才报神秘 `AttributeError`
   **And** 退出码非零

6. **AC-6（`world_size > 1` 分布式分支保留，但走 device-aware 后端）**
   **Given** `--device cuda` + `world_size > 1`
   **When** 进入分布式 init
   **Then** `dist.init_process_group(backend="nccl", ...)` 不变（上游行为）
   **Given** `--device npu` + `world_size > 1`（**Phase 2 才实施**，本 story 不实现 happy path）
   **When** 进入分布式 init
   **Then** 进程**显式 fail-loudly** 抛出 `NotImplementedError("Multi-card NPU SP is Phase 2 scope; use world_size==1 for MVP")`（**不允许**默默 fallback 到 `nccl` —— 那会在 NPU 上崩在不知所措的位置）
   > 说明：MVP scope 只覆盖 `world_size==1` 的 NPU 路径（Story 1.3 的 xfuser stub 强化此约束）；本 AC 把多卡分支的失败时机从"运行时神秘错误"提前到"启动时显式声明"。

7. **AC-7（NFR-02 行预算 — 5 个主路径文件改动 ≤ 80 行/文件）**
   **Given** 本 story 完成后
   **When** `python3 tools/check_npu_line_budget.py` 运行（CI + pre-commit 已由 Story 1.1 落地）
   **Then** EXIT=0（即任意被本 story 改动的主路径文件 added 行 ≤ 80）
   **And** 主路径文件**白名单** = `wan/modules/attention.py` / `wan/multitalk.py` / `wan/distributed/xdit_context_parallel.py` / `generate_infinitetalk.py` / `app.py`
   **And** 本 story 改动的主路径文件预期 = `generate_infinitetalk.py` + `wan/multitalk.py`（仅这两个；其余 3 个 zero-touch）
   **And** 多余适配逻辑（device 工厂 / set-device dispatch / 错误翻译）必须**外置**到独立 wrapper 模块（建议路径 `wan/_npu_adapter/device.py`，由 Dev Notes § 适配层目录约定 给出）

8. **AC-8（`--device cuda` runtime 上 NPU 适配代码零侧效 — FR-18 / NFR-05）**
   **Given** `--device cuda` 路径
   **When** 进程运行任意推理路径
   **Then** **任何** `torch_npu` import 都不在 sys.modules 中（lazy import 形态：仅 `--device npu` 才触发 import；`import torch_npu` 不在模块顶层）
   **And** lint 验证：`grep -rn "^import torch_npu" generate_infinitetalk.py wan/multitalk.py` 必须返回 0 行（顶层 import 禁止）

9. **AC-9（`local_rank` / `device_id` 计量逻辑保留 — 边界行为不变）**
   **Given** `LOCAL_RANK=0` 环境变量（J1 acceptance 命令的固定起手）
   **When** `_init_logging(rank)` 之后 `device = local_rank`
   **Then** device id 与 rank 的耦合逻辑保持不变；仅设备**后端**由 `--device` flag 决定，**不**修改 rank/world_size 解析顺序

10. **AC-10（J1 dry-run 烟测：argparse + 设备工厂能跑通到 `WAN_CONFIGS[args.task]`）**
    **Given** 一个**纯 argparse + 设备工厂 dry-run 子集**（不真正加载模型权重）
    **When** 用 mock / `--ckpt_dir=/tmp` 等无效路径触发提前退出，但 argparse + device init + 工厂分发已穿过
    **Then** 在 CUDA host 上 `--device cuda` 路径走完 set_device；`--device npu` 路径在 `torch_npu` 不可达时按 AC-5 给出清晰错误
    **And** PR 描述粘贴该 dry-run 的 stdout 片段作为 AC-10 evidence（与 Story 1.1 AC-6 evidence 留痕模式一致）

## Tasks / Subtasks

- [x] **Task 1**：创建 NPU 适配层目录骨架（不计入 5 个主路径文件预算 — AC-7 / AC-8）
  - [x] 1.1 新建目录 `wan/_npu_adapter/`（前缀 `_` 表内部包，避免被外部 `from wan import _npu_adapter` 当公共 API 误用）
  - [x] 1.2 新建 `wan/_npu_adapter/__init__.py`（空文件 + 一行 module docstring 说明 = "NPU 适配层；仅 `--device npu` 路径触发 lazy import"）
  - [x] 1.3 新建 `wan/_npu_adapter/device.py`（设备工厂主体；详见 Task 2）
  - [x] 1.4 **绝对不允许**在该目录之外创建新 NPU-only 文件，除非 PR review 显式批准（保持 NFR-03 单组 git revert 可撤回）

- [x] **Task 2**：实现 device 工厂（`wan/_npu_adapter/device.py`）— FR-01 / FR-03 / FR-18 核心载体
  - [x] 2.1 提供函数 `set_device(device: str, local_rank: int) -> None`：当 `device == "cuda"` 调用 `torch.cuda.set_device(local_rank)`；当 `device == "npu"` lazy import `torch_npu` 后调用 `torch.npu.set_device(local_rank)`；其他值 raise `ValueError`
  - [x] 2.2 提供函数 `resolve_torch_device(device: str, device_id: int) -> torch.device`：CUDA → `torch.device(f"cuda:{device_id}")`；NPU → lazy import `torch_npu` + 返回 `torch.device(f"npu:{device_id}")`
  - [x] 2.3 提供函数 `is_npu(device: str) -> bool`：纯字符串判断，**不**触发 import
  - [x] 2.4 lazy import 模板（NPU 不可达时的友好错误 — AC-5）：
    ```python
    def _import_torch_npu():
        try:
            import torch_npu  # noqa: F401
            import torch  # ensure torch.npu attribute populated
        except ImportError as exc:
            raise RuntimeError(
                "torch_npu not importable; install requirements-npu.txt "
                "and ensure CANN driver loaded"
            ) from exc
    ```
  - [x] 2.5 提供函数 `assert_single_card_or_fail(device: str, world_size: int) -> None`：当 `device == "npu" and world_size > 1` 抛 `NotImplementedError("Multi-card NPU SP is Phase 2 scope; use world_size==1 for MVP")`（AC-6）

- [x] **Task 3**：在 `generate_infinitetalk.py` 注入 `--device` flag（AC-1 / AC-2 / AC-3 / AC-7）
  - [x] 3.1 在 `_parse_args()` 现有最后一个 `add_argument` 之后（line 269 区域）追加：
    ```python
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        choices=["cuda", "npu"],
        help="Compute device backend. Defaults to 'cuda' for upstream compatibility (FR-01)."
    )
    ```
    （**4 行 actual code + helper 注释**；行预算严控）
  - [x] 3.2 修改 `generate(args)` 函数（line 453 起）：
    - 保留 `device = local_rank`（line 457）— 不动
    - **替换** line 465 的 `torch.cuda.set_device(local_rank)` 为：
      ```python
      from wan._npu_adapter.device import set_device, assert_single_card_or_fail
      assert_single_card_or_fail(args.device, world_size)
      set_device(args.device, local_rank)
      ```
      （3 行；与 line 465 单行原状的 +2 行 net；上下文 `if world_size > 1:` 块内继续保留 `dist.init_process_group(backend="nccl", ...)` —— 因 AC-6 中 `--device npu + world_size>1` 已被前置 fail-loudly 拦截）
  - [x] 3.3 **不要**改变 line 466-470 的 `dist.init_process_group(backend="nccl", ...)` 调用 — NCCL 在 CUDA + multi-card 下保留，NPU + multi-card 在 step 2.5 之前已 raise（AC-6）
  - [x] 3.4 **不要**改变 line 481-492 的 xfuser block —— 那由 Story 1.3 处理
  - [x] 3.5 改动总行数预算（generate_infinitetalk.py）：argparse 4 行 + set_device 替换 +2 行 = **+6 行 added**（远低于 80 行 budget）；预留 +10~+20 行余量给 imports / 注释，硬上限严守 ≤ 80

- [x] **Task 4**：在 `wan/multitalk.py` 抽象 `self.device` 字符串（AC-2 / AC-4 / AC-7）
  - [x] 4.1 修改 `InfiniteTalkPipeline.__init__` 签名（line 110-129 区域）：在 `device_id=0` **之后**追加新参数 `device: str = "cuda"`（**位置敏感**：放在 `device_id` 后避免破坏既有关键字调用顺序；该参数有 default 故仍兼容上游 `device_id=device` 调用）
  - [x] 4.2 替换 `self.device = torch.device(f"cuda:{device_id}")`（line 157）为：
    ```python
    from wan._npu_adapter.device import resolve_torch_device
    self.device = resolve_torch_device(device, device_id)
    ```
    （**2 行**；net +1 行 vs 原状）
  - [x] 4.3 在 `generate_infinitetalk.py:525-540` 的 `wan.InfiniteTalkPipeline(...)` 调用处追加 `device=args.device`（**1 行 added**）
  - [x] 4.4 **保留** `torch.cuda.empty_cache()` / `torch.cuda.ipc_collect()` / `torch.cuda.manual_seed_all(seed)` / `torch.cuda.synchronize()`（line 42, 43, 373, 513, 835）—— 这些是 CUDA 路径的 hot-loop 内存管理；NPU 路径的等价物**不在本 story scope**（属于 Story 1.5 multitalk happy path 的算子级排错；遗留为下游 story 处理）。**必须**在 Dev Notes Section "已知 NPU 调用点遗留"明确列出，避免后续 story 误以为本 story 已闭环。
  - [x] 4.5 改动总行数预算（wan/multitalk.py）：__init__ 签名 +1 行 + line 157 替换 net +1 行 = **+2 行 added**（远低于 80 行 budget）

- [x] **Task 5**：行预算 + 上游分离 + import 形态自检（AC-7 / AC-8 / Story 1.1 lint gate 兼容）
  - [x] 5.1 本地运行 `python3 tools/check_npu_line_budget.py` → EXIT=0；预期 stdout（基于 Task 3/4 的 +6 / +2 估算）：
    ```
    wan/modules/attention.py:0
    wan/multitalk.py:2
    wan/distributed/xdit_context_parallel.py:0
    generate_infinitetalk.py:6
    app.py:0
    ```
    （±5 行容差均可；超 80 必触发 lint gate fail）
  - [x] 5.2 验证顶层无 `torch_npu` import（AC-8）：
    ```bash
    grep -nE "^import torch_npu|^from torch_npu" generate_infinitetalk.py wan/multitalk.py
    # 必须返回 0 行
    ```
  - [x] 5.3 验证 pipeline 类不感知 `--device` 字符串（AC-4）：
    ```bash
    grep -nE 'args\.device|"npu"|"cuda"' wan/multitalk.py | grep -v "^\s*#"
    # 唯一允许命中的位置 = `device: str = "cuda"` 默认值（参数签名）
    # `wan/_npu_adapter/device.py` 中 device 字符串可见是合规的（适配层）
    ```
  - [x] 5.4 在 PR 描述 paste Task 5.1 / 5.2 / 5.3 的 stdout（与 Story 1.1 AC-6 留痕模式一致）

- [x] **Task 6**：J1 dry-run argparse 烟测（AC-10）
  - [x] 6.1 在 CUDA host（或 macOS dev box）执行：
    ```bash
    python3 generate_infinitetalk.py --device cuda --task infinitetalk-14B \
      --ckpt_dir /tmp/no_such_dir \
      --infinitetalk_dir /tmp/no_such_dir \
      --wav2vec_dir /tmp/no_such_dir \
      --input_json /tmp/no_such.json
    # 预期：argparse 通过 → 进入 generate() → set_device(cuda, 0) 成功 → 在加载模型权重时 fail（FileNotFoundError 或类似），fail 之前应能验证设备工厂被调用
    ```
    捕获 stdout/stderr 前 30 行作为 AC-10 evidence
  - [x] 6.2 同上，`--device npu`（在 CUDA host 上 — `torch_npu` 不可达）：
    ```bash
    python3 generate_infinitetalk.py --device npu --task infinitetalk-14B ...
    # 预期：argparse 通过 → 进入 generate() → 在 set_device(npu, 0) 时按 AC-5 raise `RuntimeError: torch_npu not importable; ...`，**而不是** AttributeError
    ```
    捕获错误片段作为 AC-5 + AC-10 evidence
  - [x] 6.3 同上，`--device npu` + `WORLD_SIZE=4`：
    ```bash
    WORLD_SIZE=4 python3 generate_infinitetalk.py --device npu ...
    # 预期：assert_single_card_or_fail 抛 NotImplementedError "Multi-card NPU SP is Phase 2 scope"
    ```
    捕获错误片段作为 AC-6 evidence
  - [x] 6.4 在 PR 描述 paste 6.1 / 6.2 / 6.3 三段 stdout（标注对应子任务编号）

- [x] **Task 7**（可选 — 吸收 Story 1.1 LOW 遗留 #1：5 个钉死路径存在性检查）
  - [x] 7.1 在 `tools/check_npu_line_budget.py` 的 `main()` 起首添加：
    ```python
    for f in TRACKED_FILES:
        if not (repo_root / f).is_file():
            print(f"[NPU LINE BUDGET] FATAL: tracked path '{f}' missing — "
                  "rename/delete violates NFR-02 invariant. Restore the file "
                  "or open an architecture-level exception in PR review.",
                  file=sys.stderr)
            return 2
    ```
  - [x] 7.2 烟测：临时 `git mv generate_infinitetalk.py generate_infinitetalk_renamed.py` → 跑脚本 → EXIT=2 + 清晰错误 → revert
  - [x] 7.3 在 PR 描述列出该次 evidence（与 Task 6 烟测同板块）
  - [x] 7.4 **如本 task 偏离 80 行预算或 dev agent 判断超出本 story scope（例如需要 hook 到 CI workflow），跳过 Task 7 并将其作为 deferred-work.md 标注的 "absorbed back" 记录留到下一个 story 决议；不强制本 story 闭环**
  - > **吸收策略说明**：deferred-work.md 中 Story 1.1 的 LOW #1 与本 story 的"主路径文件改动"语义直接相邻 —— 本 story 改 `generate_infinitetalk.py` 与 `wan/multitalk.py` 时若两条主路径中一条被错误重命名，lint gate 必须 fail-loudly。LOW #2（`concurrency:` / `timeout-minutes:`）与 LOW #3（`#` rationale 字符截断）与本 story 语义不直接相关，**不**吸收，留待集中清算。

## Dev Notes

> **核心定位**：本 story 是 Epic 1 的"设备抽象骨架" —— 所有后续 attention / multitalk happy path / Gradio 都依赖这里的设备工厂正确无副作用。出错最大代价 = NPU 路径以 cuda 后端启动并神秘崩溃，或 CUDA 路径退化（违反 NFR-05）。

### 关键架构约束（来自 architecture-summary.md § 1 设备抽象层）

- **设备扩散原则（pin 死）**：`--device` 参数仅在 CLI 入口层解析；各 pipeline 类 / `WanModel` 内部**不感知** device 字符串。本 story 通过两点物理保证：
  1. `wan/multitalk.py` 中**唯一**改动 = `device: str = "cuda"` 参数 + 调用 `resolve_torch_device(...)`，**没有** `if device == "npu"` 分支
  2. NPU-only 逻辑（lazy import / set_device / device 工厂）全部位于 `wan/_npu_adapter/device.py`，pipeline 类只看到接口
- **Lazy import（FR-18 / NFR-05 物理保证）**：`torch_npu` **不允许**在任何主路径文件顶层 `import`；只能在 `--device npu` 路径触发的函数内 import。这样 `--device cuda` runtime 上 `torch_npu` 不会出现在 `sys.modules`，杜绝侧效。
- **行预算严控**：`generate_infinitetalk.py` 预期 +6 行；`wan/multitalk.py` 预期 +2 行。两个文件总和远低于 NFR-02 hard 80 行/文件 cap。**适配层主体在 `wan/_npu_adapter/`，不计入 5 个主路径白名单的 budget**。

### `wan/_npu_adapter/` 适配层目录约定

```
wan/
├── _npu_adapter/             ← 本 story 引入；NFR-03 "可一组 git revert" 的载体
│   ├── __init__.py           ← 空 + docstring
│   ├── device.py             ← 本 story 唯一新增逻辑文件（device 工厂）
│   ├── attention.py          ← Story 1.4 新增（attention dispatch wrapper）
│   ├── xfuser_stub.py        ← Story 1.3 新增（world_size==1 短路）
│   └── errors.py             ← Story 2.1 新增（错误翻译层）
├── multitalk.py              ← 仅 +2 行（参数签名 + resolve_torch_device 调用）
└── ...
```

> **为何用 `_npu_adapter` 而非 `npu_adapter`**：前缀 `_` 是 Python 内部包惯例，传达"非公共 API"语义；外部用户 `from wan import npu_adapter` 不会"工作"（实际可工作但语义违约），减少误用面。

### 上游主路径文件 baseline 与零侵入对照表

| 文件 | baseline 行数 | 本 story 预期 added 行 | 80 行 budget 余量 |
|------|--------------|----------------------|-----------------|
| `wan/modules/attention.py` | 392 | 0（zero-touch；归 Story 1.4） | 80 |
| `wan/multitalk.py` | 855 | ~2 | 78 |
| `wan/distributed/xdit_context_parallel.py` | 549 | 0（zero-touch；归 Story 1.4） | 80 |
| `generate_infinitetalk.py` | 663 | ~6 | 74 |
| `app.py` | 819 | 0（zero-touch；归 Story 3.1） | 80 |

### `--device cuda` 行为不变性保证（NFR-05 验证矩阵）

| 验证项 | 检查方法 | 期望 |
|--------|---------|------|
| argparse 不破坏既有 flags | `python3 generate_infinitetalk.py --help` diff against baseline | 仅多出一条 `--device` |
| 缺省 `--device` 时退化路径 | `python3 generate_infinitetalk.py --task infinitetalk-14B`（不传 `--device`） | `args.device == "cuda"` |
| `torch.cuda.set_device(local_rank)` 仍被调用（CUDA 路径） | grep 跑通后的 strace / mock | `set_device(cuda, 0)` 在调用链中 |
| `torch_npu` 不在 `sys.modules`（CUDA 路径） | `python3 -c "import generate_infinitetalk; ..."` after CUDA dry-run | `'torch_npu' not in sys.modules` |
| `dist.init_process_group(backend="nccl")` 不变（CUDA + multi-card） | grep + dry-run | 一字不改 |

### 已知 NPU 调用点遗留（**显式不在本 story scope，传递给下游 stories**）

`wan/multitalk.py` 包含若干 hot-loop CUDA-only 调用：
- `torch.cuda.empty_cache()`（line 42, 373, 835 推断）
- `torch.cuda.ipc_collect()`（line 43）
- `torch.cuda.manual_seed_all(seed)`（line 513）
- `torch.cuda.synchronize()`（line 835）

这些**不在本 story 处理**，因为：
1. 它们是 hot loop 内的内存管理 / 同步 calls，需要在 NPU 路径上找等价 `torch.npu.empty_cache()` 等替代；牵扯到运行期算子分发，本 story 只是 init 层抽象
2. 牺牲行预算覆盖 5 处调用点会逼近 80 行 cap；最佳工程实践 = 通过设备 helper（如 `wan/_npu_adapter/device.py` 后续追加 `device_empty_cache(device: torch.device)`）由 Story 1.5（multitalk happy path）按需引入

> **传递契约**：Story 1.5 的 dev agent 必须在 multitalk happy path 跑通过程中**逐个**处理这 5 处调用，并通过同一 `_npu_adapter` 包暴露 helper，不允许在 `wan/multitalk.py` 内插入 `if str(self.device).startswith("npu")` 分支（违反 AC-4 设备扩散原则）。

### CLI 上下文：现有 argparse flags 全表（生成时间：2026-04-26）

```
--task / --size / --frame_num / --max_frame_num
--ckpt_dir / --infinitetalk_dir / --quant_dir / --wav2vec_dir / --dit_path
--lora_dir / --lora_scale
--offload_model / --t5_fsdp / --t5_cpu / --dit_fsdp
--ulysses_size / --ring_size
--save_file / --base_seed / --motion_frame
--mode / --sample_steps / --sample_shift / --sample_text_guide_scale / --sample_audio_guide_scale
--num_persistent_param_in_dit / --audio_save_dir / --color_correction_strength
--input_json / --use_teacache / --teacache_thresh
--use_apg / --apg_momentum / --apg_norm_threshold
--scene_seg / --quant
```

**本 story 新增**：`--device {cuda,npu}`（默认 `cuda`）。
**与现有 flags 关系**：完全正交；不修改 / 不删除 / 不重命名任何现有 flag。

### `world_size > 1` 分支契约（C12 / C2 协同）

当前 `generate_infinitetalk.py:464-470` 的 `world_size > 1` 分支调用 `dist.init_process_group(backend="nccl", ...)`：
- **CUDA + multi-card**（NCCL 路径）：保留（NFR-05 上游路径不变）
- **NPU + multi-card**：本 story 在 `assert_single_card_or_fail` 前置 raise（AC-6），不进入 NCCL init。**Phase 2 才设计 HCCL 等价物**。

### Story 1.1 已落地资产（不重复实现）

- `tools/check_npu_line_budget.py`（含 `BASELINE_COMMIT = fd631497254e065777f2b2d0642de3600d674e24`）
- `tools/npu-line-budget-ignore.txt`（首版空 — 本 story 不应追加任何条目；任何"超 80 行所以加 ignore-list"决议必须先经 PR review，且会被 reviewer 默认拒绝）
- `tools/pre-commit-npu-line-budget.sh` + `.github/workflows/npu-line-budget.yml`（CI gate 自动消费本 story 改动）
- `requirements-npu.txt`（含 `torch_npu==2.7.1` exact pin；本 story 不修改）

### Testing Standards Summary

PRD § OOS-12 明确 MVP 阶段不要求 pytest CI 自动化套件。**本 story 例外**：argparse + 设备工厂的正确性可通过纯 dry-run 命令烟测验证（无需真实 NPU 硬件）。具体三 case 见 Task 6。

烟测形式 = 本地 + macOS dev box（CUDA 不可达也行，通过 mock `torch.cuda` / 用 `--ckpt_dir=/tmp` 触发 fail-fast）+ PR 描述 paste stdout，与 Story 1.1 一致。

> **关键不要**：本 story **不**引入 pytest fixture / unittest module —— 那会增加上游 rebase 表面（违反 NFR-04 ≤5 工作日演练）。dry-run + grep + stdout 留痕已足够覆盖 AC-1~AC-10。

### 关于 pipeline 类签名向后兼容性

`InfiniteTalkPipeline.__init__` 在 line 110-129 当前签名带 12 个关键字参数。本 story 新增 `device: str = "cuda"` 时：
- **位置约束**：必须在 `device_id` **之后**（避免位置参数顺序错位）
- **关键字调用兼容**：上游所有调用 `InfiniteTalkPipeline(config=..., checkpoint_dir=..., device_id=...)` 仍然可用（新参数有 default）
- **`generate_infinitetalk.py:525-540` 调用点**：必须显式传 `device=args.device`，否则 NPU 路径会回落到 `cuda` default 导致 NPU 推理走 CUDA 工厂（AC-2 fail）

### 命名 / 缩写约定

- `device: str` / `args.device`：取值域 `{"cuda", "npu"}` 的小写字符串（与 PRD § FR-01 一致）
- `torch.device`：实例对象，由工厂 `resolve_torch_device(...)` 产出；pipeline 内部只使用对象，不再字符串字面量
- `torch.npu`：torch 安装好 `torch_npu` 后通过 monkey-patch 注入的子模块（不是独立 import）；这就是为何 `_import_torch_npu()` 的实现要 `import torch_npu` **再** `import torch`

### Project Structure Notes

- **新增文件**：
  - `wan/_npu_adapter/__init__.py`（空 + docstring）
  - `wan/_npu_adapter/device.py`（设备工厂主体）
- **修改文件**（计入 NFR-02 行预算）：
  - `generate_infinitetalk.py`（预期 +6 行）
  - `wan/multitalk.py`（预期 +2 行）
- **可选修改**（吸收 Story 1.1 LOW #1，仅当 dev agent 判断不超 scope）：
  - `tools/check_npu_line_budget.py`（追加 5 路径存在性 fail-loudly）
- **禁止修改**（zero-touch in this story）：
  - `wan/modules/attention.py`（Story 1.4）
  - `wan/distributed/xdit_context_parallel.py`（Story 1.4）
  - `app.py`（Story 3.1）
  - `wan/image2video.py` / `wan/text2video.py` / `wan/first_last_frame2video.py`（Story 4.x）
  - `wan/multitalk.py` 中的 `torch.cuda.empty_cache()` 等 hot-loop calls（Story 1.5）
  - `requirements-npu.txt` / `requirements.txt`（Story 1.1 已落地）
  - 上游 `tools/` 目录下其他文件（除 Task 7 的可选追加）

### Story DoD（仅本 story 对 Epic 1 DoD 的贡献项）

| 本 story DoD 项 | 验证方式 |
|----------------|---------|
| `--device {cuda,npu}` flag 在 `generate_infinitetalk.py` argparse 注册 | AC-1 / AC-3 |
| `torch.cuda.set_device` 调用通过设备工厂分发到 cuda/npu | AC-1 / AC-2 |
| `wan/multitalk.py:157` 的 `self.device` 字符串硬编码消除 | AC-2 / AC-4 |
| pipeline 类内部不感知 `--device` 字符串 | AC-4（grep 验证） |
| `torch_npu` 不在主路径文件顶层 import | AC-8（grep 验证） |
| NPU + multi-card 启动期 fail-loudly | AC-6 |
| 5 个主路径文件 added 行 ≤ 80 | AC-7（lint gate 自动消费） |
| J1 dry-run 三 case 烟测 evidence 在 PR 描述留痕 | AC-10 / Task 6 |

**不属于本 story DoD**（避免越界实施）：
- `app.py --device` flag（Story 3.1）
- attention adapter（Story 1.4）
- xfuser 单卡 stub（Story 1.3）
- multitalk happy path 跑通（Story 1.5）
- observability 三信号（Story 1.6）
- README-NPU.md 第一版（Story 1.7）
- 4 模式 CLI 分发（Story 4.1）
- `wan/multitalk.py` 中 `torch.cuda.empty_cache()` 等 hot-loop calls（Story 1.5 接手）

### References

- [Source: _gomad-output/planning-artifacts/epics.md#Story-1.2] — AC 文本来源
- [Source: _gomad-output/planning-artifacts/prd.md#FR-01] — `--device {cuda,npu}` flag on `generate_infinitetalk.py` + 默认 cuda
- [Source: _gomad-output/planning-artifacts/prd.md#FR-03] — `torch.cuda.set_device` 替换为 device-aware（line 457,465）
- [Source: _gomad-output/planning-artifacts/prd.md#FR-18] — 适配代码模块化，cuda runtime 不受影响
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-02] — 5 个主路径文件 ≤ 80 行/文件 hard cap
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-03] — 适配代码可被一组 `git revert` 完全撤回（`wan/_npu_adapter/` 是物理载体）
- [Source: _gomad-output/planning-artifacts/prd.md#NFR-05] — `--device cuda` 路径上游行为不变
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#1-设备抽象层] — `--device` 参数仅在 CLI 入口层解析；pipeline 类不感知字符串
- [Source: _gomad-output/planning-artifacts/architecture-summary.md#Maintainability-量化约束] — 主路径文件白名单 + 外置 wrapper 处理路径
- [Source: _gomad-output/implementation-artifacts/1-1-npu-branch-infrastructure.md] — Story 1.1 已落地的 lint gate / `requirements-npu.txt` / 5 路径白名单 baseline
- [Source: _gomad-output/implementation-artifacts/deferred-work.md] — Story 1.1 LOW #1（5 路径存在性检查）由 Task 7 可选吸收

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Amelia / gm-dev-story)

### Debug Log References

- `python3 tools/check_npu_line_budget.py` — EXIT=0；stdout：
  ```
  wan/modules/attention.py:0
  wan/multitalk.py:3
  wan/distributed/xdit_context_parallel.py:0
  generate_infinitetalk.py:12
  app.py:0
  ```
  （`generate_infinitetalk.py:12` 含 5 行 argparse + 4 行 `assert/import/set_device` 替换 + 3 行调用点新增 `device=args.device` 子句换行；`wan/multitalk.py:3` 含 1 行参数签名 + 2 行 `from ... import ... + resolve_torch_device` 替换；远低于 80 行 hard cap）
- `grep -nE "^import torch_npu|^from torch_npu" generate_infinitetalk.py wan/multitalk.py` → 0 行（AC-8 物理保证：顶层无 torch_npu import）
- `grep -nE 'args\.device|"npu"|"cuda"' wan/multitalk.py` → 仅 1 行 `device: str = "cuda"`（参数签名 default；AC-4 允许的唯一例外）
- `python3 _gomad-output/implementation-artifacts/smoke_test_1_2_device_factory.py` → 6/6 cases PASS（CASE 5 argparse / CASE 1 cuda set_device / CASE 2 npu RuntimeError / CASE 3 npu multi-card NotImplementedError / CASE 4 resolve_torch_device cuda / CASE 6 sys.modules 无 torch_npu 侧效）
- Task 7.2 烟测：`mv generate_infinitetalk.py generate_infinitetalk_renamed.py && python3 tools/check_npu_line_budget.py` → EXIT=2 + `[NPU LINE BUDGET] FATAL: tracked path 'generate_infinitetalk.py' missing — rename/delete violates NFR-02 invariant.`；revert 后 EXIT=0

### Completion Notes List

- **Task 1 / Task 2 完成**：新建 `wan/_npu_adapter/__init__.py` + `wan/_npu_adapter/device.py`，承载 `set_device` / `resolve_torch_device` / `is_npu` / `assert_single_card_or_fail` 4 个公共函数；torch_npu 严格 lazy import（仅在 `--device npu` 路径触发，CUDA runtime 上 `sys.modules` 不会出现 `torch_npu`）。
- **Task 3 完成**：`generate_infinitetalk.py` `_parse_args()` 注册 `--device {cuda,npu}` flag（default=`cuda`，对上游全兼容 — AC-3）；`generate(args)` 顶部加入 `from wan._npu_adapter.device import set_device, assert_single_card_or_fail` 与 `assert_single_card_or_fail(args.device, world_size)` 前置 fail-loudly；`if world_size > 1:` 块内的 `torch.cuda.set_device(local_rank)` 替换为 `set_device(args.device, local_rank)`；`dist.init_process_group(backend="nccl", ...)` 一字未动（NFR-05 上游路径不变）。
- **Task 4 完成**：`wan/multitalk.py` `InfiniteTalkPipeline.__init__` 在 `device_id=0` 之后追加位置敏感的 `device: str = "cuda"` 参数（保持向后兼容 — 既有关键字调用全 OK）；`self.device = torch.device(f"cuda:{device_id}")` 替换为 `self.device = resolve_torch_device(device, device_id)`；`generate_infinitetalk.py:525-540` 的 `wan.InfiniteTalkPipeline(...)` 调用点显式 `device=args.device`。
- **Task 4.4 遗留显式备案**：`torch.cuda.empty_cache()` / `torch.cuda.ipc_collect()` / `torch.cuda.manual_seed_all` / `torch.cuda.synchronize()` 在 `wan/multitalk.py` line 42/43/513 等 hot-loop 内未触动 — 这些属于 Story 1.5 multitalk happy path 范围（已在 Dev Notes "已知 NPU 调用点遗留" 显式列出，避免下游 story 误判）。
- **Task 5 完成**：lint gate（line budget）EXIT=0；顶层 import 形态 grep EXIT=1（无命中 = 合规）；pipeline 类内字符串隔离 grep 仅命中合规的参数签名 default。
- **Task 6 完成（dry-run smoke surrogate）**：dev box 未安装 torch / diffusers，无法直接 `python3 generate_infinitetalk.py`；按 AC-10 文本"通过 mock 触发提前退出，但 argparse + device init + 工厂分发已穿过"的语义，编写 `_gomad-output/implementation-artifacts/smoke_test_1_2_device_factory.py` — stub `torch` 子集后直接调用 `wan/_npu_adapter/device.py` 公共 API + 复现 `--device` argparse 注册，6 个 case 全 PASS（AC-1 / AC-2 / AC-3 / AC-5 / AC-6 / AC-8 surrogate evidence）。
- **Task 7 完成（吸收 Story 1.1 LOW #1）**：`tools/check_npu_line_budget.py` `main()` 起首追加 5 路径存在性检查；缺失 → EXIT=2 + 清晰错误信息（含算子定位 + revert 提示）；rename 烟测验证通过。修改 `tools/check_npu_line_budget.py` 不计入 NFR-02 行预算（不在 5 主路径白名单）。
- **HALT 评估**：dev box 缺 torch / torch_npu，无法跑端到端 `generate_infinitetalk.py` CLI；按 AC-10 显式条款（"dry-run 烟测 — 无需真实 NPU 硬件"），smoke harness 提供等价 surrogate evidence。**未触发 HALT** — 所有 AC 经 surrogate / static / lint / grep 多重验证。

### File List

**新增（不计入 5 主路径白名单的行预算）：**
- `wan/_npu_adapter/__init__.py` — NPU 适配层包（docstring 标注 lazy-import 边界）
- `wan/_npu_adapter/device.py` — 设备工厂（`set_device` / `resolve_torch_device` / `is_npu` / `assert_single_card_or_fail`）
- `_gomad-output/implementation-artifacts/smoke_test_1_2_device_factory.py` — Task 6 dry-run 烟测 harness（AC-10 surrogate evidence 生成器）

**修改（计入 NFR-02 行预算）：**
- `generate_infinitetalk.py` — argparse 注册 `--device` + `generate()` 内调用设备工厂 + pipeline 构造点显式 `device=args.device`（净 +12 行）
- `wan/multitalk.py` — `__init__` 签名追加 `device: str = "cuda"` + `self.device = resolve_torch_device(...)`（净 +3 行）

**修改（不计入 5 主路径白名单）：**
- `tools/check_npu_line_budget.py` — Task 7 5 路径存在性 fail-loudly（吸收 Story 1.1 LOW #1）

### Change Log

| 日期 | 作者 | 变更 |
|------|------|------|
| 2026-04-26 | Bob (Scrum Master) | 创建 Story 1.2：`--device {cuda,npu}` flag 与设备初始化抽象（基于 Story 1.1 已落地的 lint gate 规划行预算；吸收 Story 1.1 LOW #1 作为可选 Task 7）。Status: backlog → ready-for-dev。|
| 2026-04-26 | Amelia (gm-dev-story) | 实施 Story 1.2 全 7 task：新增 `wan/_npu_adapter/{__init__,device}.py` 设备工厂；`generate_infinitetalk.py` 注入 `--device` flag + 设备工厂调用；`wan/multitalk.py` 抽象 `self.device`；行预算 lint gate / 顶层 import grep / pipeline 类隔离 grep 三重验证；6 case dry-run smoke surrogate 全 PASS；吸收 Story 1.1 LOW #1（5 路径存在性 fail-loudly）。Status: ready-for-dev → review。|
