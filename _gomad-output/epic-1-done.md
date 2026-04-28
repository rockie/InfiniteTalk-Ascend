# Epic 1: NPU 启动与单卡 multitalk Walking Skeleton — 完成日志

本文件汇集 Epic 1 各 story 的完成总结，按时间倒序追加。

---

## 1-5-multitalk-single-card-happy-path — multitalk 单卡 NPU happy path（hot-loop 适配 + J1 acceptance pivot）

**Date:** 2026-04-26 (代码层 review 通过；J1 真机验收 PENDING USER ON ASCEND 910B)

### Story
`wan/multitalk.py` 内 5 处 hot-loop CUDA-only 调用（Story 1.2 binding contract 转交至此）device-aware 化：替换为 `wan/_npu_adapter/runtime.py` 的 `device_empty_cache / device_ipc_collect / device_manual_seed_all / device_synchronize` helper。本 story 是 J1 acceptance pivot — 完整 J1 命令（`python generate_infinitetalk.py --task infinitetalk-14B --device npu --input_json examples/single_example_image.json --save_file out_multitalk.mp4`）必须在 Ascend 910B 上由用户人工执行。3 信号采集（fallback ops / HBM 峰值 / wall-clock）显式归属 Story 1.6，不在本 story scope 内。

### Work Done
- 新增 `wan/_npu_adapter/runtime.py`：4 个 device-aware helper，按 `device.type` 分发 cuda / npu。`device_ipc_collect` 在 NPU 上用 `hasattr(torch.npu, "ipc_collect")` 检测 + `logger.debug("torch.npu.ipc_collect not available; skipping")`（CANN 版本兼容）。未支持 device.type 抛 `ValueError("Unsupported device.type='{x}'")`（pin to mps，不接受 cpu — cpu 是 t5_cpu offload 真实场景）。
- `wan/multitalk.py` (+15 行 net)：5 处 hot-loop 调用替换至 helper（原 line 42/43/377/517/839 — `torch.cuda.empty_cache` / `ipc_collect` / `manual_seed_all` / `synchronize`）；module-level `_DEVICE_FOR_GC` state via `globals()['_DEVICE_FOR_GC'] = self.device`，写入紧随 `self.device = resolve_torch_device(...)` 之后（line 163），**先于** `__init__` 内 quant 路径的 `torch_gc()` 调用（line ~205）— 修复 code review HIGH-1 ordering bug，否则 quant 路径在 NPU host 上会因 cuda fallback 撞 AttributeError。`torch_gc()` 函数体保留 `_DEVICE_FOR_GC is None` 时 cuda 字面量 fallback 作为 unit-test / 非 pipeline import 安全网（NFR-05 物理保证）。15 处现存 `torch_gc()` caller 全部 zero-touch（arg-less 签名保留）。
- 新增 `_gomad-output/implementation-artifacts/smoke_test_1_5_runtime.py`：6 case dry-run 烟测（4 cuda spies + 1 npu mock-namespace + 1 mps ValueError）。POST 检查 `not any(name.startswith('torch_npu') for name in sys.modules)` 验证 CUDA 路径 zero-pollution（NFR-05 binding runtime evidence）。6/6 PASS。
- 留存证据：lint EXIT=0；`wan/multitalk.py:15` ≤ 16/80 hard cap；`grep -nE "^import torch_npu|^from torch_npu" wan/multitalk.py` 0 命中；`wan/distributed/xdit_context_parallel.py` 0/80 zero-touch（Story 1.3 binding contract）。
- AC-10 HALT-and-handoff：5 box manual checklist (`examples/single_example_image.json` 顶层路径 — PM Round-1 修正 SM 路径错误)，含 cuda-host 回归预检 + J1 exit code/exit code/二次 reproducibility。

### J1 Acceptance Evidence (Real Hardware, 2026-04-28)
- **Host**: `/data/supagent/digital-human` on Ascend 910B (8x NPU 910B2, 64GB HBM each, CANN 24.1.0.3)
- **Selected**: NPU 2 (`ASCEND_RT_VISIBLE_DEVICES=2`)
- **Command**: `python generate_infinitetalk.py --device npu --ckpt_dir weights/Wan-AI/Wan2.1-I2V-14B-720P --wav2vec_dir weights/TencentGameMate/chinese-wav2vec2-base --infinitetalk_dir weights/MeiGen-AI/InfiniteTalk/single/infinitetalk.safetensors --input_json examples/single_example_image.json --size infinitetalk-480 --sample_steps 4 --mode streaming --motion_frame 9 --num_persistent_param_in_dit 0 --save_file out_multitalk.mp4`
- **HBM allocator tuning**: `PYTORCH_NPU_ALLOC_CONF=max_split_size_mb:512` (mitigates fragmentation on tight HBM)
- **Result**: `Saving generated video to out_multitalk.mp4.mp4` + `Finished.`, exit=0, video file generated.
- **NFR-08 N≥3 reproducibility full validation** still deferred to Story 5.1 per original design.

