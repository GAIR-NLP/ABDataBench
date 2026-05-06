import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useState,
} from "react";
import { ReportPage } from "./ReportPage";
import type {
  AnnotationErrorType,
  AnnotationSeverity,
  AnnotationStatus,
  AnnotationUpsertPayload,
  FieldStatsResponse,
  FieldLabel,
  FieldProvenance,
  FieldResult,
  PaperDetail,
  PaperListItem,
  PapersResponse,
  SequenceIssueBoardResponse,
  SummaryResponse,
} from "./types";

const labelOrder: FieldLabel[] = ["wrong", "miss", "partial", "skip", "exact"];
const issueLabels = new Set<FieldLabel>(["wrong", "miss", "partial"]);
const sequenceFields = new Set(["CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"]);

const labelMeta: Record<
  FieldLabel,
  {
    label: string;
    short: string;
    className: string;
  }
> = {
  wrong: { label: "Wrong", short: "Wrong", className: "wrong" },
  miss: { label: "Missing", short: "Miss", className: "miss" },
  partial: { label: "Partial", short: "Partial", className: "partial" },
  skip: { label: "Skipped", short: "Skip", className: "skip" },
  exact: { label: "Exact", short: "Exact", className: "exact" },
};

const statusMeta: Record<
  AnnotationStatus,
  {
    label: string;
    className: string;
  }
> = {
  pending: { label: "Pending", className: "pending" },
  reviewed: { label: "Reviewed", className: "reviewed" },
  ignored: { label: "Ignored", className: "ignored" },
};

const severityMeta: Record<
  AnnotationSeverity,
  {
    label: string;
    className: string;
  }
> = {
  high: { label: "High", className: "high" },
  medium: { label: "Medium", className: "medium" },
  low: { label: "Low", className: "low" },
};

const errorTypeMeta: Record<
  AnnotationErrorType,
  {
    label: string;
    help: string;
  }
> = {
  value_mismatch: { label: "Value mismatch", help: "The model output a value, but the content is incorrect." },
  missing_prediction: { label: "Missing prediction", help: "Ground truth has a value, but the model did not output it." },
  hallucinated_value: { label: "Hallucinated value", help: "Ground truth is empty, but the model added unsupported content." },
  incomplete_value: { label: "Incomplete value", help: "The main value is present, but qualifiers or details are missing." },
  format_issue: { label: "Format issue", help: "Units, formatting, or sequence notation differ." },
  evidence_mismatch: { label: "Evidence mismatch", help: "The output does not match paper evidence." },
  other: { label: "Other", help: "The issue does not fit the predefined categories." },
};

const fieldDisplayMap: Record<string, string> = {
  CDRH3_Sequence: "CDRH3 Sequence",
  vh_sequence_aa: "VH Amino-Acid Sequence",
  vl_sequence_aa: "VL Amino-Acid Sequence",
  Binding_Kinetics_KD: "KD Affinity",
  Binding_Kinetics_kon: "kon",
  Binding_Kinetics_koff: "koff",
  Binding_EC50: "EC50",
  Target_Name: "Target Name",
  Epitope: "Epitope",
  Experiment: "Experiment",
  Mechanism_of_Action: "Mechanism of Action",
  Structure: "Structure",
  Antibody_Type: "Antibody Type",
  Antibody_Isotype: "Antibody Isotype",
  Cross_Reactivity: "Cross-Reactivity",
  Quantitative_Metric: "Quantitative Metric",
  In_Vivo_Efficacy: "In-Vivo Efficacy",
  In_Vivo_Half_Life: "In-Vivo Half-Life",
  Reference_Source: "Reference Source",
  Target_Type: "Target Type",
  source: "Source Species",
  Thermal_Stability_Tm: "Tm Thermal Stability",
};

interface DiffSegment {
  text: string;
  diff: boolean;
}

interface AnnotationDraft {
  annotation_status: AnnotationStatus;
  final_label: FieldLabel | null;
  error_types: AnnotationErrorType[];
  severity: AnnotationSeverity;
  corrected_value: string;
  note: string;
  reviewer: string;
}

interface SaveState {
  state: "idle" | "saving" | "saved" | "error";
  message: string;
}

function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function displayFieldName(fieldName: string) {
  return fieldDisplayMap[fieldName] ?? fieldName;
}

function safeText(value: string) {
  return value && value.trim() ? value : "Not provided";
}

function hasProvenance(provenance?: FieldProvenance | null) {
  if (!provenance) return false;
  return Boolean(
    provenance.source_label ||
      provenance.pointer ||
      provenance.quote ||
      provenance.source_image ||
      provenance.source_context ||
      provenance.api_source_ids ||
      provenance.from_antibody ||
      provenance.note,
  );
}

function provenanceTypeLabel(sourceType?: string) {
  const mapping: Record<string, string> = {
    api_fetch: "API backfill",
    table: "Table evidence",
    paper_text: "Paper text",
    paper_location: "Paper location",
    figure_or_image: "Figure or image",
    sequence_image: "Sequence image",
    ocr_text_sequence: "OCR text sequence",
    inherited_from_parent: "Inherited from parent antibody",
    derived_from_vh: "Derived from VH",
    entity_sync: "Same-name record sync",
  };
  return mapping[sourceType || ""] ?? (sourceType || "Source");
}

function isSequenceField(fieldName: string) {
  return sequenceFields.has(fieldName);
}

function fieldKey(field: Pick<FieldResult, "paper_id" | "antibody_index" | "field">) {
  return `${field.paper_id}__${field.antibody_index}__${field.field}`;
}

function accordionKey(paperId: string, antibodyIndex: number) {
  return `${paperId}__${antibodyIndex}`;
}

function decodeReportPathFromLocation(pathname: string) {
  if (!pathname.startsWith("/reports")) {
    return "";
  }

  const raw = pathname.replace(/^\/reports\/?/, "");
  if (!raw) {
    return "";
  }

  return raw
    .split("/")
    .filter(Boolean)
    .map((segment) => decodeURIComponent(segment))
    .join("/");
}

function joinApiPath(apiPrefix: string, suffix: string) {
  return `${apiPrefix}${suffix}`;
}

function countIssueLabels(counts: Record<FieldLabel, number>) {
  return counts.wrong + counts.miss + counts.partial;
}

function formatDateTime(value: string) {
  if (!value) return "Not saved";
  return new Date(value).toLocaleString("en-US");
}

