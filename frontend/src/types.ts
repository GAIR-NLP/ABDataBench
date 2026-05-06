export type FieldLabel = "exact" | "partial" | "wrong" | "miss" | "skip";
export type AnnotationStatus = "pending" | "reviewed" | "ignored";
export type AnnotationSeverity = "high" | "medium" | "low";
export type AnnotationErrorType =
  | "value_mismatch"
  | "missing_prediction"
  | "hallucinated_value"
  | "incomplete_value"
  | "format_issue"
  | "evidence_mismatch"
  | "other";

export interface LabelCounts {
  wrong: number;
  miss: number;
  partial: number;
  skip: number;
  exact: number;
}

export interface AnnotationStatusCounts {
  pending: number;
  reviewed: number;
  ignored: number;
}

export interface SeverityCounts {
  high: number;
  medium: number;
  low: number;
}

export interface ErrorTypeCounts {
  value_mismatch: number;
  missing_prediction: number;
  hallucinated_value: number;
  incomplete_value: number;
  format_issue: number;
  evidence_mismatch: number;
  other: number;
}

export interface AnnotationSummary {
  total_fields: number;
  issue_fields: number;
  annotated_fields: number;
  completed_annotations: number;
  reviewed_issue_fields: number;
  pending_issue_fields: number;
  progress_percent: number;
  status_counts: AnnotationStatusCounts;
  final_label_counts: LabelCounts;
  severity_counts: SeverityCounts;
  error_type_counts: ErrorTypeCounts;
  has_annotations: boolean;
  is_completed: boolean;
  started_papers?: number;
  completed_papers?: number;
}

export interface FeedbackSummary {
  total_feedback: number;
  papers_with_feedback: number;
  antibodies_with_feedback: number;
}

export interface SummaryResponse {
  accuracy: number;
  total_fields: number;
  total_score: number;
  total_weight: number;
  total_weighted_score: number;
  paper_count: number;
  antibody_count: number;
  dataset_path: string;
  label_counts: LabelCounts;
  annotation_summary: AnnotationSummary;
  feedback: FeedbackSummary;
}

export interface FieldStatItem {
  field: string;
  total: number;
  label_counts: LabelCounts;
  partial_count: number;
  mismatch_count: number;
  exact_percent: number;
  partial_percent: number;
  mismatch_percent: number;
  skip_percent: number;
}

export interface FieldStatsResponse {
  total_fields: number;
  field_count: number;
  fields: FieldStatItem[];
}

export interface SequenceIssueEntry {
  paper_id: string;
  paper_accuracy: number;
  antibody_index: number;
  antibody_name: string;
  label: FieldLabel;
  score: number;
  reason: string;
  gt: string;
  pred: string;
}

export interface SequenceIssuePaperItem {
  paper_id: string;
  issue_count: number;
}

export interface SequenceIssueFieldItem {
  field: string;
  issue_count: number;
  exact_count: number;
  skip_count: number;
  wrong_count: number;
  miss_count: number;
  partial_count: number;
  paper_count: number;
  issue_percent: number;
  paper_breakdown: SequenceIssuePaperItem[];
  entries: SequenceIssueEntry[];
}

export interface SequenceIssueBoardResponse {
  field_count: number;
  total_sequence_fields: number;
  total_issue_fields: number;
  fields: SequenceIssueFieldItem[];
}

export interface FieldAnnotation {
  id: number;
  paper_id: string;
  antibody_index: number;
  antibody_name: string;
  field_name: string;
  original_label: FieldLabel;
  annotation_status: AnnotationStatus;
  final_label: FieldLabel | null;
  error_types: AnnotationErrorType[];
  severity: AnnotationSeverity;
  corrected_value: string;
  note: string;
  reviewer: string;
  created_at: string;
  updated_at: string;
}

export interface FieldProvenance {
  source_type?: string;
  source_label?: string;
  pointer?: string;
  paper_location?: string;
  source_image?: string;
  source_context?: string;
  api_source_ids?: string;
  api_source_kind?: string;
  quote?: string;
  note?: string;
  from_antibody?: string;
  inherited_from_field?: string;
  action?: string;
  confidence?: string;
  germline?: string;
}

export interface FieldResult {
  field: string;
  weight: number;
  gt: string;
  pred: string;
  score: number;
  weighted_score: number;
  label: FieldLabel;
  reason: string;
  provenance: FieldProvenance;
  paper_id: string;
  antibody_index: number;
  antibody_name: string;
  annotation: FieldAnnotation | null;
}

export interface AntibodyDetail {
  paper_id: string;
  antibody_index: number;
  name: string;
  matched: boolean;
  accuracy: number;
  total_fields: number;
  score_sum: number;
  weight_sum: number;
  weighted_score_sum: number;
  label_counts: LabelCounts;
  fields: FieldResult[];
  annotation_summary: AnnotationSummary;
}

export interface PaperListItem {
  paper_id: string;
  paper_index: number;
  accuracy: number;
  raw_accuracy: number;
  gt_count: number;
  pred_count: number;
  matched: number;
  false_negative: number;
  false_positive: number;
  antibody_count: number;
  label_counts: LabelCounts;
  annotation_summary: AnnotationSummary;
}

export interface FeedbackItem {
  id: number;
  paper_id: string;
  antibody_index: number;
  antibody_name: string;
  field_name: string | null;
  reviewer: string;
  comment: string;
  created_at: string;
  updated_at: string;
}

export interface PaperDetail {
  paper_id: string;
  gt_count: number;
  pred_count: number;
  matched: number;
  false_negative: number;
  false_positive: number;
  unmatched_gt: string[];
  extra_pred: string[];
  penalty_coeff: number;
  raw_accuracy: number;
  accuracy: number;
  antibody_count: number;
  label_counts: LabelCounts;
  antibodies: AntibodyDetail[];
  annotation_summary: AnnotationSummary;
  annotations: FieldAnnotation[];
  feedback: FeedbackItem[];
}

export interface PapersResponse {
  papers: PaperListItem[];
}

export interface ResultViewItem {
  id: string;
  title: string;
  label: string;
  updated_at: string;
  dataset_path: string;
}

export interface ResultViewsResponse {
  views: ResultViewItem[];
  default_id: string;
}

export interface ReportListItem {
  path: string;
  title: string;
  label: string;
  updated_at: string;
  size_bytes: number;
}

export interface ReportsResponse {
  reports: ReportListItem[];
  default_path: string;
  reports_root: string;
}

export interface ReportContentResponse {
  path: string;
  title: string;
  updated_at: string;
  size_bytes: number;
  content: string;
}

export interface AnnotationUpsertPayload {
  paper_id: string;
  antibody_index: number;
  antibody_name: string;
  field_name: string;
  original_label: FieldLabel;
  annotation_status: AnnotationStatus;
  final_label: FieldLabel | null;
  error_types: AnnotationErrorType[];
  severity: AnnotationSeverity;
  corrected_value: string;
  note: string;
  reviewer: string;
}
