from __future__ import annotations

import calendar
import re
from datetime import date, datetime

from models.schemas import QueryPlan


class QueryPlanner:
    """Rule-based planner that translates natural-language ARGO questions into Stage-7-compatible query objects."""

    SUPPORTED_PARAMETERS = {
        "temperature": ("temperature", "temp", "thermal"),
        "salinity": ("salinity", "salt", "sal"),
        "depth": ("depth", "pressure", "pres"),
    }
    REGION_ALIASES = {
        "Arabian Sea": ("arabian sea", "arabiansea"),
        "Bay of Bengal": ("bay of bengal", "bengal bay"),
        "Equatorial Indian Ocean": ("equatorial indian ocean", "equatorial io", "equatorial indian"),
        "Southern Indian Ocean": ("southern indian ocean", "southern io"),
        "Indian Ocean": ("indian ocean", "io"),
    }
    UNSUPPORTED_PARAMETER_HINTS = (
        "chlorophyll",
        "oxygen",
        "nitrate",
        "phosphate",
        "silicate",
        "dissolved oxygen",
        "sea surface height",
        "ssh",
    )
    MONTHS = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    @classmethod
    def plan(cls, query: str) -> QueryPlan:
        if not isinstance(query, str):
            raise TypeError("Query must be a string.")

        raw_query = " ".join(query.strip().split())
        if not raw_query:
            raise ValueError("Natural-language query cannot be empty.")

        parameters, unsupported = cls._extract_parameters(raw_query)
        region = cls._extract_region(raw_query)
        latitude, longitude = cls._extract_coordinates(raw_query)
        bounding_box = cls._extract_bounding_box(raw_query)
        radius_km = cls._extract_radius(raw_query)
        start_date, end_date = cls._extract_date_range(raw_query)
        top_k = cls._extract_result_limit(raw_query)

        interpretation_notes: list[str] = []
        validation_warnings: list[str] = []

        if parameters:
            interpretation_notes.append(f"Detected supported parameters: {', '.join(parameters)}.")
        else:
            interpretation_notes.append("No supported ARGO parameters were detected; semantic retrieval will use the full query text.")

        if region:
            interpretation_notes.append(f"Using supported region constraint: {region}.")
        elif re.search(r"(?i)\b(?:sea|ocean|coast|bay|gulf|atlantic|pacific|mediterranean|caribbean)\b", raw_query):
            validation_warnings.append("A geographic location was mentioned but could not be resolved reliably to a supported project region. Please specify one of: Arabian Sea, Bay of Bengal, Equatorial Indian Ocean, Southern Indian Ocean, Indian Ocean.")

        if latitude is not None and longitude is not None:
            interpretation_notes.append(f"Detected coordinate constraint at ({latitude}, {longitude}).")
        elif bounding_box:
            interpretation_notes.append(f"Detected bounding box: {bounding_box}.")

        if radius_km is not None:
            interpretation_notes.append(f"Detected radius constraint: {radius_km} km.")
            if radius_km < 0:
                validation_warnings.append("Radius must be non-negative; a negative radius is not supported.")

        if start_date or end_date:
            interpretation_notes.append(f"Detected temporal window: {start_date} to {end_date}.")
        if start_date and end_date and start_date > end_date:
            validation_warnings.append("Start date is later than end date; the query cannot be executed as written.")

        for raw_value in re.findall(r"(?i)(?:lat(?:itude)?|latitude)\s*[:=]?\s*(-?\d{1,3}(?:\.\d+)?)", raw_query):
            if float(raw_value) < -90 or float(raw_value) > 90:
                validation_warnings.append("Latitude is outside the supported range [-90, 90].")
        for raw_value in re.findall(r"(?i)(?:lon(?:gitude)?|longitude)\s*[:=]?\s*(-?\d{1,3}(?:\.\d+)?)", raw_query):
            if float(raw_value) < -180 or float(raw_value) > 180:
                validation_warnings.append("Longitude is outside the supported range [-180, 180].")

        if radius_km is not None and radius_km < 0:
            validation_warnings.append("Radius must be non-negative; a negative radius is not supported.")

        if unsupported:
            validation_warnings.append(f"Unsupported scientific parameters were mentioned: {', '.join(sorted(set(unsupported)))}. Only temperature, salinity, and depth are validated in the current retrieval layer.")

        if not any([parameters, region, latitude is not None, longitude is not None, bounding_box, start_date, end_date]):
            interpretation_notes.append("No explicit spatial or temporal constraints were recognized; the planner will preserve the original query for semantic search only.")

        semantic_query = cls._build_semantic_query(raw_query, parameters, region)

        plan = QueryPlan(
            original_query=raw_query,
            semantic_query=semantic_query,
            parameters=parameters,
            region=region,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            bounding_box=bounding_box,
            start_date=start_date,
            end_date=end_date,
            top_k=top_k,
            interpretation_notes=interpretation_notes,
            validation_warnings=validation_warnings,
        )
        return plan

    @classmethod
    def _build_semantic_query(cls, query: str, parameters: list[str], region: str | None) -> str:
        q = query.strip()
        for param in parameters:
            q = re.sub(rf"(?i)\b{re.escape(param)}\b", "", q)
        q = re.sub(r"(?i)\b(?:find|show|return|search|look for|display|top|limit)\b", " ", q)
        q = re.sub(r"(?i)\b(?:in|the|during|between|from|to|near|around|within|for)\b", " ", q)
        if region:
            q = re.sub(rf"(?i)\b{re.escape(region)}\b", " ", q)
        q = re.sub(r"\s+", " ", q).strip()
        if region:
            base = q.strip()
            q = f"{region} {base}".strip() if base else region
        if not q:
            q = query.strip()
        return q.strip()

    @classmethod
    def _extract_parameters(cls, query: str) -> tuple[list[str], list[str]]:
        lower = query.lower()
        parameters: list[str] = []
        unsupported: list[str] = []

        for canonical, aliases in cls.SUPPORTED_PARAMETERS.items():
            if any(re.search(rf"\b{re.escape(alias)}\b", lower) for alias in aliases):
                parameters.append(canonical)

        for hint in cls.UNSUPPORTED_PARAMETER_HINTS:
            if re.search(rf"\b{re.escape(hint)}\b", lower):
                unsupported.append(hint)

        return parameters, unsupported

    @classmethod
    def _extract_region(cls, query: str) -> str | None:
        lower = query.lower()
        matches: list[str] = []
        for region, aliases in cls.REGION_ALIASES.items():
            for alias in aliases:
                if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lower):
                    matches.append(region)
                    break
        if not matches:
            return None
        return matches[0]

    @classmethod
    def _extract_coordinates(cls, query: str) -> tuple[float | None, float | None]:
        latitude = cls._find_coordinate(query, "latitude")
        longitude = cls._find_coordinate(query, "longitude")
        if latitude is not None and (latitude < -90 or latitude > 90):
            latitude = None
        if longitude is not None and (longitude < -180 or longitude > 180):
            longitude = None
        if latitude is None and longitude is None:
            directional_lat, directional_lon = cls._extract_directional_coordinates(query)
            if directional_lat is not None:
                latitude = directional_lat
            if directional_lon is not None:
                longitude = directional_lon
        return latitude, longitude

    @classmethod
    def _extract_directional_coordinates(cls, query: str) -> tuple[float | None, float | None]:
        patterns = [
            r"(?i)(-?\d{1,3}(?:\.\d+)?)\s*(N|S|E|W|north|south|east|west)\b",
            r"(?i)\b(?:near|around)\s*(-?\d{1,3}(?:\.\d+)?)\s*(N|S|E|W|north|south|east|west)\b",
        ]
        lat_values: list[float] = []
        lon_values: list[float] = []

        for pattern in patterns:
            for match in re.finditer(pattern, query):
                value = float(match.group(1))
                direction = (match.group(2) or "").lower()
                if direction in {"n", "north"}:
                    lat_values.append(value)
                elif direction in {"s", "south"}:
                    lat_values.append(-value)
                elif direction in {"e", "east"}:
                    lon_values.append(value)
                elif direction in {"w", "west"}:
                    lon_values.append(-value)

        if lat_values:
            latitude = float(lat_values[0])
        else:
            latitude = None
        if lon_values:
            longitude = float(lon_values[0])
        else:
            longitude = None
        return latitude, longitude

    @classmethod
    def _find_coordinate(cls, query: str, axis: str) -> float | None:
        patterns = [
            rf"(?i)\b(?:{axis}|{axis}itude)\s*[:=]?\s*(-?\d{{1,3}}(?:\.\d+)?)\b",
            rf"(?i)\b(?:{axis}|{axis}itude)\s+of\s*(-?\d{{1,3}}(?:\.\d+)?)\b",
            rf"(?i)\b(?:near|around|at)\s*(-?\d{{1,3}}(?:\.\d+)?)\s*(?:and|,)?\s*(?:{axis}|{axis}itude)?\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return float(match.group(1))
        return None

    @classmethod
    def _extract_bounding_box(cls, query: str) -> dict[str, float] | None:
        lat_match = re.search(
            r"(?i)(?:lat(?:itude)?|latitude)\s*[:=]?\s*(-?\d{1,3}(?:\.\d+)?)\s*(?:to|-|–|and)\s*(-?\d{1,3}(?:\.\d+)?)",
            query,
        )
        lon_match = re.search(
            r"(?i)(?:lon(?:gitude)?|longitude)\s*[:=]?\s*(-?\d{1,3}(?:\.\d+)?)\s*(?:to|-|–|and)\s*(-?\d{1,3}(?:\.\d+)?)",
            query,
        )
        if not lat_match or not lon_match:
            return None

        lat_min, lat_max = sorted((float(lat_match.group(1)), float(lat_match.group(2))))
        lon_min, lon_max = sorted((float(lon_match.group(1)), float(lon_match.group(2))))

        if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
            return None
        if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180):
            return None

        return {
            "latitude_min": round(lat_min, 6),
            "latitude_max": round(lat_max, 6),
            "longitude_min": round(lon_min, 6),
            "longitude_max": round(lon_max, 6),
        }

    @classmethod
    def _extract_radius(cls, query: str) -> float | None:
        match = re.search(r"(?i)(?:within|radius|around|nearby)\s*(?:of)?\s*(-?\d+(?:\.\d+)?)\s*(?:km|kilometer|kilometres|kilometers|k)\b", query)
        if not match:
            return None
        return float(match.group(1))

    @classmethod
    def _extract_date_range(cls, query: str) -> tuple[str | None, str | None]:
        iso_dates = []
        for match in re.finditer(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", query):
            year, month, day = map(int, match.groups())
            try:
                iso_dates.append(date(year, month, day).isoformat())
            except ValueError:
                continue
        if iso_dates:
            start = min(iso_dates)
            end = max(iso_dates)
            return start, end

        range_pattern = r"(?i)(?:between|from)\s+([A-Za-z]+)\s*(?:and|to)\s+([A-Za-z]+)\s+(\d{4})"
        range_match = re.search(range_pattern, query)
        if range_match:
            start_month = cls._month_number(range_match.group(1))
            end_month = cls._month_number(range_match.group(2))
            year = int(range_match.group(3))
            if start_month is None or end_month is None:
                return None, None
            return cls._iso_month_start(year, start_month), cls._iso_month_end(year, end_month)

        month_year_match = re.search(r"(?i)\b([A-Za-z]+)\s+(\d{4})\b", query)
        if month_year_match:
            month = cls._month_number(month_year_match.group(1))
            year = int(month_year_match.group(2))
            if month is not None:
                return cls._iso_month_start(year, month), cls._iso_month_end(year, month)

        year_match = re.search(r"(?i)\b(19\d{2}|20\d{2})\b", query)
        if year_match:
            year = int(year_match.group(1))
            return f"{year}-01-01", f"{year}-12-31"

        return None, None

    @classmethod
    def _month_number(cls, month_name: str) -> int | None:
        return cls.MONTHS.get(month_name.lower())

    @classmethod
    def _iso_month_start(cls, year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}-01"

    @classmethod
    def _iso_month_end(cls, year: int, month: int) -> str:
        last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{last_day:02d}"

    @classmethod
    def _extract_result_limit(cls, query: str) -> int:
        limit_match = re.search(r"(?i)\b(?:top|limit|show)\s+(\d{1,2})\b", query)
        if limit_match:
            return max(1, min(int(limit_match.group(1)), 20))
        return 5


def plan_query(query: str) -> QueryPlan:
    """Compatibility wrapper for direct use without a class instance."""
    return QueryPlanner.plan(query)