function scoreText(value: number) {
  return value.toFixed(1);
}

function progressWidth(value: number) {
  return `${Math.max(4, Math.min(value, 100))}%`;
}

function percentText(value: number) {
  return `${value.toFixed(1)}%`;
}

function defaultStatusForField(label: FieldLabel): AnnotationStatus {
  return issueLabels.has(label) ? "reviewed" : "ignored";
}

function defaultFinalLabel(label: FieldLabel): FieldLabel {
  return label;
}

function inferDefaultErrorTypes(label: FieldLabel): AnnotationErrorType[] {
  if (label === "wrong") return ["value_mismatch"];
  if (label === "miss") return ["missing_prediction"];
  if (label === "partial") return ["incomplete_value"];
  return [];
}

function inferDefaultSeverity(field: FieldResult): AnnotationSeverity {
  if (field.weight >= 2.5 && issueLabels.has(field.label)) return "high";
  if (issueLabels.has(field.label)) return "medium";
  return "low";
}

function buildDraftFromField(field: FieldResult): AnnotationDraft {
  const annotation = field.annotation;
  return {
    annotation_status: annotation?.annotation_status ?? defaultStatusForField(field.label),
    final_label: annotation?.final_label ?? defaultFinalLabel(field.label),
    error_types: [...(annotation?.error_types ?? inferDefaultErrorTypes(field.label))],
    severity: annotation?.severity ?? inferDefaultSeverity(field),
    corrected_value: annotation?.corrected_value ?? "",
    note: annotation?.note ?? "",
    reviewer: annotation?.reviewer ?? "",
  };
}

function serializeDraft(draft: AnnotationDraft) {
  return JSON.stringify({
    annotation_status: draft.annotation_status,
    final_label: draft.final_label,
    error_types: draft.error_types,
    severity: draft.severity,
    corrected_value: draft.corrected_value.trim(),
    note: draft.note.trim(),
    reviewer: draft.reviewer.trim(),
  });
}

function isIssueField(field: FieldResult) {
  return issueLabels.has(field.label) || Boolean(field.annotation);
}

function needsReview(field: FieldResult) {
  if (!issueLabels.has(field.label)) {
    return false;
  }
  return !field.annotation || field.annotation.annotation_status === "pending";
}

function summarizeLabels(fields: FieldResult[]) {
  return fields.reduce(
    (counts, field) => {
      counts[field.label] += 1;
      return counts;
    },
    {
      wrong: 0,
      miss: 0,
      partial: 0,
      skip: 0,
      exact: 0,
    },
  );
}

function segmentsFromFlags(text: string, flags: boolean[]): DiffSegment[] {
  if (!text) return [];

  const segments: DiffSegment[] = [];
  let currentText = text[0];
  let currentDiff = !flags[0];

  for (let index = 1; index < text.length; index += 1) {
    const nextDiff = !flags[index];
    if (nextDiff === currentDiff) {
      currentText += text[index];
      continue;
    }

    segments.push({ text: currentText, diff: currentDiff });
    currentText = text[index];
    currentDiff = nextDiff;
  }

  segments.push({ text: currentText, diff: currentDiff });
  return segments;
}

