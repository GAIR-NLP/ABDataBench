# ABDataBench：科学文献结构化抗体数据抽取基准

[English](README.md) | [中文](README_zh.md)

[![GitHub](https://img.shields.io/badge/GitHub-181717?logo=github)](https://github.com/GAIR-NLP/ABDataBench)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97-Hugging%20Face-yellow)](https://huggingface.co/datasets/GAIR/ABDataCorpus)
[![代码许可证](https://img.shields.io/badge/Code-Apache_2.0-blue.svg)](LICENSE)

**ABDataBench** 是一个用于评估大语言模型从科学文献中抽取结构化抗体数据能力的基准。它包含一个精心标注的 32 篇文档语料库，覆盖论文、专利和补充材料，并提供一个以记录为中心的评估框架，涵盖结合动力学、抗体序列和生物学元数据等 22 个字段。

**ABCurator** 是配套的多智能体抽取系统，通过文档预处理、结构化骨架构建、并行信息补全和结果验证，从异构科学文档中恢复抗体记录。

## ✨ 主要特点

- **🧬 结构化抗体记录**：将抗体序列、结合动力学、靶标信息和生物学元数据抽取到统一模式中。

- **📚 多来源科学语料库**：支持在研究论文、专利和补充材料上评估抽取能力，并结合 OCR 文本与相关图像。

- **🧩 分层 22 字段模式**：将字段划分为核心、标准和辅助层级，区分关键抗体信息与补充元数据。

- **⚖️ 记录级匹配**：使用匈牙利算法将预测抗体记录与标准答案记录进行匹配，再开展字段级评分。

- **🧠 LLM-as-a-Judge 评估**：使用模型辅助判断灵活比较抽取值，同时保留精确的结构化指标。

- **🤖 多智能体抽取**：ABCurator 结合骨架构建、证据压缩、序列与图像抽取、文献重点分析和验证等专用智能体。

<p align="center">
  <img src="figures/ABDataBench-ABCurator.png" width="90%" alt="ABDataBench 与 ABCurator 概览"/>
</p>

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/GAIR-NLP/ABDataBench.git
cd ABDataBench
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

创建本地环境文件：

```bash
cp .env.example .env
```

配置抽取和评测流程所需的 API 参数：

```bash
LLM_API_BASE=https://your-api-endpoint
LLM_API_KEY=your_api_key
LLM_MODEL=your_model_name
BENCHMARK_API_KEY=your_api_key
```

完整配置项见 `.env.example`，其中还包括可选的 VLM、NCBI 和 PDB 配置。

### 运行端到端流程

```bash
source .venv/bin/activate
set -a; source .env; set +a

python scripts/run_pipeline.py \
  --output-root runs \
  --papers-per-worker 4 \
  --llm-concurrency 8 \
  --paper-concurrency 5 \
  --trace \
  --serve \
  --host 0.0.0.0 \
  --port 8000
```

### 仅运行抽取

```bash
python scripts/run_pipeline.py --skip-eval --output-root runs
```

### 运行基准评测器

```bash
cd benchmark
python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark
```

### 生成评测可视化面板

```bash
python benchmark/scripts/visualize_eval.py \
  runs/dev/benchmark/eval_result_latest.json \
  --output runs/dev/benchmark/eval_dashboard.html
```

## 🏗️ 基准框架

<p align="center">
  <img src="figures/benchmark.png" width="95%" alt="ABDataBench 评估框架"/>
</p>

评估流程采用分层 22 字段模式、记录级匈牙利匹配和 LLM-as-a-Judge 评分，最终生成基准分数。

基准从抗体记录、序列字段和结合亲和力字段等多个角度报告指标：

| 指标 | 说明 |
|:-----|:-----|
| **抗体精确率** | 抗体记录级别的精确率 |
| **抗体召回率** | 抗体记录级别的召回率 |
| **序列命中率** | 序列字段的精确或部分命中率 |
| **KD 命中率** | 结合亲和力字段的精确或部分命中率 |
| **分数** | ABDataBench 最终基准分数 |

## 🤖 多智能体流水线：ABCurator

<p align="center">
  <img src="figures/multiagent.png" width="95%" alt="ABCurator 多智能体流水线"/>
</p>

ABCurator 采用四阶段流水线：

1. **文档预处理**：整理 OCR 文本、图像、表格和补充材料，供后续抽取使用。
2. **骨架构建**：识别候选抗体记录并填充核心字段。
3. **并行信息补全**：补充序列、结合测量值、靶标信息和相关证据。
4. **验证**：检查记录一致性、规范化字段值，并在必要时触发定向重试。

该流程通过 Agent-Scientist 协同演化循环支持最多三轮重试。

## 🏆 模型基准结果

| 模型 | 抗体精确率 ↑ | 抗体召回率 ↑ | 序列命中率 ↑ | KD 命中率 ↑ | 分数 ↑ |
|:------|:-----------:|:----------:|:----------:|:--------:|:-------:|
| **闭源模型** | | | | | |
| Claude-4.7-Opus | **38.1** | 96.9 | 91.5 | 73.8 | **84.0** |
| Claude-4.6-Sonnet | 31.8 | 95.6 | 84.3 | 67.7 | 77.9 |
| Gemini-3.1-Pro | 28.0 | **100.0** | 86.3 | 46.2 | 78.4 |
| GPT-5.5 | 24.0 | **100.0** | 94.8 | 67.7 | 83.0 |
| **开源模型** | | | | | |
| Qwen3.5-Plus | 26.4 | **100.0** | 93.5 | **75.4** | **81.7** |
| DeepSeek-V4-Pro | **34.6** | 99.4 | **95.4** | 72.3 | 80.2 |
| GLM-5.1 | 27.7 | 97.5 | 86.9 | 70.8 | 77.1 |
| MiniMax-M2.7 | 33.8 | 96.2 | 85.6 | 69.2 | 76.4 |

## 📦 数据集

ABDataBench 语料库已发布在 Hugging Face：

- **ABDataCorpus**：[https://huggingface.co/datasets/GAIR/ABDataCorpus](https://huggingface.co/datasets/GAIR/ABDataCorpus)

仓库同时包含默认 OCR 基准数据集、标准答案标注、评估脚本以及复现实验所需的文档配图。

## 📁 仓库结构

```text
agent/                  多智能体抽取系统（ABCurator）
agent/prompts/          版本化的提示词资源
agent/skills/           智能体加载的技能元数据
dataset/                默认 OCR 基准数据集
benchmark/              标准答案、评估器和可视化工具
figures/                文档配图
ocr/                    可选的 OCR 辅助脚本
frontend/               可选的 React 标注/审核前端
backend/                可选的 FastAPI 标注/审核后端
scripts/run_pipeline.py 端到端抽取、评测和面板脚本
```

## 📤 输出结构

```text
runs/<run_name>/
├── agent/benchmark_predictions.json   # 预测结果
├── benchmark/eval_result_latest.json  # 评测结果
├── benchmark/eval_report_latest.md    # 评测报告
└── benchmark/eval_dashboard.html      # 交互式面板
```

## ⚙️ 配置

关键环境变量包括：

| 变量 | 说明 |
|:-----|:-----|
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | 文本抽取模型 |
| `LLM_REVIEW_MODEL` | 审阅模型，默认使用 `LLM_MODEL` |
| `VLM_API_BASE`, `VLM_API_KEY`, `VLM_MODEL` | 图像抽取模型 |
| `BENCHMARK_API_KEY`, `BENCHMARK_MODEL` | 基准评测裁判模型 |
| `NCBI_EMAIL`, `NCBI_API_KEY` | 可选的 NCBI/PDB 查询 |

## 📄 许可证

仓库源代码采用 [Apache License 2.0](LICENSE) 许可证。

## 🙏 致谢

感谢开放科学文献、OCR、语言模型和生物信息学社区提供的工具与资源，它们支持了 ABDataBench 的构建和评估。

## 🤝 贡献

欢迎贡献代码！请随时提交 Pull Request。

## 📞 联系方式

如有问题或建议，请在 [GitHub](https://github.com/GAIR-NLP/ABDataBench) 提交 Issue。

---

**ABDataBench** —— 面向科学文献的结构化抗体数据抽取基准。
