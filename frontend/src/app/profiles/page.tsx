"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowDownUp, GitCompare, Search } from "lucide-react";
import { buildProfileDetailUrl, getProfiles } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { ProfileRecord } from "@/lib/types";

const pageSize = 50;
const regions = ["Arabian Sea", "Bay of Bengal", "Equatorial Indian Ocean", "Southern Indian Ocean", "Indian Ocean"];
type SortKey = "datetime" | "float_id" | "profile_number" | "observation_count";

export default function ProfilesPage() {
  return <Suspense fallback={<div className="panel p-8 text-sm text-slate-500">Loading profile explorer…</div>}><ProfileList /></Suspense>;
}

function ProfileList() {
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [region, setRegion] = useState("");
  const [parameter, setParameter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [offset, setOffset] = useState(0);
  const [profiles, setProfiles] = useState<ProfileRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Record<string, ProfileRecord>>({});
  const [sortKey, setSortKey] = useState<SortKey>("datetime");
  const [sortDescending, setSortDescending] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(nextOffset = 0) {
    setLoading(true);
    setError(null);
    try {
      const page = await getProfiles({
        limit: pageSize,
        offset: nextOffset,
        search: search || undefined,
        region: region || undefined,
        parameter: parameter || undefined,
        start_datetime: startDate || undefined,
        end_datetime: endDate || undefined,
      });
      setProfiles(page.results);
      setTotal(page.total_count);
      setOffset(nextOffset);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Profile data could not be loaded.");
      setProfiles([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(() => load(0));
    // Initial profile fetch; explicit filter submission reloads with selected constraints.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    void load(0);
  }

  const sortedProfiles = useMemo(() => {
    return [...profiles].sort((a, b) => {
      const left = a[sortKey];
      const right = b[sortKey];
      let comparison: number;
      if (typeof left === "number" && typeof right === "number") comparison = left - right;
      else comparison = String(left ?? "").localeCompare(String(right ?? ""));
      return sortDescending ? -comparison : comparison;
    });
  }, [profiles, sortKey, sortDescending]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDescending((value) => !value);
    else {
      setSortKey(key);
      setSortDescending(key === "datetime");
    }
  }

  const selectedProfiles = Object.values(selected);
  const compareHref = `/compare?profiles=${encodeURIComponent(JSON.stringify(selectedProfiles.map(({ file_name, profile_number }) => ({ file_name, profile_number }))))}`;

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Profile-level data</p>
          <h1>Profile Explorer</h1>
          <p>Search paginated profile summaries and open the stored measurement levels for inspection. Select two to four profiles for comparison.</p>
        </div>
        <Link href={compareHref} aria-disabled={selectedProfiles.length < 2} className={`primary-button ${selectedProfiles.length < 2 ? "pointer-events-none opacity-50" : ""}`}>
          <GitCompare size={16} /> Compare selected ({selectedProfiles.length})
        </Link>
      </header>

      <form onSubmit={applyFilters} className="panel grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-6">
        <label className="filter-field sm:col-span-2"><span>Search float, source file, or profile number</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search identifiers" /></label>
        <label className="filter-field"><span>Region</span><select value={region} onChange={(event) => setRegion(event.target.value)}><option value="">All regions</option>{regions.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="filter-field"><span>Parameter present</span><select value={parameter} onChange={(event) => setParameter(event.target.value)}><option value="">Any parameter</option><option value="temperature">Temperature</option><option value="salinity">Salinity</option><option value="depth">Pressure field</option></select></label>
        <label className="filter-field"><span>Start date</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label className="filter-field"><span>End date</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        <button type="submit" className="primary-button sm:col-span-2 xl:col-span-6" disabled={loading}><Search size={16} /> Apply filters</button>
      </form>

      {error ? <div role="alert" className="error-box">{error}</div> : null}
      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="section-title">Profiles</h2>
            <p className="mt-1 text-xs text-slate-500">{loading ? "Loading profile page…" : `${formatNumber(total)} matching profiles · ${profiles.length} shown`}</p>
          </div>
          <p className="text-xs text-slate-500">Profile identity: source file + profile number</p>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[1050px]">
            <thead>
              <tr>
                <th>Select</th>
                <SortableHeader label="Project float key" active={sortKey === "float_id"} onClick={() => toggleSort("float_id")} />
                <SortableHeader label="Profile #" active={sortKey === "profile_number"} onClick={() => toggleSort("profile_number")} />
                <SortableHeader label="Observation time" active={sortKey === "datetime"} onClick={() => toggleSort("datetime")} />
                <th>Location</th>
                <SortableHeader label="Levels" active={sortKey === "observation_count"} onClick={() => toggleSort("observation_count")} />
                <th>Available parameters</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {!loading && sortedProfiles.map((profile) => (
                <tr key={profile.profile_key}>
                  <td>
                    <input
                      aria-label={`Select profile ${profile.profile_number} from ${profile.file_name}`}
                      type="checkbox"
                      checked={Boolean(selected[profile.profile_key])}
                      disabled={!selected[profile.profile_key] && selectedProfiles.length >= 4}
                      onChange={(event) => setSelected((current) => {
                        const next = { ...current };
                        if (event.target.checked) next[profile.profile_key] = profile;
                        else delete next[profile.profile_key];
                        return next;
                      })}
                    />
                  </td>
                  <td><span className="font-medium">{profile.float_id}</span><span className="block text-xs text-slate-500">{profile.file_name}</span></td>
                  <td>{profile.profile_number}</td>
                  <td>{formatDateTime(profile.datetime)}</td>
                  <td>{profile.latitude?.toFixed(3) ?? "—"}, {profile.longitude?.toFixed(3) ?? "—"}</td>
                  <td>{formatNumber(profile.observation_count)}</td>
                  <td>{Object.entries(profile.available_parameters).filter(([, yes]) => yes).map(([name]) => name).join(", ") || "None"}</td>
                  <td><Link href={buildProfileDetailUrl(profile.file_name, profile.profile_number)} className="font-medium text-cyan-800 hover:underline">Open profile</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !error && !profiles.length ? <div className="empty-state">No profiles matched these filters.</div> : null}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
          <button type="button" className="secondary-button" disabled={loading || offset === 0} onClick={() => void load(Math.max(0, offset - pageSize))}>Previous</button>
          <span className="text-xs text-slate-500">Page {Math.floor(offset / pageSize) + 1} of {Math.max(1, Math.ceil(total / pageSize))}</span>
          <button type="button" className="secondary-button" disabled={loading || offset + pageSize >= total} onClick={() => void load(offset + pageSize)}>Next</button>
        </div>
      </section>
      <p className="text-xs text-slate-500">The processed dataset contains no QC fields. Profile measurements are loaded only after opening a selected profile; the full observation dataset is not sent to the browser.</p>
    </div>
  );
}

function SortableHeader({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return <th><button type="button" onClick={onClick} className={`inline-flex items-center gap-1 ${active ? "text-cyan-900" : ""}`}>{label}<ArrowDownUp size={13} /></button></th>;
}
