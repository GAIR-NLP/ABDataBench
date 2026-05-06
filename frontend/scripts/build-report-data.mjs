import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");

const defaultReportPath = path.resolve(
  frontendRoot,
  "../runs/dev/benchmark/eval_report_latest.md",
);

const reportPath = process.env.EVAL_REPORT_PATH
  ? path.resolve(process.env.EVAL_REPORT_PATH)
  : defaultReportPath;

const outputPath = path.resolve(frontendRoot, "public/generated/reportData.json");

const raw = fs.readFileSync(reportPath, "utf8");
const lines = raw.split(/\r?\n/);

const reservedSections = new Set([
  "Evaluation Scope",
  "Overall Score",
  "Field Weight Policy",
  "Penalty Formula",
  "Paper-Level Scores",
]);
const issueRules = [
  {
    name: "Stable empty-field handling",
    description: "The model often keeps no-data fields empty correctly.",
    regex: /both values are empty|correctly recognized no data/i,
  },
  {
    name: "Over-extension or hallucination",
    description: "The model adds experiments, structures, or qualifiers not supported by the paper.",
    regex: /extra|hallucinated|ground truth is empty|skipped for scoring/i,
  },
  {
    name: "Missing key detail",
    description: "The main entity is found, but clade, cross-target, dose, or qualifiers are missing.",
    regex: /missing|incomplete|not output|did not output|omits?/i,
  },
  {
    name: "No model output",
    description: "Some non-empty ground-truth fields are left blank by the model.",
    regex: /model did not output|not identified by the model/i,
  },
  {
    name: "Isotype or type confusion",
    description: "IgG, IgA, IgM, and subtype distinctions can still be confused.",
    regex: /isotype|antibody type|type mismatch|IgG|IgA|IgM/i,
  },
  {
    name: "Numeric vagueness",
    description: "Quantitative fields sometimes use ranges or qualitative wording instead of exact values.",
    regex: /numeric|range|vague|approx|difference/i,
  },
];

function parseCells(line) {
  return line
    .split("|")
    .slice(1, -1)
    .map((cell) => cell.trim());
}

function stripMarkdown(value) {
  return value.replace(/\*\*/g, "").trim();
}

