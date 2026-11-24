"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, Database, MapPin, Waves } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDatasetSummary } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { DatasetSummary, QueryHistoryItem } from "@/lib/types";

const HISTORY_KEY = "oceaniq.query_history";

export default function Home() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const historyTimer = window.setTimeout(() => {
      try {
        setQueryHistory(JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") as QueryHistoryItem[]);
      } catch {
        setQueryHistory([]);
      }
    }, 0);
    getDatasetSummary()
      .then((dataset) => {
        if (!active) return;
        setSummary(dataset);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Dataset summary is unavailable.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      window.clearTimeout(historyTimer);
    };
  }, []);

  const parameterRows = summary
    ? [
        { name: "Temperature", count: summary.temperature_rows },
        { name: "Salinity", count: summary.salinity_rows },
        { name: "Pressure field", count: summary.depth_rows },
      ]
    : [];

  return (
    <div className="space-y-7">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Oceanographic data workspace</p>
          <h1>ARGO data overview</h1>
          <p>Explore the processed float archive through conversational retrieval, maps, and profile-level measurements.</p>
        </div>
        <div className="connection-pill">
          <span className={`status-dot ${summary ? "status-dot-ok" : loading ? "status-dot-pending" : "status-dot-error"}`} />
          {summary ? "Backend connected" : loading ? "Checking backend" : "Backend unavailable"}
        </div>
      </header>

      {error ? <div role="alert" className="error-box">{error}</div> : null}
      {loading ? <div className="panel p-8 text-sm text-slate-500">Loading dataset summary…</div> : null}

      {!loading && summary ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<Database size={18} />} label="Observation rows" value={formatNumber(summary.observation_rows)} note="Flattened measurement levels" />
            <Metric icon={<FileIcon />} label="Distinct profiles" value={formatNumber(summary.profile_count)} note="File and profile number pairs" />
            <Metric icon={<Waves size={18} />} label="Project float keys" value={formatNumber(summary.project_float_count)} note="Not independently verified WMO IDs" />
            <Metric icon={<Activity size={18} />} label="Source files" value={formatNumber(summary.source_file_count)} note="Processed NetCDF source files" />
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="panel p-5 sm:p-7">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="section-title">Observation data availability</h2>
                  <p className="mt-1 text-sm text-slate-500">Non-null measurement rows per variable; not profile counts.</p>
                </div>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-900">
                  {summary.available_parameters.join(" · ") || "No parameter metadata"}
                </span>
              </div>
              <div className="mt-5 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={parameterRows} margin={{ left: 10, right: 12, bottom: 5 }}>
                    <CartesianGrid stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(value: number) => new Intl.NumberFormat("en", { notation: "compact" }).format(value)} />
                    <Tooltip formatter={(value) => [formatNumber(Number(value)), "Available rows"]} />
                    <Bar dataKey="count" fill="#0e7490" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel p-5 sm:p-7">
              <h2 className="section-title">Dataset coverage</h2>
              <div className="mt-5 space-y-5">
                <Coverage label="Observation dates (UTC)" value={`${formatDate(summary.earliest_datetime)} — ${formatDate(summary.latest_datetime)}`} />
                <Coverage
                  label="Latitude range"
                  value={summary.latitude_min === null || summary.latitude_max === null ? "Not available" : `${summary.latitude_min.toFixed(2)}° to ${summary.latitude_max.toFixed(2)}°`}
                />
                <Coverage
                  label="Longitude range"
                  value={summary.longitude_min === null || summary.longitude_max === null ? "Not available" : `${summary.longitude_min.toFixed(2)}° to ${summary.longitude_max.toFixed(2)}°`}
                />
                <Coverage label="Located observation rows" value={formatNumber(summary.located_observation_rows)} note="This metric counts observation rows with coordinates." />
                <Coverage label="Indian Ocean profiles" value={formatNumber(summary.regional_profile_counts["Indian Ocean"])} note="Profiles within the project's configured Indian Ocean bounds." />
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-xs sm:grid-cols-3">
                {Object.entries(summary.regional_profile_counts).map(([name, count]) => (
                  <div key={name}>
                    <div className="text-slate-500">{name}</div>
                    <div className="mt-1 font-semibold text-slate-800">{formatNumber(count)} profiles</div>
                  </div>
                ))}
              </div>
              <p className="mt-5 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">{summary.float_identifier_note}</p>
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="panel p-5 sm:p-7">
              <h2 className="section-title">Explore OceanIQ</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <QuickLink href="/explorer" title="Ask a question" text="Query verified retrieval services." />
                <QuickLink href="/map" title="Open ocean map" text="Browse actual profile coordinates." />
                <QuickLink href="/profiles" title="Explore profiles" text="Search and paginate profile records." />
                <QuickLink href="/compare" title="Compare profiles" text="Overlay actual measurements." />
              </div>
              <div className="mt-5 border-t border-slate-100 pt-4">
                <h3 className="text-sm font-semibold text-slate-800">Recent queries in this browser</h3>
                {queryHistory.length ? (
                  <ul className="mt-2 space-y-2">
                    {queryHistory.slice(0, 3).map((item) => (
                      <li key={`${item.created_at}-${item.question}`} className="flex flex-col gap-1 text-xs sm:flex-row sm:justify-between">
                        <Link href="/explorer" className="line-clamp-1 text-slate-700 hover:text-cyan-800">{item.question}</Link>
                        <span className="shrink-0 text-slate-500">{item.retrieval_status.replaceAll("_", " ")} · {item.result_count} results</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-2 text-xs text-slate-500">No recent query history is stored.</p>}
              </div>
            </div>
            <div className="panel overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                <div><h2 className="section-title">Processed schema</h2><p className="mt-1 text-xs text-slate-500">Fields available to profile-level retrieval.</p></div>
              </div>
              <div className="grid gap-3 p-5 sm:grid-cols-2">
                <SchemaField label="Profile identity" value="Source file + profile number" />
                <SchemaField label="Project float key" value="float_id" />
                <SchemaField label="Observation time" value="UTC-normalized timestamp" />
                <SchemaField label="Location" value="Latitude / longitude when present" />
                <SchemaField label="Science fields" value="Pressure, temperature, salinity" />
                <SchemaField label="Quality flags" value="Not present in processed schema" />
              </div>
              <div className="border-t border-slate-100 px-5 py-3">
                <Link href="/profiles" className="text-sm font-medium text-cyan-800 hover:underline">Open paginated profile explorer →</Link>
              </div>
            </div>
          </section>

          <section className="panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
            <div className="flex items-start gap-3">
              <MapPin size={19} className="mt-0.5 shrink-0 text-cyan-800" />
              <div>
                <h2 className="font-semibold text-slate-900">Scientific metadata and quality</h2>
                <p className="mt-1 text-sm text-slate-600">QC flag columns are not present in the processed schema. Unavailable QC is not interpreted as good quality.</p>
              </div>
            </div>
            <Link href="/about" className="inline-flex items-center gap-2 text-sm font-medium text-cyan-800 hover:underline">
              Data notes <ArrowRight size={16} />
            </Link>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Metric({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string; note: string }) {
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between text-cyan-800">{icon}<span className="metric-label">{label}</span></div>
      <div className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">{value}</div>
      <p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>
    </div>
  );
}

function Coverage({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div><div className="metric-label">{label}</div><div className="mt-1 text-sm font-medium text-slate-800">{value}</div>{note ? <p className="mt-1 text-xs text-slate-500">{note}</p> : null}</div>;
}

function QuickLink({ href, title, text }: { href: string; title: string; text: string }) {
  return <Link href={href} className="rounded-xl border border-slate-200 p-4 transition hover:border-cyan-600 hover:bg-cyan-50/50"><div className="font-medium text-slate-900">{title}</div><div className="mt-1 text-xs leading-5 text-slate-500">{text}</div></Link>;
}

function SchemaField({ label, value }: { label: string; value: string }) {
  return <div><div className="metric-label">{label}</div><div className="mt-1 text-sm font-medium text-slate-800">{value}</div></div>;
}

function FileIcon() {
  return <Database size={18} />;
}
