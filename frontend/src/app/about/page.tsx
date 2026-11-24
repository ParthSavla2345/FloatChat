"use client";

import { useEffect, useState } from "react";
import { Database, Waves } from "lucide-react";
import { getDatasetSummary } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { DatasetSummary } from "@/lib/types";

export default function AboutPage() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    getDatasetSummary()
      .then((data) => { if (active) setSummary(data); })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Dataset metadata is unavailable."); });
    return () => { active = false; };
  }, []);

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div><p className="eyebrow">Project and data notes</p><h1>About OceanIQ</h1><p>A staged ARGO data retrieval system with a thin interactive interface over read-only analytical services.</p></div>
      </header>
      <section className="panel p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-cyan-50 p-3 text-cyan-900"><Waves size={22} /></div>
          <div><h2 className="section-title">OceanIQ data explorer</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">The backend extracts profile observations from local NetCDF source files, materializes them into DuckDB, and combines Chroma semantic retrieval with structured spatial and temporal filtering. The browser layer uses those services and never executes SQL directly.</p></div>
        </div>
      </section>
      <section className="grid gap-5 lg:grid-cols-2">
        <article className="panel p-6">
          <h2 className="section-title flex items-center gap-2"><Database size={17} /> Current processed dataset</h2>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <AboutMetric label="Observation rows" value={formatNumber(summary?.observation_rows)} />
            <AboutMetric label="Distinct profiles" value={formatNumber(summary?.profile_count)} />
            <AboutMetric label="Project float keys" value={formatNumber(summary?.project_float_count)} />
            <AboutMetric label="Date coverage" value={summary ? `${formatDate(summary.earliest_datetime)} — ${formatDate(summary.latest_datetime)}` : "Not available"} />
          </dl>
        </article>
        <article className="panel p-6">
          <h2 className="section-title">Fields and scientific interpretation</h2>
          <ul className="mt-4 list-inside list-disc space-y-3 text-sm leading-6 text-slate-700">
            <li>Temperature, salinity, and pressure values are exposed where present. Missing values are not synthesized.</li>
            <li>The processed <code>depth</code> column originates from NetCDF pressure (PRES). The interface labels charts with pressure in dbar and does not convert it to geometric depth.</li>
            <li>QC flags are not present in the processed DuckDB schema. Their absence is shown as unavailable, not as passing quality.</li>
            <li>Profile identity uses source file plus profile number. `float_id` is the project key; the processed table does not expose a separate authoritative WMO PLATFORM_NUMBER field.</li>
            <li>Times returned by the profile service are normalized and displayed in UTC.</li>
          </ul>
        </article>
      </section>
      <section className="panel p-6">
        <h2 className="section-title">Backend boundaries</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">The conversational explorer uses the existing query planner, orchestration, Chroma, and DuckDB services. The profile/map APIs are read-only and parameterized, with limits on pages, map markers, and profile levels. No API credentials are sent to the browser.</p>
        {summary ? <p className="mt-3 text-xs text-slate-500">{summary.qc_note} {summary.float_identifier_note}</p> : <p className="mt-3 text-xs text-slate-500">Dataset metadata is not currently available from the backend.</p>}
      </section>
      {error ? <div role="alert" className="error-box">{error}</div> : null}
    </div>
  );
}

function AboutMetric({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-sm font-medium text-slate-900">{value}</dd></div>;
}