function extractNumber(value) {
  const match = stripMarkdown(value).match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

function parseLabel(scoreText) {
  if (scoreText.includes("✅")) return "exact";
  if (scoreText.includes("⚠")) return "partial";
  if (scoreText.includes("❌")) return "wrong";
  if (scoreText.includes("🔲")) return "miss";
  if (scoreText.includes("➖")) return "skip";
  return "other";
}

function parseCategory(levelText) {
  if (/core/i.test(levelText)) return "core";
  if (/standard/i.test(levelText)) return "standard";
  return "auxiliary";
}

function parseTable(startIndex) {
  const header = parseCells(lines[startIndex]);
  const rows = [];
  let index = startIndex + 2;

  while (index < lines.length && lines[index].trim().startsWith("|")) {
    const cells = parseCells(lines[index]);
    const row = {};
    header.forEach((key, cellIndex) => {
      row[key] = cells[cellIndex] ?? "";
    });
    rows.push(row);
    index += 1;
  }

  return { header, rows, nextIndex: index };
}

function findHeadingIndex(heading) {
  return lines.findIndex((line) => line.trim() === heading);
}

function findNextTableIndex(startIndex) {
  let index = startIndex + 1;
  while (index < lines.length && !lines[index].trim().startsWith("|")) {
    index += 1;
  }
  return index;
}

const overallScoreLine = lines.find((line) => /^### \*\*.+\/ 100\*\*$/.test(line.trim())) ?? "";
const overallScore = extractNumber(overallScoreLine);

const summaryTable = parseTable(findNextTableIndex(findHeadingIndex("## Overall Score")));
const summaryMetrics = summaryTable.rows.map((row) => ({
  key: row["Metric"],
  value: row["Value"],
}));

const weightTable = parseTable(findNextTableIndex(findHeadingIndex("## Field Weight Policy")));
const weightStrategy = weightTable.rows.map((row) => {
  const category = parseCategory(row["Weight level"]);
  return {
    level: row["Weight level"],
    category,
    weightValue: extractNumber(row["Weight"]),
    fields: row["Fields"]
      .split(",")
      .map((field) => field.trim())
      .filter(Boolean),
  };
});

const fieldMetaMap = new Map();
weightStrategy.forEach((row) => {
  row.fields.forEach((field) => {
    fieldMetaMap.set(field, {
      category: row.category,
      weightValue: row.weightValue,
      weightText: row.level,
    });
  });
});

const paperSummaryTable = parseTable(findNextTableIndex(findHeadingIndex("## Paper-Level Scores")));
const paperSummaries = paperSummaryTable.rows.map((row) => ({
  paperId: row["Paper ID"],
  gt: extractNumber(row["GT"]),
  matched: extractNumber(row["Matched"]),
  falseNegative: extractNumber(row["Missing"]),
  falsePositive: extractNumber(row["Extra"]),
  penalty: extractNumber(row["Penalty"]),
  rawScore: extractNumber(row["Raw Score"]),
  finalScore: extractNumber(row["Final Score"]),
  unmatchedGt: row["Unmatched GT"] === "-" ? "" : row["Unmatched GT"],
}));

const paperSummaryMap = new Map(paperSummaries.map((paper) => [paper.paperId, paper]));

const emptyLabels = {
  exact: 0,
  partial: 0,
  wrong: 0,
  miss: 0,
  skip: 0,
  other: 0,
};

const fieldStatsMap = new Map();
const issueMap = new Map(
  issueRules.map((rule) => [
    rule.name,
    {
      name: rule.name,
      description: rule.description,
      count: 0,
      examples: [],
    },
  ]),
);

function getFieldStats(fieldName, meta) {
  if (!fieldStatsMap.has(fieldName)) {
    fieldStatsMap.set(fieldName, {
      field: fieldName,
      category: meta.category,
      weightValue: meta.weightValue,
      count: 0,
      totalScore: 0,
      activeCount: 0,
      activeTotalScore: 0,
      gtNonEmptyCount: 0,
      predNonEmptyCount: 0,
      bothEmptyExactCount: 0,
      labels: { ...emptyLabels },
      examples: [],
    });
  }

  return fieldStatsMap.get(fieldName);
}

const papers = [];
let index = 0;

while (index < lines.length) {
  const paperMatch = lines[index].match(/^## (.+)$/);
  if (!paperMatch || reservedSections.has(paperMatch[1])) {
    index += 1;
    continue;
  }

  const paperId = paperMatch[1];
  const summary = paperSummaryMap.get(paperId);
  const metrics = {
    ngs: 0,
    ntp: 0,
    nfn: 0,
    nfp: 0,
    penalty: summary?.penalty ?? 0,
    rawAverage: summary?.rawScore ?? 0,
    finalScore: summary?.finalScore ?? 0,
  };

  const records = [];
  index += 1;

  while (index < lines.length && !/^## /.test(lines[index])) {
    const metricMatch = lines[index].match(/^- \*\*(.+?)\*\*: (.+)$/);
    if (metricMatch) {
      const metricKey = metricMatch[1];
      const metricValue = metricMatch[2];
      if (metricKey === "NGS/NTP/NFN/NFP") {
        const values = metricValue.split("/").map((item) => extractNumber(item));
        metrics.ngs = values[0] ?? 0;
        metrics.ntp = values[1] ?? 0;
        metrics.nfn = values[2] ?? 0;
        metrics.nfp = values[3] ?? 0;
      }
      if (metricKey === "Penalty") metrics.penalty = extractNumber(metricValue);
      if (metricKey === "Raw weighted average") metrics.rawAverage = extractNumber(metricValue);
      if (metricKey === "Final score") metrics.finalScore = extractNumber(metricValue);
      index += 1;
      continue;
    }

    const antibodyMatch = lines[index].match(/^### (.+?)\s+(matched|unmatched)\s+-\s+([0-9.]+)\s+pts$/i);
    if (!antibodyMatch) {
      index += 1;
      continue;
    }

    const antibodyName = antibodyMatch[1];
    const statusText = antibodyMatch[2];
    const statusSymbol = statusText.toLowerCase() === "matched" ? "matched" : "unmatched";
    const antibodyScore = Number(antibodyMatch[3]);

    index += 1;
    while (index < lines.length && !lines[index].startsWith("| Field |") && !/^### /.test(lines[index]) && !/^## /.test(lines[index])) {
      index += 1;
    }

    const fields = [];

    if (lines[index]?.startsWith("| Field |")) {
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const cells = parseCells(lines[index]);
        const [field, weightText, gt, pred, scoreText, weightedScoreText, reason] = cells;
        const label = parseLabel(scoreText);
        const meta = fieldMetaMap.get(field) ?? {
          category: "standard",
          weightValue: extractNumber(weightText),
          weightText,
        };
        const item = {
          field,
          weightText,
          weightValue: meta.weightValue,
          category: meta.category,
          gt,
          pred,
          score: extractNumber(scoreText),
          weightedScore: extractNumber(weightedScoreText),
          reason,
          label,
          hasGroundTruth: gt !== "",
          hasPrediction: pred !== "",
        };

        fields.push(item);

        const stats = getFieldStats(field, meta);
        stats.count += 1;
        stats.totalScore += item.score;
        stats.labels[label] += 1;
        if (item.hasGroundTruth) stats.gtNonEmptyCount += 1;
        if (item.hasPrediction) stats.predNonEmptyCount += 1;
        if ((item.hasGroundTruth || item.hasPrediction) && label !== "skip") {
          stats.activeCount += 1;
          stats.activeTotalScore += item.score;
        }
        if (!item.hasGroundTruth && !item.hasPrediction && label === "exact") {
          stats.bothEmptyExactCount += 1;
        }
        if (label !== "exact" && stats.examples.length < 4) {
          stats.examples.push({
            paperId,
            antibodyName,
            label,
            score: item.score,
            gt,
            pred,
            reason,
          });
        }

        issueRules.forEach((rule) => {
          if (rule.regex.test(reason)) {
            const issue = issueMap.get(rule.name);
            issue.count += 1;
            if (issue.examples.length < 3) {
              issue.examples.push(`${field}: ${reason}`);
            }
          }
        });

        index += 1;
      }
    }

    records.push({
      name: antibodyName,
      statusSymbol,
      statusText,
      score: antibodyScore,
      fields,
    });
  }

  papers.push({
    paperId,
    summary: summary ?? {
      paperId,
      gt: metrics.ngs,
      matched: metrics.ntp,
      falseNegative: metrics.nfn,
      falsePositive: metrics.nfp,
      penalty: metrics.penalty,
      rawScore: metrics.rawAverage,
      finalScore: metrics.finalScore,
      unmatchedGt: "",
    },
    metrics,
    records,
  });
}

const fieldStats = [...fieldStatsMap.values()]
  .map((entry) => ({
    field: entry.field,
    category: entry.category,
    weightValue: entry.weightValue,
    count: entry.count,
    avgScore: Number(((entry.totalScore / entry.count) * 100).toFixed(1)),
    activeAvgScore: Number(
      ((entry.activeTotalScore / Math.max(entry.activeCount, 1)) * 100).toFixed(1),
    ),
    activeCount: entry.activeCount,
    gtNonEmptyCount: entry.gtNonEmptyCount,
    predNonEmptyCount: entry.predNonEmptyCount,
    bothEmptyExactCount: entry.bothEmptyExactCount,
    labels: entry.labels,
    examples: entry.examples,
  }))
  .sort((left, right) => right.activeAvgScore - left.activeAvgScore);

const categoryOrder = ["core", "standard", "auxiliary"];
const categoryLabelMap = {
  core: "Core fields",
  standard: "Standard fields",
  auxiliary: "Auxiliary fields",
};

const categoryStats = categoryOrder.map((category) => {
  const items = fieldStats.filter((field) => field.category === category);
  const labelTotals = { ...emptyLabels };
  let totalScore = 0;
  let totalCount = 0;
  let activeScore = 0;
  let activeCount = 0;

  items.forEach((item) => {
    totalScore += item.avgScore * item.count;
    totalCount += item.count;
    activeScore += item.activeAvgScore * item.activeCount;
    activeCount += item.activeCount;
    Object.keys(labelTotals).forEach((label) => {
      labelTotals[label] += item.labels[label];
    });
  });

  const topFields = [...items]
    .sort((left, right) => right.activeAvgScore - left.activeAvgScore)
    .slice(0, 3)
    .map((item) => item.field);
  const riskFields = [...items]
    .sort((left, right) => left.activeAvgScore - right.activeAvgScore)
    .slice(0, 3)
    .map((item) => item.field);

  return {
    category,
    label: categoryLabelMap[category],
    weightValue: items[0]?.weightValue ?? 0,
    fieldCount: items.length,
    avgScore: Number((totalScore / Math.max(totalCount, 1)).toFixed(1)),
    activeAvgScore: Number((activeScore / Math.max(activeCount, 1)).toFixed(1)),
    activeCount,
    labels: labelTotals,
    topFields,
    riskFields,
  };
});

const sortedByFinal = [...paperSummaries].sort((left, right) => right.finalScore - left.finalScore);
const sortedByFp = [...paperSummaries].sort(
  (left, right) => right.falsePositive - left.falsePositive || left.finalScore - right.finalScore,
);

const paperScoreBands = {
  excellent: paperSummaries.filter((paper) => paper.finalScore >= 85).length,
  stable: paperSummaries.filter((paper) => paper.finalScore >= 75 && paper.finalScore < 85).length,
  watch: paperSummaries.filter((paper) => paper.finalScore < 75).length,
};

const issuePatterns = [...issueMap.values()]
  .filter((issue) => issue.count > 0)
  .sort((left, right) => right.count - left.count);

const strongestFields = [...fieldStats]
  .filter((item) => item.activeCount >= 20)
  .sort((left, right) => right.activeAvgScore - left.activeAvgScore)
  .slice(0, 3)
  .map((item) => `${item.field} (${item.activeAvgScore} pts)`);

const weakestFields = [...fieldStats]
  .filter((item) => item.activeCount >= 20)
  .sort((left, right) => left.activeAvgScore - right.activeAvgScore)
  .slice(0, 4)
  .map((item) => `${item.field} (${item.activeAvgScore} pts)`);

const commonTraits = [
  {
    tone: "strength",
    title: "Missing-record control is stable",
    detail: `Across ${paperSummaries.length} papers, paper-level missing records total ${paperSummaries.reduce(
      (sum, paper) => sum + paper.falseNegative,
      0,
    )}.`,
  },
  {
    tone: "risk",
    title: "Main penalties come from extra predictions",
    detail: `Paper-level extra predictions total ${paperSummaries.reduce((sum, paper) => sum + paper.falsePositive, 0)}, averaging ${Number(
      (
        paperSummaries.reduce((sum, paper) => sum + paper.falsePositive, 0) /
        Math.max(paperSummaries.length, 1)
      ).toFixed(1),
    )} per paper. Highest examples: ${sortedByFp
      .slice(0, 3)
      .map((paper) => `${paper.paperId}(${paper.falsePositive})`)
      .join(", ")}.`,
  },
  {
    tone: "strength",
    title: "Core entity extraction is relatively stable",
    detail: `The strongest active fields are ${strongestFields.join(", ")}.`,
  },
  {
    tone: "risk",
    title: "Fine-grained fields remain the main weakness",
    detail: `Lower-scoring fields concentrate in ${weakestFields.join(", ")}.`,
  },
  {
    tone: "neutral",
    title: "Empty-field handling affects averages",
    detail: "Correct empty-field recognition helps overall averages, so the dashboard also reports active-sample averages.",
  },
];

const report = {
  generatedAt: new Date().toISOString(),
  reportPath,
  title: raw.split(/\r?\n/, 1)[0].replace(/^#\s*/, "").trim(),
  overallScore,
  summaryMetrics,
  weightStrategy,
  paperSummaries,
  papers,
  analytics: {
    fieldStats,
    categoryStats,
    issuePatterns,
    commonTraits,
    paperScoreBands,
    paperLeaders: {
      topFinal: sortedByFinal.slice(0, 5),
      lowestFinal: [...sortedByFinal].reverse().slice(0, 5),
      highestFalsePositive: sortedByFp.slice(0, 5),
    },
  },
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);

console.log(`Generated ${path.relative(frontendRoot, outputPath)} from ${reportPath}`);
