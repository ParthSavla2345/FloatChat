"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { buildProfileDetailUrl, getMapProfiles } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { MapProfileRecord } from "@/lib/types";

const ArgoMap = dynamic(
  () => import("@/components/map/argo-map").then((module) => module.ArgoMap),
  { ssr: false, loading: () => <div className="map-frame grid place-items-center text-sm text-slate-500">Loading interactive map…</div> },
);

const regions = ["Arabian Sea", "Bay of Bengal", "Equatorial Indian Ocean", "Southern Indian Ocean", "Indian Ocean"];

export default function MapPage() {
  const [profiles, setProfiles] = useState<MapProfileRecord[]>([]);
  const [selected, setSelected] = useState<MapProfileRecord | null>(null);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("");
  const [parameter, setParameter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [latitudeMin, setLatitudeMin] = useState("");
  const [latitudeMax, setLatitudeMax] = useState("");
  const [longitudeMin, setLongitudeMin] = useState("");
  const [longitudeMax, setLongitudeMax] = useState("");
  const [returned, setReturned] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadMap() {
    setLoading(true);
    setError(null);
    try {
      const response = await getMapProfiles({
        limit: 1500,
        search: search || undefined,
        region: region || undefined,
        parameter: parameter || undefined,
        start_datetime: startDate || undefined,
        end_datetime: endDate || undefined,
        latitude_min: latitudeMin ? Number(latitudeMin) : undefined,
        latitude_max: latitudeMax ? Number(latitudeMax) : undefined,
        longitude_min: longitudeMin ? Number(longitudeMin) : undefined,
        longitude_max: longitudeMax ? Number(longitudeMax) : undefined,
      });
      setProfiles(response.results);
      setReturned(response.returned_count);
      setSelected(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Map profiles could not be loaded.");
      setProfiles([]);
      setReturned(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(() => loadMap());
    // Load only after mount; filters are applied by the explicit button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Spatial exploration</p>
          <h1>ARGO ocean map</h1>
          <p>Markers represent actual distinct profile locations returned from DuckDB, not generated float positions.</p>
        </div>
        <div className="connection-pill">{formatNumber(returned)} locations loaded · max 1,500</div>
      </header>

      <section className="panel grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
        <label className="filter-field"><span>Float / source file</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Project float key or file" /></label>
        <label className="filter-field">
          <span>Region</span>
          <select value={region} onChange={(event) => setRegion(event.target.value)}>
            <option value="">All available locations</option>
            {regions.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="filter-field">
          <span>Parameter</span>
          <select value={parameter} onChange={(event) => setParameter(event.target.value)}>
            <option value="">Any available</option>
            <option value="temperature">Temperature</option>
            <option value="salinity">Salinity</option>
            <option value="depth">Pressure field</option>
          </select>
        </label>
        <label className="filter-field"><span>Start date</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label className="filter-field"><span>End date</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        <label className="filter-field"><span>Minimum latitude</span><input type="number" min="-90" max="90" value={latitudeMin} onChange={(event) => setLatitudeMin(event.target.value)} placeholder="-90" /></label>
        <label className="filter-field"><span>Maximum latitude</span><input type="number" min="-90" max="90" value={latitudeMax} onChange={(event) => setLatitudeMax(event.target.value)} placeholder="90" /></label>
        <label className="filter-field"><span>Minimum longitude</span><input type="number" min="-180" max="180" value={longitudeMin} onChange={(event) => setLongitudeMin(event.target.value)} placeholder="-180" /></label>
        <label className="filter-field"><span>Maximum longitude</span><input type="number" min="-180" max="180" value={longitudeMax} onChange={(event) => setLongitudeMax(event.target.value)} placeholder="180" /></label>
        <button type="button" className="primary-button sm:col-span-2 xl:col-span-4" disabled={loading} onClick={() => void loadMap()}>
          {loading ? "Loading…" : "Apply filters"}
        </button>
      </section>

      {error ? <div role="alert" className="error-box">{error}</div> : null}
      <section className="grid gap-5 xl:grid-cols-[1fr_320px]">
        <div className="panel overflow-hidden p-2">
          {loading ? <div className="map-frame grid place-items-center text-sm text-slate-500">Fetching profile coordinates…</div> : null}
          {!loading ? <ArgoMap profiles={profiles} onSelect={setSelected} /> : null}
          {!loading && !error && profiles.length === 0 ? <p className="px-4 pb-4 text-sm text-slate-500">No profile locations matched these filters.</p> : null}
        </div>
        <aside className="panel p-5">
          <p className="eyebrow">Selected profile</p>
          {selected ? (
            <>
              <h2 className="mt-2 break-all text-lg font-semibold text-slate-900">Profile {selected.profile_number}</h2>
              <dl className="mt-4 space-y-3 text-sm">
                <MapField label="Project float key" value={selected.float_id} />
                <MapField label="Source file" value={selected.file_name} />
                <MapField label="Coordinates" value={`${selected.latitude.toFixed(4)}, ${selected.longitude.toFixed(4)}`} />
                <MapField label="Observation time" value={formatDateTime(selected.datetime)} />
                <MapField label="Measurement levels" value={formatNumber(selected.observation_count)} />
                <MapField label="Available fields" value={Object.entries(selected.available_parameters).filter(([, yes]) => yes).map(([name]) => name).join(", ") || "None"} />
              </dl>
              <Link href={buildProfileDetailUrl(selected.file_name, selected.profile_number)} className="primary-button mt-5 w-full">
                Inspect profile
              </Link>
              <Link
                href={`/compare?profiles=${encodeURIComponent(JSON.stringify([{ file_name: selected.file_name, profile_number: selected.profile_number }]))}`}
                className="secondary-button mt-2 w-full"
              >
                Add to comparison
              </Link>
            </>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">Select a marker to inspect the profile metadata. Coordinates and measurements come from the processed observation table.</p>
          )}
          <p className="mt-5 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500">
            Marker results are capped at 1,500 for responsiveness. Selecting filters runs a bounded DuckDB query.
          </p>
        </aside>
      </section>
    </div>
  );
}

function MapField({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-0.5 break-words font-medium text-slate-800">{value}</dd></div>;
}
