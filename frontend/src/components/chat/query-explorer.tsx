"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUp, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { runQuery } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { OrchestrationResult, QueryHistoryItem } from "@/lib/types";

const examples = [
  "Find temperature observations in the Arabian Sea.",
  "Show salinity profiles in the Bay of Bengal.",
  "Find ARGO floats near latitude 0 and longitude 80 within 500 km.",
  "Show available observations from March 2023.",
];
const HISTORY_KEY = "oceaniq.query_history";

export function QueryExplorer() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [showExplanation, setShowExplanation] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        setHistory(JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") as QueryHistoryItem[]);
      } catch {
        setHistory([]);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await runQuery(value);
      setResult(response);
      const nextHistory = [
        { question: value, retrieval_status: response.retrieval_status, result_count: response.result_count, created_at: new Date().toISOString() },
        ...history.filter((item) => item.question !== value),
      ].slice(0, 10);
      setHistory(nextHistory);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The query could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  function clearConversation() {
    setResult(null);
    setQuestion("");
    setHistory([]);
    localStorage.removeItem(HISTORY_KEY);
  }

  const plan = result?.query_plan ?? {};
  const semanticText = typeof plan.semantic_query === "string" ? plan.semantic_query : "Not available";
  const parameters = Array.isArray(plan.parameters) ? plan.parameters.join(", ") : "Not specified";
  const region = typeof plan.region === "string" ? plan.region : "Not specified";
  const start = typeof plan.start_date === "string" ? plan.start_date : "Not specified";
  const end = typeof plan.end_date === "string" ? plan.end_date : "Not specified";

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Conversational retrieval</p>
          <h1>AI Explorer</h1>
          <p>Ask a question in natural language. The rule-based planner and hybrid retrieval service report how it was interpreted.</p>
        </div>
        <button type="button" onClick={clearConversation} className="secondary-button">
          <RotateCcw size={16} /> Clear conversation
        </button>
      </header>

      <section className="panel p-5 sm:p-7">
        <form onSubmit={submit}>
          <label htmlFor="question" className="field-label">Your question</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            maxLength={1000}
            className="query-input"
            placeholder="For example: Find temperature observations in the Arabian Sea."
          />
          <div className="mt-4 flex flex-wrap gap-2">
            {examples.map((example) => (
              <button key={example} type="button" className="suggestion-chip" onClick={() => setQuestion(example)}>
                {example}
              </button>
            ))}
          </div>
          <div className="mt-5 flex items-center justify-between gap-4">
            <p className="text-xs text-slate-500">The browser does not call an external LLM provider.</p>
            <button type="submit" className="primary-button" disabled={loading || !question.trim()}>
              {loading ? <span className="loading-dot" /> : <ArrowUp size={17} />}
              {loading ? "Retrieving…" : "Run query"}
            </button>
          </div>
        </form>
        {error ? <div role="alert" className="error-box mt-5">{error}</div> : null}
      </section>

      {loading ? (
        <section className="panel p-8 text-center" aria-live="polite">
          <div className="loading-dot mx-auto" />
          <p className="mt-3 text-sm text-slate-500">Planning query and retrieving matching ARGO data…</p>
        </section>
      ) : null}

      {result ? (
        <section className="panel overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
            <div>
              <p className="eyebrow">Retrieval response</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-900">{result.retrieval_status.replaceAll("_", " ")}</h2>
            </div>
            <div className="rounded-full bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-900">
              {formatNumber(result.result_count)} result(s)
            </div>
          </div>
          <div className="space-y-6 p-5 sm:p-7">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Original question</div>
              <p className="mt-2 text-slate-900">{result.original_query}</p>
            </div>

            <button
              type="button"
              onClick={() => setShowExplanation((visible) => !visible)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left font-semibold text-slate-800"
              aria-expanded={showExplanation}
            >
              Query interpretation and retrieval details
              {showExplanation ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            {showExplanation ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <InfoCard label="Parameters" value={parameters} />
                <InfoCard label="Region" value={region} />
                <InfoCard label="Date range" value={`${start} → ${end}`} />
                <InfoCard label="Semantic query" value={semanticText} />
                <InfoCard label="Applied filters" value={JSON.stringify(result.applied_filters, null, 2)} />
                <InfoCard label="Ranking" value={JSON.stringify(result.ranking_explanation, null, 2)} />
              </div>
            ) : null}

            <MessageList label="Interpretation notes" items={result.interpretation_notes} />
            <MessageList label="Validation warnings" items={result.validation_warnings} empty="No validation warnings." />
            <MessageList label="Limitations" items={result.limitations} empty="No additional limitations were returned." />

            <div>
              <h3 className="section-title">Retrieved candidates</h3>
              {result.results.length ? (
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {result.results.map((item, index) => (
                    <article key={`${String(item.float_id)}-${index}`} className="rounded-xl border border-slate-200 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h4 className="font-semibold text-slate-900">Project float key: {String(item.float_id ?? "Unavailable")}</h4>
                          <p className="mt-1 text-xs text-slate-500">Source file: {String(item.source_file ?? "Unavailable")}</p>
                        </div>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                          Score {String(item.hybrid_score ?? "Unavailable")}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">
                        {String(item.latitude ?? "—")}, {String(item.longitude ?? "—")} · {formatDateTime(typeof item.earliest_datetime === "string" ? item.earliest_datetime : null)}
                      </p>
                      <Link
                        href={`/profiles?search=${encodeURIComponent(String(item.float_id ?? ""))}`}
                        className="mt-3 inline-block text-sm font-medium text-cyan-800 hover:underline"
                      >
                        Find matching profiles
                      </Link>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">The retrieval completed without matching candidates.</p>
              )}
              <p className="mt-3 text-xs text-slate-500">Hybrid candidates are float-level summaries; individual profiles are available in the Profile Explorer.</p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="panel p-5 sm:p-7">
        <h2 className="section-title">Recent queries</h2>
        {history.length ? (
          <div className="mt-4 divide-y divide-slate-100">
            {history.map((item) => (
              <button
                key={`${item.created_at}-${item.question}`}
                type="button"
                onClick={() => setQuestion(item.question)}
                className="flex w-full flex-col gap-1 py-3 text-left sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="text-sm text-slate-800">{item.question}</span>
                <span className="text-xs text-slate-500">
                  {item.retrieval_status.replaceAll("_", " ")} · {item.result_count} result(s) · {formatDateTime(item.created_at)}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Queries made in this browser will appear here until cleared.</p>
        )}
      </section>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-800">{value}</pre>
    </div>
  );
}

function MessageList({ label, items, empty }: { label: string; items: string[]; empty?: string }) {
  return (
    <div>
      <h3 className="section-title">{label}</h3>
      {items.length ? (
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-700">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : <p className="mt-2 text-sm text-slate-500">{empty || "None returned."}</p>}
    </div>
  );
}
