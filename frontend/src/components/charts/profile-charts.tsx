"use client";

import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProfileDetail } from "@/lib/types";

const parameterStyle = {
  temperature: { label: "Temperature", unit: "°C", color: "#0e7490" },
  salinity: { label: "Salinity", unit: "PSU", color: "#7c3aed" },
} as const;

type Parameter = keyof typeof parameterStyle;

function points(profile: ProfileDetail, parameter: Parameter) {
  return profile.measurements
    .filter((row) => row.depth !== null && row[parameter] !== null)
    .map((row) => ({ value: row[parameter], pressure: row.depth }));
}

export function ProfileChart({ profile, parameter }: { profile: ProfileDetail; parameter: Parameter }) {
  const style = parameterStyle[parameter];
  const data = points(profile, parameter);
  if (!data.length) {
    return <p className="chart-empty">No {style.label.toLowerCase()} measurements are available in this profile.</p>;
  }
  return (
    <div className="chart-frame">
      <p className="chart-caption">{style.label} vs. pressure</p>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 16 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="value"
            name={style.label}
            unit={` ${style.unit}`}
            label={{ value: `${style.label} (${style.unit})`, position: "insideBottom", offset: -12 }}
          />
          <YAxis
            type="number"
            dataKey="pressure"
            name="Pressure"
            unit=" dbar"
            reversed
            label={{ value: "Pressure (dbar; stored in depth column)", angle: -90, position: "insideLeft" }}
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Legend />
          <Scatter name={style.label} data={data} fill={style.color} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComparisonChart({
  profiles,
  parameter,
}: {
  profiles: ProfileDetail[];
  parameter: Parameter;
}) {
  const style = parameterStyle[parameter];
  const available = profiles
    .map((profile) => ({ profile, data: points(profile, parameter) }))
    .filter((item) => item.data.length > 0);
  const missing = profiles.filter((profile) => points(profile, parameter).length === 0);
  if (!available.length) {
    return <p className="chart-empty">None of the selected profiles contain {style.label.toLowerCase()} and pressure values.</p>;
  }
  return (
    <div className="chart-frame">
      <p className="chart-caption">Overlay by actual pressure levels · {style.label} ({style.unit})</p>
      {missing.length ? (
        <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
          No paired {style.label.toLowerCase()} and pressure values for: {missing.map((profile) => `${profile.float_id} profile ${profile.profile_number}`).join(", ")}.
        </p>
      ) : null}
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 16 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="value"
            name={style.label}
            unit={` ${style.unit}`}
            label={{ value: `${style.label} (${style.unit})`, position: "insideBottom", offset: -12 }}
          />
          <YAxis
            type="number"
            dataKey="pressure"
            name="Pressure"
            unit=" dbar"
            reversed
            label={{ value: "Pressure (dbar; stored in depth column)", angle: -90, position: "insideLeft" }}
          />
          <Tooltip />
          <Legend />
          {available.map(({ profile, data }, index) => (
            <Scatter
              key={profile.profile_key}
              name={`${profile.float_id} · profile ${profile.profile_number}`}
              data={data}
              fill={["#0e7490", "#7c3aed", "#ea580c", "#16a34a"][index % 4]}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TemperatureSalinityChart({ profile }: { profile: ProfileDetail }) {
  const data = profile.measurements
    .filter((row) => row.temperature !== null && row.salinity !== null)
    .map((row) => ({ temperature: row.temperature, salinity: row.salinity, pressure: row.depth }));
  if (!data.length) {
    return <p className="chart-empty">No rows contain both temperature and salinity values.</p>;
  }
  return (
    <div className="chart-frame">
      <p className="chart-caption">Co-located temperature and salinity observations · no interpolation</p>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 16 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="temperature"
            name="Temperature"
            unit=" °C"
            label={{ value: "Temperature (°C)", position: "insideBottom", offset: -12 }}
          />
          <YAxis
            type="number"
            dataKey="salinity"
            name="Salinity"
            unit=" PSU"
            label={{ value: "Salinity (PSU)", angle: -90, position: "insideLeft" }}
          />
          <Tooltip />
          <Scatter name="Observed pairs" data={data} fill="#0e7490" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
