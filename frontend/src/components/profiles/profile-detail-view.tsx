"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, GitCompare, MapPin } from "lucide-react";
import { getProfile } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { ProfileDetail } from "@/lib/types";
import { ProfileChart, TemperatureSalinityChart } from "@/components/charts/profile-charts";

export function ProfileDetailView() {
  return (
    <Suspense fallback={<div className="panel p-8 text-sm text-slate-500">Loading profile…</div>}>
      <ProfileDetailContent />
    </Suspense>
  );
}

function ProfileDetailContent() {
  const search = useSearchParams();
  const fileName = search.get("file_name") || "";
  const profileNumber = Number(search.get("profile_number"));
  const [profile, setProfile] = useState<ProfileDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [measurementPage, setMeasurementPage] = useState(0);
  const invalidRequest = !fileName || !Number.isInteger(profileNumber) || profileNumber < 1;

  useEffect(() => {
    if (invalidRequest) return;
    let active = true;
    getProfile(fileName, profileNumber)
      .then((value) => {
        if (active) setProfile(value);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Profile request failed.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [fileName, profileNumber, invalidRequest]);

  if (invalidRequest) return <div role="alert" className="error-box">A source file and valid profile number are required.</div>;
  if (loading) return <div className="panel p-8 text-sm text-slate-500">Loading actual profile measurements…</div>;
  if (error) return <div role="alert" className="error-box">{error}</div>;
  if (!profile) return <div className="empty-state">No profile matched this source file and profile number.</div>;

  const compareHref = `/compare?profiles=${encodeURIComponent(JSON.stringify([{ file_name: profile.file_name, profile_number: profile.profile_number }]))}`;
  const pageSize = 50;
  const pageCount = Math.max(1, Math.ceil(profile.measurements.length / pageSize));
  const visibleMeasurements = profile.measurements.slice(measurementPage * pageSize, (measurementPage + 1) * pageSize);
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <Link href="/profiles" className="mb-3 inline-flex items-center gap-2 text-sm text-cyan-800 hover:underline">
            <ArrowLeft size={16} /> Back to profiles
          </Link>
          <p className="eyebrow">Individual profile</p>
          <h1>Profile {profile.profile_number}</h1>
          <p>{profile.file_name}</p>
        </div>
        <Link href={compareHref} className="secondary-button">
          <GitCompare size={16} /> Compare this profile
        </Link>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <DetailMetric label="Project float key" value={profile.float_id} />
        <DetailMetric label="Cycle number" value={String(profile.cycle_number)} />
        <DetailMetric label="Observation time (UTC)" value={formatDateTime(profile.datetime)} />
        <DetailMetric label="Measurement levels" value={formatNumber(profile.observation_count)} />
      </section>

      <section className="panel p-5 sm:p-7">
        <h2 className="section-title flex items-center gap-2"><MapPin size={17} /> Location and available data</h2>
        <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <DetailItem label="Latitude" value={profile.latitude === null ? "Not available" : `${profile.latitude}°`} />
          <DetailItem label="Longitude" value={profile.longitude === null ? "Not available" : `${profile.longitude}°`} />
          <DetailItem label="Available fields" value={Object.entries(profile.available_parameters).filter(([, available]) => available).map(([name]) => name === "depth" ? "pressure/depth field" : name).join(", ") || "None"} />
          <DetailItem label="QC data" value={profile.qc_available ? "Available" : "Not available in processed schema"} />
        </div>
        <p className="mt-4 text-xs leading-5 text-slate-500">
          The stored <code>depth</code> field is sourced from NetCDF pressure (PRES). It is charted as pressure in dbar, not converted to geometric depth.
        </p>
        {profile.truncated ? <p className="mt-2 text-xs text-amber-800">This profile contains {profile.observation_count} measurement levels; the chart and table show the first {profile.returned_measurement_count} returned levels.</p> : null}
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="panel p-4 sm:p-6"><ProfileChart profile={profile} parameter="temperature" /></div>
        <div className="panel p-4 sm:p-6"><ProfileChart profile={profile} parameter="salinity" /></div>
      </section>
      <section className="panel p-4 sm:p-6"><TemperatureSalinityChart profile={profile} /></section>

      <section className="panel overflow-hidden">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="section-title">Measurement levels</h2>
          <p className="mt-1 text-xs text-slate-500">Missing values remain blank; no interpolation is applied.</p>
        </div>
        <div className="max-h-[480px] overflow-auto">
          <table className="data-table">
            <thead><tr><th>Pressure (dbar)</th><th>Temperature (°C)</th><th>Salinity (PSU)</th></tr></thead>
            <tbody>
              {visibleMeasurements.map((row, index) => (
                <tr key={`${row.depth}-${index}`}>
                  <td>{row.depth ?? "—"}</td><td>{row.temperature ?? "—"}</td><td>{row.salinity ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3">
          <span className="text-xs text-slate-500">Showing {visibleMeasurements.length} levels on this page · {profile.returned_measurement_count} returned of {profile.observation_count} total</span>
          <div className="flex gap-2">
            <button type="button" className="secondary-button" disabled={measurementPage === 0} onClick={() => setMeasurementPage((page) => page - 1)}>Previous</button>
            <span className="self-center text-xs text-slate-500">{measurementPage + 1}/{pageCount}</span>
            <button type="button" className="secondary-button" disabled={measurementPage + 1 >= pageCount} onClick={() => setMeasurementPage((page) => page + 1)}>Next</button>
          </div>
        </div>
      </section>

      <p className="text-xs text-slate-500">{profile.qc_note}</p>
    </div>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return <div className="panel p-4"><div className="metric-label">{label}</div><div className="mt-2 break-all text-sm font-semibold text-slate-900">{value}</div></div>;
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return <div><div className="metric-label">{label}</div><div className="mt-1 font-medium text-slate-800">{value}</div></div>;
}
