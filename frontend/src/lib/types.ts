export type AvailableParameters = {
  temperature: boolean;
  salinity: boolean;
  depth: boolean;
};

export type ProfileRecord = {
  profile_key: string;
  file_name: string;
  float_id: string;
  profile_number: number;
  cycle_number: number;
  datetime: string | null;
  latitude: number | null;
  longitude: number | null;
  observation_count: number;
  temperature_count?: number;
  salinity_count?: number;
  depth_count?: number;
  min_pressure_or_depth?: number | null;
  max_pressure_or_depth?: number | null;
  available_parameters: AvailableParameters;
  qc_available: boolean;
};

export type ProfileMeasurement = {
  depth: number | null;
  temperature: number | null;
  salinity: number | null;
};

export type ProfileDetail = Omit<ProfileRecord, "temperature_count" | "salinity_count" | "depth_count"> & {
  qc_note: string;
  returned_measurement_count: number;
  measurements: ProfileMeasurement[];
  truncated: boolean;
};

export type DatasetSummary = {
  observation_rows: number;
  profile_count: number;
  project_float_count: number;
  source_file_count: number;
  temperature_rows: number;
  salinity_rows: number;
  depth_rows: number;
  earliest_datetime: string | null;
  latest_datetime: string | null;
  latitude_min: number | null;
  latitude_max: number | null;
  longitude_min: number | null;
  longitude_max: number | null;
  located_observation_rows: number;
  available_parameters: string[];
  regional_profile_counts: Record<string, number>;
  qc_available: boolean;
  qc_note: string;
  float_identifier_note: string;
};

export type ProfilePage = {
  results: ProfileRecord[];
  total_count: number;
  limit: number;
  offset: number;
};

export type MapProfiles = {
  results: MapProfileRecord[];
  returned_count: number;
  limit: number;
};

export type MapProfileRecord = ProfileRecord & { latitude: number; longitude: number };

export type OrchestrationResult = {
  original_query: string;
  query_plan: Record<string, unknown>;
  interpretation_notes: string[];
  applied_filters: Record<string, unknown>;
  validation_warnings: string[];
  retrieval_status: string;
  results: Array<Record<string, unknown>>;
  result_count: number;
  ranking_explanation: Record<string, unknown>;
  limitations: string[];
};

export type QueryHistoryItem = {
  question: string;
  retrieval_status: string;
  result_count: number;
  created_at: string;
};