### Known Issues
- N=2 reproducibility validation per AC-3 not yet run on real hardware (recommended manual follow-up; JSON of step-2 stdout to be appended to this section if user runs).
- First successful run used reduced parameters (480 size / 4 steps) for HBM headroom; production-grade run at 720 size / 40 steps deferred (likely needs `--quant int8` or HBM-larger NPU device).
- `--save_file` upstream bug: doubled `.mp4` extension in output filename (cosmetic; deferred-work).
- 30+ fixes applied during real-hardware bring-up — see commits 79d8ed5..6bf3127 (Story 1.5 + cross-cutting NPU adapter polish). Pattern: cuda-only assumption purges in non-tracked files (multitalk_utils torch_gc, attention.py xfuser/xformers try/except, clip.py autocast, t5.py default arg, multitalk_model amp_shim, time_embedding fp32 promotion, flash_attention SDPA fallback, kokoro/misaki lazy import, decord aarch64 source-build, torch/torchvision ABI pin, requirements.txt split for cuda-only deps, wav2vec2 strict-API output_attentions removal). Story 1-7 README-NPU.md must consolidate the install + runtime checklist for the next NPU host operator so they don't redo the full whack-a-mole.
- NFR-08 N≥3 完整 reproducibility validation 显式 deferred 至 Story 5.1。
- 3 LOW 遗留 (`deferred-work.md` "From Story 1-5"): (1) `torch_gc()` line 45 分号串行损害可读性；(2) `globals()` 直写 module state 反模式 + 多实例覆盖脆弱性 (单卡 inference 不爆)；(3) AC-4 字面 "grep 0 行" 与 cuda fallback 字面量 narrative 落差 (Story Debug Log 已显式备案)。

---

## 1-4-attention-adapter — attention 后端 NPU 适配（BNSD 单一路径）

**Date:** 2026-04-26

### Story
为 `wan/modules/attention.py` 内的 `xformers.ops.memory_efficient_attention(...)` 两处调用（SingleStreamAttention.forward / SingleStreamMutiAttention.forward）引入 device-aware 分发：CUDA 上字符等价透传，NPU 上路由至 `torch_npu.npu_fusion_attention` BNSD 形态。BlockDiagonalMask + NPU 路径属于 multi-card SP（Phase 2），本 story 显式抛 `NotImplementedError`。

### Work Done
- 新增 `wan/_npu_adapter/attention_dispatch.py`：导出 `dispatch_memory_efficient_attention(q, k, v, attn_bias=None, op=None)`，按 `q.device.type` 分发：
  * CUDA 分支：函数体内 `import xformers.ops`，透传 `xformers.ops.memory_efficient_attention(q, k, v, attn_bias=attn_bias, op=op)`，character-equivalent 上游（NFR-05）。
  * NPU 分支：调用私有 `_npu_dispatch(q, k, v, attn_bias)`。先检查 `attn_bias is not None` → 抛 `NotImplementedError("BlockDiagonalMask is multi-card NPU SP path; Phase 2 scope...")`，**严格在 lazy `import torch_npu` 之前**；BNSD 路径（`attn_bias=None`）调用 `torch_npu.npu_fusion_attention(q, k, v, head_num=q.shape[-2], input_layout="BSND", scale=1/sqrt(q.shape[-1]))[0]`。
- `wan/modules/attention.py` (+3 行 net)：1 行顶层 `from wan._npu_adapter.attention_dispatch import dispatch_memory_efficient_attention`；2 处 call-site 替换（line 267 + line 381，原 `xformers.ops.memory_efficient_attention(...)` → `dispatch_memory_efficient_attention(...)`），kwargs 完全一致。`import xformers.ops`（line 11）保留 — `BlockDiagonalMask.from_seqlens(...)`（line 264）仍需用。
- 新增 `_gomad-output/implementation-artifacts/smoke_test_1_4_attention_dispatch.py`：4 case dry-run 烟测（无需 torch / torch_npu / xformers 安装）：CASE 1 CUDA 透传 spy；CASE 2 NPU+BNSD 路由至 mock `npu_fusion_attention`；CASE 3 CUDA dispatch 后 `not any(name.startswith('torch_npu') for name in sys.modules)`（AC-6 binding runtime evidence）；CASE 4 BlockDiagonalMask + NPU → NotImplementedError，traceback frame 锚定 `_npu_dispatch:99`，sys.modules 无 torch_npu（验证错误在 lazy import 之前抛出）。4/4 PASS。
- 留存证据：lint EXIT=0；`wan/modules/attention.py:3` 命中 +3 target lower bound（远低 +12 hard cap）；`wan/distributed/xdit_context_parallel.py` 0/80 zero-touch（Story 1.3 binding contract）；`grep -nE "xformers\.ops\.memory_efficient_attention\(" wan/modules/attention.py` 0 行（AC-1）；`grep -nE "^import torch_npu|^from torch_npu" wan/modules/attention.py wan/_npu_adapter/attention_dispatch.py` 0 行（AC-6）。

### Known Issues
- 无遗留（0 LOW deferred）。
- FR-06 显式收缩：本 story 仅验证 multitalk 路径（通过 SingleStreamAttention/SingleStreamMutiAttention 共享层实现）；i2v/t2v/flf2v 的 `wan/modules/model.py` 使用 `flash_attention()` 而非 xformers，无 class-specific bypass 需要消除，平凡继承 FR-06。`flash_attention` 后端的 NPU 适配延迟到 Story 1.5（real hardware）/ Epic 4。
- NPU 数值正确性（CUDA flash_attn vs `npu_fusion_attention` BNSD 输出 tensor 等价性）属于 Story 1.5 real hardware 验证范畴；本 story 仅证明 dispatch 路由正确。

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
