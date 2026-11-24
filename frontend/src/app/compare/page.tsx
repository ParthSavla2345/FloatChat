"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, X } from "lucide-react";
import { ComparisonChart } from "@/components/charts/profile-charts";
import { getProfile } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ProfileDetail } from "@/lib/types";

type ProfileReference = { file_name: string; profile_number: number };

export default function ComparePage() {
  return <Suspense fallback={<div className="panel p-8 text-sm text-slate-500">Loading comparison…</div>}><CompareProfiles /></Suspense>;
}

function CompareProfiles() {
  const search = useSearchParams();
  const [profiles, setProfiles] = useState<ProfileDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const references = useMemo(() => {
    try {
      const parsed = JSON.parse(search.get("profiles") || "[]") as ProfileReference[];
      return parsed.filter((item) => typeof item.file_name === "string" && Number.isInteger(item.profile_number)).slice(0, 4);
    } catch {
      return [];
    }
  }, [search]);

  useEffect(() => {
    let active = true;
    if (!references.length) {
      return;
    }
    Promise.all(references.map((item) => getProfile(item.file_name, item.profile_number, 2000)))
      .then((values) => {
        if (active) setProfiles(values.filter((value): value is ProfileDetail => Boolean(value)));
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Profiles could not be loaded for comparison.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [references]);

  function removeProfile(profile: ProfileDetail) {
    const remaining = profiles.filter((item) => item.profile_key !== profile.profile_key);
    setProfiles(remaining);
    const query = encodeURIComponent(JSON.stringify(remaining.map(({ file_name, profile_number }) => ({ file_name, profile_number }))));
    window.history.replaceState(null, "", `/compare?profiles=${query}`);
  }

  const comparable = profiles.length >= 2;
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <Link href="/profiles" className="mb-3 inline-flex items-center gap-2 text-sm text-cyan-800 hover:underline"><ArrowLeft size={16} /> Select profiles</Link>
          <p className="eyebrow">Scientific comparison</p>
          <h1>Profile Comparison</h1>
          <p>Compare actual temperature and salinity measurements against their recorded pressure levels. Up to four profiles can be compared.</p>
        </div>
        <Link href="/profiles" className="primary-button">Add profiles in explorer</Link>
      </header>

      {error ? <div role="alert" className="error-box">{error}</div> : null}
      {loading && references.length ? <div className="panel p-8 text-sm text-slate-500">Loading selected profile measurements…</div> : null}
      {(!loading || !references.length) && !error && profiles.length < 2 ? (
        <div className="empty-state">
          Select at least two profiles from the Profile Explorer to compare them.
          <p className="mt-2 text-xs">This page currently has {profiles.length} selected profile(s).</p>
        </div>
      ) : null}

      {!loading && profiles.length ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {profiles.map((profile) => (
              <article key={profile.profile_key} className="panel relative p-4">
                <button type="button" className="absolute right-3 top-3 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-900" aria-label="Remove profile" onClick={() => removeProfile(profile)}><X size={16} /></button>
                <p className="eyebrow">Profile {profile.profile_number}</p>
                <h2 className="mt-1 break-all pr-7 font-semibold text-slate-900">{profile.float_id}</h2>
                <p className="mt-1 break-all text-xs text-slate-500">{profile.file_name}</p>
                <dl className="mt-4 space-y-2 text-sm">
                  <CompareField label="Observed at" value={formatDateTime(profile.datetime)} />
                  <CompareField label="Location" value={`${profile.latitude}, ${profile.longitude}`} />
                  <CompareField label="Levels" value={String(profile.observation_count)} />
                  <CompareField label="Parameters" value={Object.entries(profile.available_parameters).filter(([, yes]) => yes).map(([name]) => name).join(", ") || "None"} />
                </dl>
                <p className="mt-3 text-xs text-slate-500">QC flags: not available in processed schema.</p>
              </article>
            ))}
          </section>

          {comparable ? (
            <>
              <section className="panel overflow-hidden">
                <div className="border-b border-slate-200 px-5 py-4">
                  <h2 className="section-title">Differences from reference profile</h2>
                  <p className="mt-1 text-xs text-slate-500">Straight-line surface distance and absolute observation-time difference; unavailable when source fields are missing.</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="data-table min-w-[700px]">
                    <thead><tr><th>Profile</th><th>Reference</th><th>Coordinate distance</th><th>Time difference</th></tr></thead>
                    <tbody>
                      {profiles.slice(1).map((profile) => {
                        const reference = profiles[0];
                        const distance = coordinateDistance(reference, profile);
                        const timeHours = reference.datetime && profile.datetime
                          ? Math.abs(Date.parse(reference.datetime) - Date.parse(profile.datetime)) / 3600000
                          : null;
                        return (
                          <tr key={profile.profile_key}>
                            <td>{profile.float_id} · profile {profile.profile_number}</td>
                            <td>{reference.float_id} · profile {reference.profile_number}</td>
                            <td>{distance === null ? "Not available" : `${distance.toFixed(1)} km`}</td>
                            <td>{timeHours === null ? "Not available" : `${timeHours.toFixed(1)} hours`}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="grid gap-5 xl:grid-cols-2">
                <div className="panel p-4 sm:p-6"><ComparisonChart profiles={profiles} parameter="temperature" /></div>
                <div className="panel p-4 sm:p-6"><ComparisonChart profiles={profiles} parameter="salinity" /></div>
              </section>
            </>
          ) : (
            <div className="empty-state">Add another profile to enable direct profile overlays.</div>
          )}

          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
            Measurements are plotted only where both the parameter and pressure values are present. Profiles are overlaid at their observed pressure coordinates; no interpolation, statistical significance, or scientific conclusion is inferred.
          </div>
        </>
      ) : null}
    </div>
  );
}

function CompareField({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="break-words font-medium text-slate-800">{value}</dd></div>;
}

function coordinateDistance(
  first: ProfileDetail,
  second: ProfileDetail,
): number | null {
  if (first.latitude === null || first.longitude === null || second.latitude === null || second.longitude === null) return null;
  const radians = (value: number) => value * Math.PI / 180;
  const lat1 = radians(first.latitude);
  const lat2 = radians(second.latitude);
  const deltaLat = radians(second.latitude - first.latitude);
  const deltaLon = radians(second.longitude - first.longitude);
  const raw = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  const a = Math.min(1, Math.max(0, raw));
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