function buildSequenceDiff(left: string, right: string) {
  if (!left || !right) {
    return null;
  }

  const leftLength = left.length;
  const rightLength = right.length;
  const dp = Array.from({ length: leftLength + 1 }, () => new Uint16Array(rightLength + 1));

  for (let leftIndex = leftLength - 1; leftIndex >= 0; leftIndex -= 1) {
    for (let rightIndex = rightLength - 1; rightIndex >= 0; rightIndex -= 1) {
      dp[leftIndex][rightIndex] =
        left[leftIndex] === right[rightIndex]
          ? dp[leftIndex + 1][rightIndex + 1] + 1
          : Math.max(dp[leftIndex + 1][rightIndex], dp[leftIndex][rightIndex + 1]);
    }
  }

  const leftFlags = Array.from({ length: leftLength }, () => false);
  const rightFlags = Array.from({ length: rightLength }, () => false);
  let leftIndex = 0;
  let rightIndex = 0;

  while (leftIndex < leftLength && rightIndex < rightLength) {
    if (left[leftIndex] === right[rightIndex]) {
      leftFlags[leftIndex] = true;
      rightFlags[rightIndex] = true;
      leftIndex += 1;
      rightIndex += 1;
      continue;
    }

    if (dp[leftIndex + 1][rightIndex] >= dp[leftIndex][rightIndex + 1]) {
      leftIndex += 1;
    } else {
      rightIndex += 1;
    }
  }

  return {
    left: segmentsFromFlags(left, leftFlags),
    right: segmentsFromFlags(right, rightFlags),
  };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch {
      // ignore json parse failure
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

function StatBar({
  counts,
}: {
  counts: Record<FieldLabel, number>;
}) {
  const total = labelOrder.reduce((sum, label) => sum + counts[label], 0);

  return (
    <div className="stacked-bar" aria-label="Label distribution">
      {labelOrder.map((label) => {
        const value = counts[label];
        if (!value || !total) return null;
        return (
          <span
            key={label}
            className={cn("stack-segment", `segment-${labelMeta[label].className}`)}
            style={{ width: `${(value / total) * 100}%` }}
            title={`${labelMeta[label].label} ${value}`}
          />
        );
      })}
    </div>
  );
}

function RichTextBlock({
  fieldName,
  value,
  segments,
}: {
  fieldName: string;
  value: string;
  segments?: DiffSegment[];
}) {
  if (!value) {
    return <pre className="rich-text-block rich-text-empty">Not provided</pre>;
  }

  if (isSequenceField(fieldName) && segments) {
    return (
      <pre className="rich-text-block rich-sequence-block">
        {segments.map((segment, index) => (
          <span
            key={`${segment.text}_${index}`}
            className={segment.diff ? "sequence-diff" : "sequence-same"}
          >
            {segment.text}
          </span>
        ))}
      </pre>
    );
  }

  return <pre className="rich-text-block">{value}</pre>;
}

function ProvenanceBlock({ provenance }: { provenance: FieldProvenance }) {
  if (!hasProvenance(provenance)) {
    return null;
  }

  return (
    <section className="provenance-panel">
      <div className="provenance-head">
        <h4>Field Provenance</h4>
        <div className="field-chip-row">
          <span className="chip chip-provenance">{provenanceTypeLabel(provenance.source_type)}</span>
          {provenance.action ? <span className="chip chip-provenance-soft">{provenance.action}</span> : null}
        </div>
      </div>

      <div className="provenance-grid">
        {provenance.source_label ? (
          <div className="provenance-card">
            <span>Source Summary</span>
            <pre className="rich-text-block">{provenance.source_label}</pre>
          </div>
        ) : null}

        {provenance.pointer || provenance.paper_location || provenance.source_image ? (
          <div className="provenance-card">
            <span>Location</span>
            <pre className="rich-text-block">
              {[
                provenance.pointer ? `Pointer: ${provenance.pointer}` : "",
                provenance.paper_location ? `Location: ${provenance.paper_location}` : "",
                provenance.source_image ? `Image: ${provenance.source_image}` : "",
              ]
                .filter(Boolean)
                .join("\n")}
            </pre>
          </div>
        ) : null}

        {provenance.api_source_ids || provenance.api_source_kind ? (
          <div className="provenance-card">
            <span>External Source</span>
            <pre className="rich-text-block">
              {[
                provenance.api_source_kind ? `Kind: ${provenance.api_source_kind}` : "",
                provenance.api_source_ids ? `IDs: ${provenance.api_source_ids}` : "",
              ]
                .filter(Boolean)
                .join("\n")}
            </pre>
          </div>
        ) : null}

        {provenance.from_antibody || provenance.inherited_from_field ? (
          <div className="provenance-card">
            <span>Inheritance</span>
            <pre className="rich-text-block">
              {[
                provenance.from_antibody ? `From antibody: ${provenance.from_antibody}` : "",
                provenance.inherited_from_field ? `From field: ${displayFieldName(provenance.inherited_from_field)}` : "",
              ]
                .filter(Boolean)
                .join("\n")}
            </pre>
          </div>
        ) : null}

        {provenance.quote ? (
          <div className="provenance-card provenance-card-wide">
            <span>Evidence Quote</span>
            <pre className="rich-text-block">{provenance.quote}</pre>
          </div>
        ) : null}

        {provenance.source_context ? (
          <div className="provenance-card provenance-card-wide">
            <span>Context</span>
            <pre className="rich-text-block">{provenance.source_context}</pre>
          </div>
        ) : null}

        {provenance.note ? (
          <div className="provenance-card provenance-card-wide">
            <span>Processing Note</span>
            <pre className="rich-text-block">{provenance.note}</pre>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function OverviewCard({
  title,
  value,
  detail,
  accent,
}: {
  title: string;
  value: string;
  detail: string;
  accent?: "warm" | "teal";
}) {
  return (
    <article className={cn("overview-card", accent === "warm" && "overview-card-warm", accent === "teal" && "overview-card-teal")}>
      <p>{title}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function FieldStatsTable({ stats }: { stats: FieldStatsResponse }) {
  return (
    <section className="panel field-stats-panel">
      <div className="panel-head field-stats-head">
        <div>
          <p className="eyebrow">Field Breakdown</p>
          <h2>Field Match Statistics</h2>
          <p className="field-stats-copy">
            Each row summarizes the label distribution for a field across the result set. Partial includes `partial` and `wrong`; mismatch counts `miss`.
          </p>
        </div>
        <div className="field-stats-meta">
          <span className="tag">Field types {stats.field_count}</span>
          <span className="tag">Total fields {stats.total_fields}</span>
        </div>
      </div>

      <div className="field-stats-table-wrap">
        <table className="field-stats-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Total</th>
              <th>Exact</th>
              <th>Partial</th>
              <th>Mismatch</th>
              <th>Skipped</th>
              <th>Distribution</th>
            </tr>
          </thead>
          <tbody>
            {stats.fields.map((item) => (
              <tr key={item.field}>
                <td>
                  <div className="field-stats-name">
                    <strong>{displayFieldName(item.field)}</strong>
                    <span>{item.field}</span>
                  </div>
                </td>
                <td>{item.total}</td>
                <td className="field-stats-cell field-stats-cell-exact">
                  <strong>{percentText(item.exact_percent)}</strong>
                  <span>{item.label_counts.exact}</span>
                </td>
                <td className="field-stats-cell field-stats-cell-partial">
                  <strong>{percentText(item.partial_percent)}</strong>
                  <span>
                    {item.partial_count} = {item.label_counts.partial} partial + {item.label_counts.wrong} wrong
                  </span>
                </td>
                <td className="field-stats-cell field-stats-cell-mismatch">
                  <strong>{percentText(item.mismatch_percent)}</strong>
                  <span>{item.mismatch_count} miss</span>
                </td>
                <td className="field-stats-cell field-stats-cell-skip">
                  <strong>{percentText(item.skip_percent)}</strong>
                  <span>{item.label_counts.skip}</span>
                </td>
                <td>
                  <StatBar counts={item.label_counts} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SequenceIssueBoard({ board }: { board: SequenceIssueBoardResponse }) {
  return (
    <section className="panel sequence-issue-panel">
      <div className="panel-head sequence-issue-head">
        <div>
          <p className="eyebrow">Sequence Issue Board</p>
          <h2>Sequence Field Issue Board</h2>
          <p className="field-stats-copy">
            Tracks non-`exact` and non-`skip` entries for `CDRH3`, `VH`, and `VL` sequence fields.
          </p>
        </div>
        <div className="field-stats-meta">
          <span className="tag">Sequence fields {board.field_count}</span>
          <span className="tag">Issue entries {board.total_issue_fields}</span>
          <span className="tag">Total slots {board.total_sequence_fields}</span>
        </div>
      </div>

      <div className="sequence-issue-grid">
        {board.fields.map((item) => (
          <article key={item.field} className="sequence-issue-card">
            <div className="sequence-issue-card-head">
              <div>
                <strong>{displayFieldName(item.field)}</strong>
                <span>{item.field}</span>
              </div>
              <span className="chip chip-sequence-issue">{percentText(item.issue_percent)}</span>
            </div>

            <div className="sequence-issue-card-metrics">
              <div>
                <span>Issue Entries</span>
                <strong>{item.issue_count}</strong>
              </div>
              <div>
                <span>Papers</span>
                <strong>{item.paper_count}</strong>
              </div>
              <div>
                <span>Exact</span>
                <strong>{item.exact_count}</strong>
              </div>
            </div>

            <div className="sequence-issue-card-breakdown">
              <span>Label Breakdown</span>
              <p>
                wrong {item.wrong_count} / miss {item.miss_count} / partial {item.partial_count}
              </p>
            </div>

            <div className="sequence-issue-card-papers">
              <span>Frequent Papers</span>
              <div className="sequence-issue-paper-chips">
                {item.paper_breakdown.slice(0, 6).map((paper) => (
                  <button
                    key={`${item.field}_${paper.paper_id}`}
                    type="button"
                    className="sequence-paper-chip"
                    onClick={() => {
                      const target = document.getElementById(`sequence-issue-${item.field}`);
                      if (target) {
                        target.scrollIntoView({ behavior: "smooth", block: "start" });
                      }
                    }}
                    title={paper.paper_id}
                  >
                    {paper.paper_id} · {paper.issue_count}
                  </button>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>

      <div className="sequence-issue-sections">
        {board.fields.map((item, index) => (
          <details
            key={`table_${item.field}`}
            id={`sequence-issue-${item.field}`}
            className="sequence-issue-section"
            open={index === 0}
          >
            <summary className="sequence-issue-summary">
              <div className="sequence-issue-section-head">
                <div>
                  <h3>{displayFieldName(item.field)}</h3>
                  <p>{item.entries.length} non-exact entries</p>
                </div>
                <div className="sequence-issue-summary-meta">
                  <span className="tag">wrong {item.wrong_count}</span>
                  <span className="tag">miss {item.miss_count}</span>
                  <span className="tag">partial {item.partial_count}</span>
                </div>
              </div>
            </summary>

            <div className="sequence-issue-table-wrap">
              <table className="sequence-issue-table">
                <thead>
                  <tr>
                    <th>Paper / Antibody</th>
                    <th>Label</th>
                    <th>GT</th>
                    <th>Pred</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {item.entries.map((entry) => {
                    const diff = buildSequenceDiff(entry.gt, entry.pred);
                    return (
                      <tr key={`${item.field}_${entry.paper_id}_${entry.antibody_index}_${entry.antibody_name}`}>
                        <td>
                          <div className="sequence-issue-name">
                            <strong>{entry.antibody_name}</strong>
                            <span>{entry.paper_id}</span>
                            <span>Antibody index {entry.antibody_index + 1}</span>
                          </div>
                        </td>
                        <td>
                          <div className="sequence-issue-label">
                            <span className={cn("chip", `chip-${labelMeta[entry.label].className}`)}>
                              {labelMeta[entry.label].label}
                            </span>
                            <span>{scoreText(entry.score)}</span>
                          </div>
                        </td>
                        <td>
                          <RichTextBlock
                            fieldName={item.field}
                            value={safeText(entry.gt)}
                            segments={diff?.left}
                          />
                        </td>
                        <td>
                          <RichTextBlock
                            fieldName={item.field}
                            value={safeText(entry.pred)}
                            segments={diff?.right}
                          />
                        </td>
                        <td>
                          <div className="sequence-issue-reason">
                            <strong>Auto-Evaluation Reason</strong>
                            <span>{entry.reason || "Not provided"}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function PaperQueueCard({
  paper,
  active,
  onSelect,
  readOnly = false,
}: {
  paper: PaperListItem;
  active: boolean;
  onSelect: () => void;
  readOnly?: boolean;
}) {
  return (
    <button type="button" className={cn("paper-card", active && "paper-card-active")} onClick={onSelect}>
      <div className="paper-card-head">
        <div>
          <strong>{paper.paper_id}</strong>
          <span>{paper.antibody_count} antibody records</span>
        </div>
        {readOnly ? (
          <span className="chip chip-readonly">Score Detail</span>
        ) : (
          <span className={cn("chip", paper.annotation_summary.is_completed ? "chip-done" : "chip-warn")}>
            {paper.annotation_summary.is_completed ? "Completed" : `Pending ${paper.annotation_summary.pending_issue_fields}`}
          </span>
        )}
      </div>

      <div className="paper-card-metrics">
        <div>
          <span>Score</span>
          <strong>{scoreText(paper.accuracy)}</strong>
        </div>
        <div>
          <span>Issue Fields</span>
          <strong>{countIssueLabels(paper.label_counts)}</strong>
        </div>
        <div>
          <span>{readOnly ? "Exact" : "Reviewed"}</span>
          <strong>{readOnly ? paper.label_counts.exact : paper.annotation_summary.reviewed_issue_fields}</strong>
        </div>
      </div>

      {readOnly ? (
        <div className="paper-progress">
          <StatBar counts={paper.label_counts} />
          <span>Field Distribution</span>
        </div>
      ) : (
        <div className="paper-progress">
          <div className="paper-progress-track">
            <span style={{ width: progressWidth(paper.annotation_summary.progress_percent) }} />
          </div>
          <span>{paper.annotation_summary.progress_percent.toFixed(1)}%</span>
        </div>
      )}

      <div className="paper-card-footer">
        <span>Extra {paper.false_positive}</span>
        <span>GT {paper.gt_count}</span>
        <span>Matched {paper.matched}</span>
      </div>
    </button>
  );
}

function AnnotationApp({
  apiPrefix = "/api",
  readOnly = false,
  backHref,
}: {
  apiPrefix?: string;
  readOnly?: boolean;
  backHref?: string;
}) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [fieldStats, setFieldStats] = useState<FieldStatsResponse | null>(null);
  const [sequenceIssueBoard, setSequenceIssueBoard] = useState<SequenceIssueBoardResponse | null>(null);
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState("");
  const [paperDetail, setPaperDetail] = useState<PaperDetail | null>(null);
  const [drafts, setDrafts] = useState<Record<string, AnnotationDraft>>({});
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
  const [expandedAntibodies, setExpandedAntibodies] = useState<Record<string, boolean>>({});
  const [booting, setBooting] = useState(true);
  const [loadingPaper, setLoadingPaper] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [paperError, setPaperError] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [query, setQuery] = useState("");
  const [paperFilter, setPaperFilter] = useState<"all" | "pending" | "started" | "completed">(
    readOnly ? "all" : "pending",
  );
  const [showOnlyIssues, setShowOnlyIssues] = useState(true);
  const [showOnlyPending, setShowOnlyPending] = useState(false);
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const syncDraftsFromPaper = useEffectEvent((detail: PaperDetail) => {
    setDrafts((current) => {
      const next = { ...current };
      detail.antibodies.forEach((antibody) => {
        antibody.fields.forEach((field) => {
          next[fieldKey(field)] = buildDraftFromField(field);
        });
      });
      return next;
    });
    setExpandedAntibodies((current) => {
      const next = { ...current };
      detail.antibodies.forEach((antibody, index) => {
        const key = accordionKey(detail.paper_id, antibody.antibody_index);
        if (!(key in next)) {
          next[key] = index === 0;
        }
      });
      return next;
    });
  });

  async function refreshOverviewData() {
    const [nextSummary, nextPapers, nextFieldStats, nextSequenceIssueBoard] = await Promise.all([
      apiFetch<SummaryResponse>(joinApiPath(apiPrefix, "/summary")),
      apiFetch<PapersResponse>(joinApiPath(apiPrefix, "/papers")),
      apiFetch<FieldStatsResponse>(joinApiPath(apiPrefix, "/field-stats")),
      apiFetch<SequenceIssueBoardResponse>(joinApiPath(apiPrefix, "/sequence-issue-board")),
    ]);
    setSummary(nextSummary);
    setPapers(nextPapers.papers);
    setFieldStats(nextFieldStats);
    setSequenceIssueBoard(nextSequenceIssueBoard);
    return nextPapers.papers;
  }

  async function refreshPaperDetail(paperId: string) {
    const detail = await apiFetch<PaperDetail>(
      `${joinApiPath(apiPrefix, "/papers")}/${encodeURIComponent(paperId)}`,
    );
    setPaperDetail(detail);
    syncDraftsFromPaper(detail);
    return detail;
  }

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setBooting(true);
      try {
        const nextPapers = await refreshOverviewData();
        if (cancelled) return;
        if (nextPapers.length > 0) {
          const firstPending = nextPapers.find((paper) => !paper.annotation_summary.is_completed);
          const initial = firstPending ?? nextPapers[0];
          startTransition(() => {
            setSelectedPaperId(initial.paper_id);
          });
        }
        setLoadError("");
      } catch (error) {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Failed to load data");
        }
      } finally {
        if (!cancelled) {
          setBooting(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedPaperId) return;
    let cancelled = false;

    void (async () => {
      setLoadingPaper(true);
      try {
        await refreshPaperDetail(selectedPaperId);
        if (!cancelled) {
          setPaperError("");
        }
      } catch (error) {
        if (!cancelled) {
          setPaperError(error instanceof Error ? error.message : "Failed to load paper detail");
        }
      } finally {
        if (!cancelled) {
          setLoadingPaper(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedPaperId]);

  function updateDraft(field: FieldResult, patch: Partial<AnnotationDraft>) {
    const key = fieldKey(field);
    setDrafts((current) => {
      const base = current[key] ?? buildDraftFromField(field);
      return {
        ...current,
        [key]: {
          ...base,
          ...patch,
        },
      };
    });
    setSaveStates((current) => ({
      ...current,
      [key]: {
        state: "idle",
        message: "",
      },
    }));
  }

  async function handleSave(field: FieldResult) {
    const key = fieldKey(field);
    const currentDraft = drafts[key] ?? buildDraftFromField(field);
    const payload: AnnotationUpsertPayload = {
      paper_id: field.paper_id,
      antibody_index: field.antibody_index,
      antibody_name: field.antibody_name,
      field_name: field.field,
      original_label: field.label,
      annotation_status: currentDraft.annotation_status,
      final_label:
        currentDraft.annotation_status === "ignored"
          ? currentDraft.final_label ?? field.label
          : currentDraft.final_label,
      error_types:
        currentDraft.annotation_status === "ignored" ||
        currentDraft.final_label === "exact" ||
        !currentDraft.final_label
          ? []
          : currentDraft.error_types,
      severity: currentDraft.severity,
      corrected_value: currentDraft.corrected_value.trim(),
      note: currentDraft.note.trim(),
      reviewer: (currentDraft.reviewer || reviewer).trim(),
    };

    if (payload.annotation_status === "reviewed" && !payload.final_label) {
      setSaveStates((current) => ({
        ...current,
        [key]: {
          state: "error",
          message: "Reviewed status requires a final label.",
        },
      }));
      return;
    }

    setSaveStates((current) => ({
      ...current,
      [key]: {
        state: "saving",
        message: "Saving...",
      },
    }));

    try {
      await apiFetch("/api/annotations", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await Promise.all([refreshOverviewData(), refreshPaperDetail(field.paper_id)]);
      setSaveStates((current) => ({
        ...current,
        [key]: {
          state: "saved",
          message: "Saved to database",
        },
      }));
    } catch (error) {
      setSaveStates((current) => ({
        ...current,
        [key]: {
          state: "error",
          message: error instanceof Error ? error.message : "Save failed",
        },
      }));
    }
  }

  if (booting) {
    return (
      <div className="app-shell">
        <section className="hero loading-panel">
          <p className="eyebrow">Annotation Workspace</p>
          <h1>Loading Paper Annotation Workspace</h1>
          <p>Loading summary state, paper queue, and field-level details from the backend.</p>
        </section>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="app-shell">
        <section className="hero loading-panel">
          <p className="eyebrow">Load Error</p>
          <h1>Data Load Failed</h1>
          <p>{loadError}</p>
        </section>
      </div>
    );
  }

  const activePaper = paperDetail && paperDetail.paper_id === selectedPaperId ? paperDetail : null;
  const queuePapers = [...papers]
    .filter((paper) => {
      const hitQuery = !deferredQuery || paper.paper_id.toLowerCase().includes(deferredQuery);
      if (readOnly) {
        return hitQuery;
      }
      const hitFilter =
        paperFilter === "all" ||
        (paperFilter === "pending" && !paper.annotation_summary.is_completed) ||
        (paperFilter === "started" && paper.annotation_summary.has_annotations) ||
        (paperFilter === "completed" && paper.annotation_summary.is_completed);
      return hitQuery && hitFilter;
    })
    .sort((left, right) => {
      if (left.annotation_summary.is_completed !== right.annotation_summary.is_completed) {
        return Number(left.annotation_summary.is_completed) - Number(right.annotation_summary.is_completed);
      }
      if (left.annotation_summary.pending_issue_fields !== right.annotation_summary.pending_issue_fields) {
        return right.annotation_summary.pending_issue_fields - left.annotation_summary.pending_issue_fields;
      }
      return right.false_positive - left.false_positive;
    });

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">{readOnly ? "Benchmark Result Viewer" : "Document Sequence Annotation"}</p>
          <h1>{readOnly ? "Evaluation Detail Dashboard" : "Paper Field Error Review"}</h1>
          <p className="hero-description">
            {readOnly
              ? "Browse papers on the left and inspect GT, prediction, label, score, and reason details on the right."
              : "Review each antibody and field, then save structured error types, final labels, corrected values, and notes."}
          </p>
          <div className="hero-meta">
            {backHref ? (
              <a className="report-link" href={backHref}>
                Back to Result Versions
              </a>
            ) : null}
            <span>Data source: {summary?.dataset_path}</span>
            <span>Papers: {summary?.paper_count ?? 0}</span>
            <span>Antibodies: {summary?.antibody_count ?? 0}</span>
          </div>
        </div>

        <div className="hero-side">
          <div className="score-card">
            <span>Overall Score</span>
            <strong>{summary ? scoreText(summary.accuracy) : "-"}</strong>
          </div>
          {readOnly ? (
            <div className="progress-card">
              <div className="progress-card-head">
                <span>Field Label Distribution</span>
                <strong>{summary?.total_fields ?? 0}</strong>
              </div>
              <div className="progress-track">
                <span style={{ width: progressWidth(((summary?.label_counts.exact ?? 0) / Math.max(summary?.total_fields ?? 1, 1)) * 100) }} />
              </div>
              <p>
                Exact {summary?.label_counts.exact ?? 0}, issue fields{" "}
                {summary ? countIssueLabels(summary.label_counts) : 0}
              </p>
            </div>
          ) : (
            <div className="progress-card">
              <div className="progress-card-head">
                <span>Error Field Review Progress</span>
                <strong>{summary?.annotation_summary.progress_percent.toFixed(1) ?? "0.0"}%</strong>
              </div>
              <div className="progress-track">
                <span style={{ width: progressWidth(summary?.annotation_summary.progress_percent ?? 0) }} />
              </div>
              <p>
                Reviewed {summary?.annotation_summary.reviewed_issue_fields ?? 0} /{" "}
                {summary?.annotation_summary.issue_fields ?? 0} issue fields
              </p>
            </div>
          )}
        </div>
      </header>

      <section className="overview-grid">
        {readOnly ? (
          <>
            <OverviewCard
              title="Total Fields"
              value={`${summary?.total_fields ?? 0}`}
              detail="Total fields evaluated in this result JSON."
              accent="warm"
            />
            <OverviewCard
              title="Exact"
              value={`${summary?.label_counts.exact ?? 0}`}
              detail="Fields automatically evaluated as exact."
              accent="teal"
            />
            <OverviewCard
              title="Issue Fields"
              value={`${summary ? countIssueLabels(summary.label_counts) : 0}`}
              detail="Sum of wrong, miss, and partial fields."
            />
            <OverviewCard
              title="Skipped Fields"
              value={`${summary?.label_counts.skip ?? 0}`}
              detail="Fields automatically marked as skip."
            />
          </>
        ) : (
          <>
            <OverviewCard
              title="Pending Fields"
              value={`${summary?.annotation_summary.pending_issue_fields ?? 0}`}
              detail="Issue fields that still need review."
              accent="warm"
            />
            <OverviewCard
              title="Started Papers"
              value={`${summary?.annotation_summary.started_papers ?? 0}`}
              detail="Papers with at least one saved structured annotation."
            />
            <OverviewCard
              title="Completed Papers"
              value={`${summary?.annotation_summary.completed_papers ?? 0}`}
              detail="Papers whose issue fields have all been reviewed."
              accent="teal"
            />
            <OverviewCard
              title="Database Annotations"
              value={`${summary?.annotation_summary.annotated_fields ?? 0}`}
              detail="Field-level records saved in SQLite."
            />
          </>
        )}
      </section>

      {readOnly && fieldStats ? <FieldStatsTable stats={fieldStats} /> : null}
      {readOnly && sequenceIssueBoard ? <SequenceIssueBoard board={sequenceIssueBoard} /> : null}

      <main className="workspace-grid">
        <aside className="queue-panel panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Paper Queue</p>
              <h2>Paper Queue</h2>
            </div>
            <span className="count-badge">{queuePapers.length}</span>
          </div>

          <div className="queue-filters">
            <label>
              Search Papers
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Enter paper name" />
            </label>
            {!readOnly ? (
              <label>
                Queue Filter
                <select
                  value={paperFilter}
                  onChange={(event) =>
                    setPaperFilter(event.target.value as "all" | "pending" | "started" | "completed")
                  }
                >
                  <option value="pending">Pending first</option>
                  <option value="all">All papers</option>
                  <option value="started">Started</option>
                  <option value="completed">Completed</option>
                </select>
              </label>
            ) : null}
          </div>

          <div className="paper-list">
            {queuePapers.map((paper) => (
              <PaperQueueCard
                key={paper.paper_id}
                paper={paper}
                active={paper.paper_id === selectedPaperId}
                readOnly={readOnly}
                onSelect={() => {
                  startTransition(() => {
                    setSelectedPaperId(paper.paper_id);
                  });
                }}
              />
            ))}
            {queuePapers.length === 0 ? <div className="empty-state">No papers match the current filters.</div> : null}
          </div>
        </aside>

        <section className="detail-panel panel">
          {!activePaper || loadingPaper ? (
            <div className="empty-state large">
              {selectedPaperId ? "Loading paper detail..." : "Select a paper first."}
            </div>
          ) : paperError ? (
            <div className="empty-state large">{paperError}</div>
          ) : (
            <>
              <div className="panel-head detail-head">
                <div>
                  <p className="eyebrow">Paper Detail</p>
                  <h2>{activePaper.paper_id}</h2>
                  <p className="detail-copy">
                    {readOnly
                      ? `This paper has ${activePaper.antibody_count} antibody records, ${countIssueLabels(
                          activePaper.label_counts,
                        )} issue fields, and ${activePaper.label_counts.exact} exact fields.`
                      : `This paper has ${activePaper.antibody_count} antibody records, ${activePaper.annotation_summary.issue_fields} issue fields, and ${activePaper.annotation_summary.reviewed_issue_fields} reviewed fields.`}
                  </p>
                </div>

                <div className="detail-metrics">
                  <div>
                    <span>Score</span>
                    <strong>{scoreText(activePaper.accuracy)}</strong>
                  </div>
                  <div>
                    <span>Extra</span>
                    <strong>{activePaper.false_positive}</strong>
                  </div>
                  <div>
                    <span>Missing</span>
                    <strong>{activePaper.false_negative}</strong>
                  </div>
                  <div>
                    <span>Penalty</span>
                    <strong>{activePaper.penalty_coeff.toFixed(2)}</strong>
                  </div>
                </div>
              </div>

              {!readOnly ? (
                <div className="paper-progress-block">
                  <div className="progress-card-head">
                    <span>Paper Review Progress</span>
                    <strong>{activePaper.annotation_summary.progress_percent.toFixed(1)}%</strong>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: progressWidth(activePaper.annotation_summary.progress_percent) }} />
                  </div>
                  <div className="progress-caption">
                    <span>Issue fields {activePaper.annotation_summary.issue_fields}</span>
                    <span>Reviewed {activePaper.annotation_summary.reviewed_issue_fields}</span>
                    <span>Pending {activePaper.annotation_summary.pending_issue_fields}</span>
                  </div>
                </div>
              ) : null}

              <div className="paper-tags">
                <span className="tag">GT {activePaper.gt_count}</span>
                <span className="tag">Pred {activePaper.pred_count}</span>
                <span className="tag">Matched {activePaper.matched}</span>
                <span className="tag">
                  Extra predictions {activePaper.extra_pred.length > 0 ? activePaper.extra_pred.length : 0}
                </span>
                <span className="tag">
                  Unmatched GT {activePaper.unmatched_gt.length > 0 ? activePaper.unmatched_gt.length : 0}
                </span>
              </div>

              <div className="workspace-toolbar">
                {!readOnly ? (
                  <label>
                    Default Reviewer
                    <input
                      value={reviewer}
                      onChange={(event) => setReviewer(event.target.value)}
                      placeholder="e.g. alice"
                    />
                  </label>
                ) : null}
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={showOnlyIssues}
                    onChange={(event) => setShowOnlyIssues(event.target.checked)}
                  />
                  Show issue fields only
                </label>
                {!readOnly ? (
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={showOnlyPending}
                      onChange={(event) => setShowOnlyPending(event.target.checked)}
                    />
                    Show unfinished reviews only
                  </label>
                ) : null}
              </div>

              <div className="antibody-list">
                {activePaper.antibodies.map((antibody) => {
                  const cardKey = accordionKey(activePaper.paper_id, antibody.antibody_index);
                  const expanded = expandedAntibodies[cardKey] ?? false;
                  const visibleFields = [...antibody.fields]
                    .filter((field) => !showOnlyIssues || isIssueField(field))
                    .filter((field) => !showOnlyPending || needsReview(field))
                    .sort((left, right) => {
                      if (needsReview(left) !== needsReview(right)) {
                        return Number(needsReview(right)) - Number(needsReview(left));
                      }
                      return labelOrder.indexOf(left.label) - labelOrder.indexOf(right.label);
                    });
                  const antibodyLabelCounts = summarizeLabels(visibleFields);

                  return (
                    <section key={cardKey} className="antibody-card">
                      <button
                        type="button"
                        className="antibody-head"
                        onClick={() =>
                          setExpandedAntibodies((current) => ({
                            ...current,
                            [cardKey]: !expanded,
                          }))
                        }
                      >
                        <div>
                          <div className="antibody-title-row">
                            <strong>{antibody.name}</strong>
                            <span className={cn("chip", antibody.matched ? "chip-done" : "chip-warn")}>
                              {antibody.matched ? "Matched" : "Needs Review"}
                            </span>
                          </div>
                          <span className="antibody-subtitle">
                            {readOnly
                              ? `Fields ${visibleFields.length} / ${antibody.fields.length}, issue fields ${countIssueLabels(
                                  antibody.label_counts,
                                )}, exact ${antibody.label_counts.exact}`
                              : `Fields ${visibleFields.length} / ${antibody.fields.length}, issue fields ${antibody.annotation_summary.issue_fields}, reviewed ${antibody.annotation_summary.reviewed_issue_fields}`}
                          </span>
                        </div>
                        <div className="antibody-right">
                          <div className="mini-stat">
                            <span>Antibody Score</span>
                            <strong>{scoreText(antibody.accuracy)}</strong>
                          </div>
                          <div className="mini-stat wide">
                            <span>Visible Field Distribution</span>
                            <StatBar counts={antibodyLabelCounts} />
                          </div>
                          <span className="toggle-text">{expanded ? "Collapse" : "Expand"}</span>
                        </div>
                      </button>

                      {expanded ? (
                        <div className="field-list">
                          {visibleFields.length === 0 ? (
                            <div className="empty-state">No fields match the current filters.</div>
                          ) : (
                            visibleFields.map((field) => {
                              const draft = drafts[fieldKey(field)] ?? buildDraftFromField(field);
                              const sourceDraft = buildDraftFromField(field);
                              const dirty = serializeDraft(draft) !== serializeDraft(sourceDraft);
                              const saveState = saveStates[fieldKey(field)] ?? {
                                state: "idle",
                                message: "",
                              };
                              const sequenceDiff = isSequenceField(field.field)
                                ? buildSequenceDiff(field.pred, field.gt)
                                : null;
                              const annotation = field.annotation;

                              return (
                                <article
                                  key={fieldKey(field)}
                                  className={cn("field-card", `field-card-${labelMeta[field.label].className}`)}
                                >
                                  <div className="field-head">
                                    <div>
                                      <div className="field-title-row">
                                        <h3>{displayFieldName(field.field)}</h3>
                                        <span className="field-code">{field.field}</span>
                                      </div>
                                      <div className="field-chip-row">
                                        <span className={cn("chip", `chip-label-${labelMeta[field.label].className}`)}>
                                          Original label {labelMeta[field.label].label}
                                        </span>
                                        {!readOnly ? (
                                          <>
                                            <span
                                              className={cn("chip", `chip-status-${statusMeta[draft.annotation_status].className}`)}
                                            >
                                              {statusMeta[draft.annotation_status].label}
                                            </span>
                                            <span
                                              className={cn("chip", `chip-severity-${severityMeta[draft.severity].className}`)}
                                            >
                                              Severity {severityMeta[draft.severity].label}
                                            </span>
                                          </>
                                        ) : null}
                                      </div>
                                    </div>

                                    <div className="field-score-group">
                                      <span>Weight {field.weight.toFixed(1)}</span>
                                      <span>Raw score {scoreText(field.score * 100)}</span>
                                      <span>Weighted score {scoreText(field.weighted_score)}</span>
                                    </div>
                                  </div>

                                  <div className="compare-grid">
                                    <section className="compare-card">
                                      <div className="compare-head">
                                        <h4>Model Prediction</h4>
                                        {isSequenceField(field.field) && field.pred ? <span>{field.pred.length} aa</span> : null}
                                      </div>
                                      <RichTextBlock
                                        fieldName={field.field}
                                        value={field.pred}
                                        segments={sequenceDiff ? sequenceDiff.left : undefined}
                                      />
                                    </section>

                                    <section className="compare-card">
                                      <div className="compare-head">
                                        <h4>Ground Truth</h4>
                                        {isSequenceField(field.field) && field.gt ? <span>{field.gt.length} aa</span> : null}
                                      </div>
                                      <RichTextBlock
                                        fieldName={field.field}
                                        value={field.gt}
                                        segments={sequenceDiff ? sequenceDiff.right : undefined}
                                      />
                                    </section>

                                    <section className="compare-card compare-card-reason">
                                      <div className="compare-head">
                                        <h4>Auto-Evaluation Reason</h4>
                                      </div>
                                      <p>{safeText(field.reason)}</p>
                                    </section>
                                  </div>

                                  <ProvenanceBlock provenance={field.provenance} />

                                  {!readOnly ? <div className="annotation-form">
                                    <div className="form-grid">
                                      <label>
                                        Annotation Status
                                        <select
                                          value={draft.annotation_status}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              annotation_status: event.target.value as AnnotationStatus,
                                              error_types:
                                                event.target.value === "ignored" ? [] : draft.error_types,
                                              final_label:
                                                event.target.value === "ignored"
                                                  ? draft.final_label ?? field.label
                                                  : draft.final_label,
                                            })
                                          }
                                        >
                                          <option value="reviewed">Reviewed</option>
                                          <option value="pending">Pending</option>
                                          <option value="ignored">Ignored</option>
                                        </select>
                                      </label>

                                      <label>
                                        Final Label
                                        <select
                                          value={draft.final_label ?? ""}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              final_label: (event.target.value || null) as FieldLabel | null,
                                              error_types:
                                                event.target.value === "exact" ? [] : draft.error_types,
                                            })
                                          }
                                        >
                                          {labelOrder.map((label) => (
                                            <option key={label} value={label}>
                                              {labelMeta[label].label}
                                            </option>
                                          ))}
                                        </select>
                                      </label>

                                      <label>
                                        Severity
                                        <select
                                          value={draft.severity}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              severity: event.target.value as AnnotationSeverity,
                                            })
                                          }
                                        >
                                          <option value="high">High</option>
                                          <option value="medium">Medium</option>
                                          <option value="low">Low</option>
                                        </select>
                                      </label>

                                      <label>
                                        Reviewer
                                        <input
                                          value={draft.reviewer}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              reviewer: event.target.value,
                                            })
                                          }
                                          placeholder={reviewer || "Not filled"}
                                        />
                                      </label>
                                    </div>

                                    <div>
                                      <p className="form-label">Error Type</p>
                                      <div className="error-type-grid">
                                        {(Object.keys(errorTypeMeta) as AnnotationErrorType[]).map((errorType) => {
                                          const active = draft.error_types.includes(errorType);
                                          return (
                                            <button
                                              key={errorType}
                                              type="button"
                                              className={cn("toggle-chip", active && "toggle-chip-active")}
                                              onClick={() =>
                                                updateDraft(field, {
                                                  error_types: active
                                                    ? draft.error_types.filter((item) => item !== errorType)
                                                    : [...draft.error_types, errorType],
                                                })
                                              }
                                              title={errorTypeMeta[errorType].help}
                                            >
                                              {errorTypeMeta[errorType].label}
                                            </button>
                                          );
                                        })}
                                      </div>
                                    </div>

                                    <div className="form-grid form-grid-stack">
                                      <label className="full-width">
                                        Corrected Value
                                        <textarea
                                          value={draft.corrected_value}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              corrected_value: event.target.value,
                                            })
                                          }
                                          placeholder="Enter the human-confirmed value. Use the button below if the ground truth is final."
                                        />
                                      </label>

                                      <label className="full-width">
                                        Review Note
                                        <textarea
                                          value={draft.note}
                                          onChange={(event) =>
                                            updateDraft(field, {
                                              note: event.target.value,
                                            })
                                          }
                                          placeholder="Explain why this is wrong, missing, partial, or add human review context."
                                        />
                                      </label>
                                    </div>

                                    <div className="form-actions">
                                      <div className="form-hints">
                                        <button
                                          type="button"
                                          className="ghost-button"
                                          onClick={() =>
                                            updateDraft(field, {
                                              corrected_value: field.gt,
                                            })
                                          }
                                        >
                                          Use Ground Truth
                                        </button>
                                        <span className={cn("save-hint", `save-hint-${saveState.state}`)}>
                                          {saveState.message ||
                                            (dirty ? "Unsaved changes" : annotation ? `Last saved: ${formatDateTime(annotation.updated_at)}` : "Not saved yet")}
                                        </span>
                                      </div>
                                      <button
                                        type="button"
                                        className="primary-button"
                                        disabled={saveState.state === "saving"}
                                        onClick={() => handleSave(field)}
                                      >
                                        {saveState.state === "saving" ? "Saving..." : "Save to Database"}
                                      </button>
                                    </div>

                                    {annotation ? (
                                      <div className="annotation-meta">
                                        <span>Created {formatDateTime(annotation.created_at)}</span>
                                        <span>Updated {formatDateTime(annotation.updated_at)}</span>
                                        <span>
                                          Final label {annotation.final_label ? labelMeta[annotation.final_label].label : "Unset"}
                                        </span>
                                      </div>
                                    ) : null}
                                  </div> : null}
                                </article>
                              );
                            })
                          )}
                        </div>
                      ) : null}
                    </section>
                  );
                })}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function App() {
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setPathname(window.location.pathname);
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  const reportPath = decodeReportPathFromLocation(pathname);
  if (pathname.startsWith("/reports")) {
    if (!reportPath) {
      return <ReportPage />;
    }
    return (
      <AnnotationApp
        key={reportPath}
        apiPrefix={`/api/result-views/${encodeURIComponent(reportPath)}`}
        readOnly
        backHref="/reports"
      />
    );
  }

  return <AnnotationApp />;
}

export default App;
