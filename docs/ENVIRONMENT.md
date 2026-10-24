# 环境检查、复用情况与依赖变更

检查日期：2026-10-23（节点 A）。机器：Windows 10 19045 x64，Git Bash。

## 结论

P0 完全复用系统已有 Python 环境，仅新增 1 个小依赖（`ddgs`）。未创建新环境，未改动任何已有软件。

## 已复用（未做任何修改）

| 组件 | 版本/状态 | 说明 |
|---|---|---|
| Python | 3.11.0（`C:\Python311`，系统级） | 无 Conda；直接复用 |
| pip | 25.3 | — |
| PyYAML | 已安装 | 任务文件解析 |
| requests | 已安装 | `ddgs` 的底层依赖 |
| pytest | 8.3.5 | 单元测试 |
| torch | 2.6.0+cpu | P0 **未使用**（评价器为确定性词法规则，纯 CPU 轻量） |
| transformers | 4.57.6 | P0 未使用；P1 语义融合候选 |
| git | 2.49.0.windows.1 | 已配置 user（duanyan / 2907762730@qq.com） |
| GPU | RTX 5060 Ti 16GB，驱动 580.97 | P0 未使用 |

## 本项目新增

| 依赖 | 版本 | 用途 | 备注 |
|---|---|---|---|
| `ddgs` | 9.16.0 | DuckDuckGo 检索（无 API Key） | **清华 pip 镜像无此包**，须 `pip install ddgs -i https://pypi.org/simple` |

### 2026-10-24 P1-a 实验新增（记录）

- 模型缓存：`sentence-transformers/all-MiniLM-L6-v2`（约 90MB）下载至用户级 `~/.cache/huggingface`，**不入仓库**；
- 未新增任何 pip 包（复用已装 transformers 4.57.6 + torch 2.6.0 CPU）；实验脚本 `experiments/p1a/run_experiment.py` 仅在语义臂运行时需要该模型，词法臂无额外依赖；
- 下载途径：`hf-mirror.com` 的 hub 元数据接口与 huggingface_hub 不兼容（FileMetadataError），实际经 `huggingface.co` 直连成功（当日该域名可达；两域名连通性均间歇波动）。

运行依赖固化在 `requirements.txt`（ddgs / PyYAML / requests）。torch/transformers 有意不列入 P0 依赖。

## 风险与注意事项

1. **torch 为 CPU 版**：若 P1 要用本地 GPU 嵌入（RTX 5060 Ti 为 Blackwell 架构），需 torch ≥ 2.7 + cu128 构建。属环境变更，届时单独评估并记录，v0.1 内不动。
2. **DuckDuckGo 后端不稳定**：实测 `ddgs` 偶发 `No results found` / 回落 Yahoo 后 `tls handshake eof`。已实现重试 + 降级 + 错误归因（见代码），并在轨迹中如实记录。
3. **pip 默认源为清华镜像**：少数新包（如 ddgs）镜像缺失，需显式指定官方源；已在安装命令中注明。
4. GitHub 推送凭据：本机未配置 `gh` CLI；push 依赖 git 凭据管理器。若 push 失败会如实报告，不影响本地交付。

## 环境变更原则（承自协作规范）

先利用已有环境完成原型，再考虑优化；不升级/降级核心软件；确需变更时先说明原因与影响并记录于本文件。
