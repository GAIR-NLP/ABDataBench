# ABDataBench

[English](README.md) | [中文](README_zh.md)

**ABDataBench** 是一个用于评估大语言模型从科学文献中提取结构化抗体数据能力的基准。它包含一个精心标注的 32 篇文档数据集（论文 + 专利 + 补充材料），以及一个涵盖结合动力学、序列和生物学元数据等 22 个字段的以记录为中心的评估框架。

**ABCurator** 是配套的多智能体抽取系统，在该基准上取得了最优性能。

---

## 概览

<p align="center">
  <img src="figures/ABDataBench-ABCurator.png" width="90%" alt="ABDataBench 与 ABCurator 概览"/>
</p>

## 基准框架

<p align="center">
  <img src="figures/benchmark.png" width="95%" alt="基准评估框架"/>
</p>

评估流程采用分层 22 字段模式（核心 / 标准 / 辅助），记录级匈牙利匹配，以及 LLM-as-Judge 评分，最终生成基准分数。

## 多智能体流水线（ABCurator）

<p align="center">
  <img src="figures/multiagent.png" width="95%" alt="ABCurator 多智能体流水线"/>
</p>

ABCurator 采用四阶段流水线：文档预处理 → 骨架构建 → 并行富化 → 验证，并通过 Agent-Scientist 协同演化循环支持最多 3 轮重试。

## 模型基准结果

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

- **抗体精确率 / 抗体召回率**：抗体记录级别的精确率和召回率
- **序列命中率**：序列字段的精确/部分命中率
- **KD 命中率**：结合亲和力字段的精确/部分命中率
- **分数**：ABDataBench 最终基准分数

## 仓库结构

```text
agent/                  多智能体抽取系统（ABCurator）
agent/prompts/          版本化的提示词资源
agent/skills/           智能体加载的技能元数据
dataset/                默认 OCR 基准数据集（32 篇文档）
benchmark/              标准答案、评估器和可视化工具
figures/                文档配图
ocr/                    可选的 OCR 辅助脚本
frontend/               可选的 React 标注/审核前端
backend/                可选的 FastAPI 标注/审核后端
scripts/run_pipeline.py 端到端抽取、评测和面板脚本
```

## 安装

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

至少设置以下值：

```bash
LLM_API_BASE=https://your-api-endpoint
LLM_API_KEY=your_api_key
LLM_MODEL=your_model_name
BENCHMARK_API_KEY=your_api_key
```

## 快速开始

### 端到端运行

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

### 仅抽取

```bash
python scripts/run_pipeline.py --skip-eval --output-root runs
```

### 仅评测

```bash
cd benchmark
python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark
```

### 生成可视化面板

```bash
python benchmark/scripts/visualize_eval.py \
  runs/dev/benchmark/eval_result_latest.json \
  --output runs/dev/benchmark/eval_dashboard.html
```

## 输出结构

```text
runs/<run_name>/
├── agent/benchmark_predictions.json   # 预测结果
├── benchmark/eval_result_latest.json  # 评测结果
├── benchmark/eval_report_latest.md    # 评测报告
└── benchmark/eval_dashboard.html      # 交互式面板
```

## 配置

完整配置项见 `.env.example`。关键设置：

| 变量 | 说明 |
|------|------|
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | 文本抽取模型 |
| `LLM_REVIEW_MODEL` | 审阅模型（默认与 LLM_MODEL 相同） |
| `VLM_API_BASE`, `VLM_API_KEY`, `VLM_MODEL` | 图像抽取模型 |
| `BENCHMARK_API_KEY`, `BENCHMARK_MODEL` | 评测裁判模型 |
| `NCBI_EMAIL`, `NCBI_API_KEY` | 可选的 NCBI/PDB 查询 |

## 许可证

Apache 2.0。详见 [LICENSE](LICENSE)。
