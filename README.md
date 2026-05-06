# ABDataBench

**ABDataBench** is a benchmark for evaluating LLM-based extraction of structured antibody data from scientific literature. It pairs a curated 32-document dataset (papers + patents + supplements) with a record-centered evaluation framework covering 22 fields across binding kinetics, sequences, and biological metadata.

**ABCurator** is the accompanying multi-agent extraction system that achieves state-of-the-art performance on this benchmark.

---

**ABDataBench** 是一个用于评估大语言模型从科学文献中提取结构化抗体数据能力的基准。它包含一个精心标注的 32 篇文档数据集（论文 + 专利 + 补充材料），以及一个涵盖结合动力学、序列和生物学元数据等 22 个字段的以记录为中心的评估框架。

**ABCurator** 是配套的多智能体抽取系统，在该基准上取得了最优性能。

---

## Overview / 概览

<p align="center">
  <img src="figures/ABDataBench-ABCurator.png" width="90%" alt="ABDataBench and ABCurator Overview"/>
</p>

## Benchmark Framework / 基准框架

<p align="center">
  <img src="figures/benchmark.png" width="95%" alt="Benchmark Evaluation Framework"/>
</p>

The evaluation pipeline uses a tiered 22-field schema (Core / Standard / Auxiliary), record-level Hungarian matching, and LLM-as-Judge scoring to produce a final benchmark score.

评估流程采用分层 22 字段模式（核心 / 标准 / 辅助），记录级匈牙利匹配，以及 LLM-as-Judge 评分，最终生成基准分数。

## Multi-Agent Pipeline (ABCurator) / 多智能体流水线

<p align="center">
  <img src="figures/multiagent.png" width="95%" alt="ABCurator Multi-Agent Pipeline"/>
</p>

ABCurator uses a four-stage pipeline: Document Conditioning → Skeleton Construction → Parallel Enrichment → Validation, with up to 3 retry rounds driven by an Agent–Scientist Co-evolution loop.

ABCurator 采用四阶段流水线：文档预处理 → 骨架构建 → 并行富化 → 验证，并通过 Agent-Scientist 协同演化循环支持最多 3 轮重试。

## Model Benchmark Results / 模型基准结果

| Model | Ab. Prec. ↑ | Ab. Rec. ↑ | Seq. Hit ↑ | KD Hit ↑ | Score ↑ |
|:------|:-----------:|:----------:|:----------:|:--------:|:-------:|
| **Proprietary Models** | | | | | |
| Claude-4.7-Opus | **38.1** | 96.9 | 91.5 | 73.8 | **84.0** |
| Claude-4.6-Sonnet | 31.8 | 95.6 | 84.3 | 67.7 | 77.9 |
| Gemini-3.1-Pro | 28.0 | **100.0** | 86.3 | 46.2 | 78.4 |
| GPT-5.5 | 24.0 | **100.0** | 94.8 | 67.7 | 83.0 |
| **Open-Source Models** | | | | | |
| Qwen3.5-Plus | 26.4 | **100.0** | 93.5 | **75.4** | **81.7** |
| DeepSeek-V4-Pro | **34.6** | 99.4 | **95.4** | 72.3 | 80.2 |
| GLM-5.1 | 27.7 | 97.5 | 86.9 | 70.8 | 77.1 |
| MiniMax-M2.7 | 33.8 | 96.2 | 85.6 | 69.2 | 76.4 |

- **Ab. Prec. / Ab. Rec.**: Antibody-record precision and recall (抗体记录精确率和召回率)
- **Seq. Hit**: Exact-or-partial hit rate for sequence fields (序列字段精确/部分命中率)
- **KD Hit**: Exact-or-partial hit rate for binding affinity fields (结合亲和力字段命中率)
- **Score**: Final ABDataBench score (最终基准分数)

## Repository Layout / 仓库结构

```text
agent/                  Multi-agent extraction system (ABCurator)
agent/prompts/          Versioned prompt assets
agent/skills/           Skill metadata loaded by the agents
dataset/                Default OCR benchmark dataset (32 documents)
benchmark/              Ground truth, evaluator, and visualization tools
figures/                Figures for documentation
ocr/                    Optional OCR helper scripts
frontend/               Optional React frontend for annotation/review
backend/                Optional FastAPI backend for annotation/review
scripts/run_pipeline.py End-to-end extraction, evaluation, and dashboard
```

## Installation / 安装

```bash
git clone https://github.com/GAIR-NLP/ABDataBench.git
cd ABDataBench
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local environment file / 创建本地环境文件:

```bash
cp .env.example .env
```

Set at least these values / 至少设置以下值:

```bash
LLM_API_BASE=https://your-api-endpoint
LLM_API_KEY=your_api_key
LLM_MODEL=your_model_name
BENCHMARK_API_KEY=your_api_key
```

## Quick Start / 快速开始

### End-to-End Run / 端到端运行

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

### Extraction Only / 仅抽取

```bash
python scripts/run_pipeline.py --skip-eval --output-root runs
```

### Benchmark Only / 仅评测

```bash
cd benchmark
python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark
```

### Generate Dashboard / 生成可视化面板

```bash
python benchmark/scripts/visualize_eval.py \
  runs/dev/benchmark/eval_result_latest.json \
  --output runs/dev/benchmark/eval_dashboard.html
```

## Output Structure / 输出结构

```text
runs/<run_name>/
├── agent/benchmark_predictions.json   # Predictions
├── benchmark/eval_result_latest.json  # Evaluation results
├── benchmark/eval_report_latest.md    # Evaluation report
└── benchmark/eval_dashboard.html      # Interactive dashboard
```

## Configuration / 配置

See `.env.example` for the full configuration surface. Key settings:

| Variable | Description |
|----------|-------------|
| `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL` | Text extraction model / 文本抽取模型 |
| `LLM_REVIEW_MODEL` | Reviewer model (defaults to LLM_MODEL) / 审阅模型 |
| `VLM_API_BASE`, `VLM_API_KEY`, `VLM_MODEL` | Image extraction model / 图像抽取模型 |
| `BENCHMARK_API_KEY`, `BENCHMARK_MODEL` | Benchmark judge model / 评测裁判模型 |
| `NCBI_EMAIL`, `NCBI_API_KEY` | Optional NCBI/PDB lookup / NCBI/PDB 查询 |

## License

See [LICENSE](LICENSE).
