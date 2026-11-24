import type {
  DatasetSummary,
  MapProfiles,
  OrchestrationResult,
  ProfileDetail,
  ProfilePage,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

function resolveApiUrl(path: string) {
  if (!API_BASE_URL) return path;
  const normalizedBase = API_BASE_URL.replace(/\/$/, "");
  return `${normalizedBase}${path}`;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(url), init);
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}.`);
  }
  return payload;
}

function queryString(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && String(value).trim() !== "") {
      search.set(key, String(value));
    }
  }
  return search.toString();
}

export function getDatasetSummary() {
  return requestJson<DatasetSummary>("/api/data/summary");
}

export function getProfiles(params: {
  limit?: number;
  offset?: number;
  search?: string;
  parameter?: string;
  region?: string;
  start_datetime?: string;
  end_datetime?: string;
  latitude_min?: number;
  latitude_max?: number;
  longitude_min?: number;
  longitude_max?: number;
}) {
  return requestJson<ProfilePage>(`/api/data/profiles?${queryString(params)}`);
}

export function getMapProfiles(params: {
  limit?: number;
  search?: string;
  parameter?: string;
  region?: string;
  start_datetime?: string;
  end_datetime?: string;
  latitude_min?: number;
  latitude_max?: number;
  longitude_min?: number;
  longitude_max?: number;
}) {
  return requestJson<MapProfiles>(`/api/data/map?${queryString(params)}`);
}

export function getProfile(fileName: string, profileNumber: number, limit = 3000) {
  return requestJson<ProfileDetail>(
    `/api/data/profile?${queryString({ file_name: fileName, profile_number: profileNumber, limit })}`,
  );
}

export function runQuery(question: string) {
  return requestJson<OrchestrationResult>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function buildProfileDetailUrl(fileName: string, profileNumber: number) {
  return `/profiles/detail?${queryString({ file_name: fileName, profile_number: profileNumber })}`;
}
