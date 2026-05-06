import { useEffect, useState } from "react";
import type { ResultViewItem, ResultViewsResponse } from "./types";

function formatDateTime(value: string) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}${month}${day}`;
}

function encodeResultHref(viewId: string) {
  return `/reports/${encodeURIComponent(viewId)}`;
}

export function ReportPage() {
  const [views, setViews] = useState<ResultViewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setLoading(true);
      try {
        const response = await fetch("/api/result-views");
        if (!response.ok) {
          throw new Error(`Failed to load result versions: ${response.status}`);
        }
        const payload = (await response.json()) as ResultViewsResponse;
        if (cancelled) return;
        setViews(payload.views);
        setError("");
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Failed to load result versions");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="report-shell">
      <section className="hero report-hero">
        <div>
          <div className="eyebrow">Benchmark Result Versions</div>
          <h1>Evaluation Result Versions</h1>
          <p className="hero-description">
            Select a benchmark result version to inspect paper-level, antibody-level, and field-level scores.
          </p>
        </div>
        <div className="report-summary-card">
          <span>Current View</span>
          <strong>{views[0]?.title ?? "No result version configured"}</strong>
          <p>{views[0] ? formatDateTime(views[0].updated_at) : " "}</p>
        </div>
      </section>

      <section className="report-layout">
        <section className="panel report-content-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Available Versions</p>
              <h2>Result Directory</h2>
            </div>
            <span>{views.length}</span>
          </div>

          {loading ? <p className="empty-state">Loading result versions...</p> : null}
          {!loading && error ? <p className="empty-state">{error}</p> : null}
          {!loading && !error && !views.length ? <p className="empty-state">No result versions are available.</p> : null}

          <div className="report-list">
            {views.map((view) => (
              <a key={view.id} className="report-list-item" href={encodeResultHref(view.id)}>
                <strong>{view.title}</strong>
                <span>{view.label}</span>
                <small>{formatDateTime(view.updated_at)}</small>
              </a>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
