"""
Phase 5 — ChromaDB Semantic Index Build
Reads float_metadata.parquet, generates natural language summaries
for each float observation, embeds them using sentence-transformers/all-MiniLM-L6-v2,
and stores them in a persistent ChromaDB collection.

Verified status: this script successfully built the persisted `argo_profiles`
collection in backend/data/chroma/ and returned live search results for the
recovered metadata set. The console output is intentionally kept Windows-safe to
avoid Unicode encoding failures on cp1252 terminals.

Unverified status: later retrieval stages that depend on this semantic layer (for
example spatial/temporal and hybrid retrieval) have not been exercised by the
current recovery validation pass.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from config import settings

# Batch size for embedding (memory-friendly)
EMBED_BATCH_SIZE = 256


def classify_region(lat: float, lon: float) -> str:
    """Classify a lat/lon into an Indian Ocean sub-region."""
    if np.isnan(lat) or np.isnan(lon):
        return "Indian Ocean"
    if 5 <= lat <= 22 and 80 <= lon <= 100:
        return "Bay of Bengal"
    if 5 <= lat <= 25 and 55 <= lon <= 78:
        return "Arabian Sea"
    if -10 <= lat <= 10 and 60 <= lon <= 90:
        return "Equatorial Indian Ocean"
    if lat < -20:
        return "Southern Indian Ocean"
    return "Indian Ocean"


def _as_float(value):
    """Return a float or NaN for the provided value."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _normalise_float_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Adapt the float-level metadata summary to the schema expected by the index builder."""
    df = df.copy()

    if "latitude" not in df.columns:
        lat_min = df["latitude_min"] if "latitude_min" in df.columns else pd.Series(np.nan, index=df.index)
        lat_max = df["latitude_max"] if "latitude_max" in df.columns else pd.Series(np.nan, index=df.index)
        df["latitude"] = lat_min.combine(lat_max, lambda a, b: (a + b) / 2 if pd.notna(a) and pd.notna(b) else np.nan)

    if "longitude" not in df.columns:
        lon_min = df["longitude_min"] if "longitude_min" in df.columns else pd.Series(np.nan, index=df.index)
        lon_max = df["longitude_max"] if "longitude_max" in df.columns else pd.Series(np.nan, index=df.index)
        df["longitude"] = lon_min.combine(lon_max, lambda a, b: (a + b) / 2 if pd.notna(a) and pd.notna(b) else np.nan)

    if "time" not in df.columns:
        if "observation_start" in df.columns:
            df["time"] = df["observation_start"]
        elif "observation_end" in df.columns:
            df["time"] = df["observation_end"]
        else:
            df["time"] = pd.NaT

    if "file_name" not in df.columns:
        df["file_name"] = df.get("float_id", "UNKNOWN")

    if "n_profiles" not in df.columns and "total_profiles" in df.columns:
        df["n_profiles"] = df["total_profiles"]
    if "n_levels" not in df.columns and "total_observations" in df.columns:
        df["n_levels"] = df["total_observations"]

    df["latitude"] = df["latitude"].apply(_as_float)
    df["longitude"] = df["longitude"].apply(_as_float)
    return df


def generate_summary(row: pd.Series) -> str:
    """Generate a natural language description for a float observation."""
    lat = _as_float(row.get("latitude", np.nan))
    lon = _as_float(row.get("longitude", np.nan))
    time_val = row.get("time", None)
    float_id = str(row.get("float_id", "UNKNOWN")).strip()
    profile_count = int(row.get("n_profiles", row.get("total_profiles", 0)) or 0)
    observation_count = int(row.get("n_levels", row.get("total_observations", 0)) or 0)
    file_name = str(row.get("file_name", float_id))

    lat_str = f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}" if not np.isnan(lat) else "unknown latitude"
    lon_str = f"{abs(lon):.2f}°{'E' if lon >= 0 else 'W'}" if not np.isnan(lon) else "unknown longitude"

    if pd.notna(time_val):
        t = pd.Timestamp(time_val)
        date_str = t.strftime("%B %d, %Y")
        year_str = str(t.year)
        month_str = t.strftime("%B")
    else:
        date_str = "unknown date"
        year_str = "unknown year"
        month_str = "unknown month"

    region = classify_region(lat, lon)

    summary = (
        f"ARGO float {float_id} operated in the {region} "
        f"at {lat_str}, {lon_str} on {date_str}. "
        f"This float collected {profile_count} profiles and {observation_count} depth-level observations, "
        f"capturing pressure, temperature, and salinity data during {month_str} {year_str}. "
        f"Source record: {file_name}."
    )
    return summary


def main():
    metadata_path = settings.float_metadata_parquet
    chroma_dir = settings.chroma_dir

    if not metadata_path.exists():
        print(f"[ERROR] Metadata parquet not found: {metadata_path}")
        print("[ERROR] Please run generate_metadata.py first.")
        sys.exit(1)

    settings.ensure_dirs()

    print(f"\n[INFO] Loading metadata: {metadata_path}")
    meta_df = pd.read_parquet(metadata_path)
    print(f"[INFO] Loaded {len(meta_df):,} metadata records")

    meta_df = _normalise_float_metadata(meta_df)
    meta_df = meta_df.dropna(subset=["latitude", "longitude"])
    print(f"[INFO] {len(meta_df):,} records after dropping missing lat/lon")

    # ── Load embedding model ──────────────────────────────────────────────
    print(f"\n[INFO] Loading embedding model: {settings.embedding_model}")
    print("[INFO] (This may download ~80MB on first run...)")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.embedding_model)
    print("[INFO] Model loaded successfully")

    # ── Initialize ChromaDB ───────────────────────────────────────────────
    print(f"\n[INFO] Initializing ChromaDB at: {chroma_dir}")
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_dir))

    # Delete and recreate collection for fresh build
    try:
        client.delete_collection(settings.chroma_collection_name)
        print(f"[INFO] Deleted existing collection '{settings.chroma_collection_name}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine", "description": "ARGO Indian Ocean float observations"}
    )
    print(f"[INFO] Created collection: {settings.chroma_collection_name}")

    # ── Generate summaries and index in batches ───────────────────────────
    print(f"\n[INFO] Generating summaries and embeddings for {len(meta_df):,} records...")
    print(f"[INFO] Batch size: {EMBED_BATCH_SIZE}\n")

    t_start = time.time()
    total_indexed = 0

    for batch_start in range(0, len(meta_df), EMBED_BATCH_SIZE):
        batch = meta_df.iloc[batch_start: batch_start + EMBED_BATCH_SIZE]
        batch_num = batch_start // EMBED_BATCH_SIZE + 1

        # Generate summaries
        summaries = [generate_summary(row) for _, row in batch.iterrows()]

        # Generate embeddings
        embeddings = model.encode(summaries, show_progress_bar=False).tolist()

        # Build IDs (unique string)
        ids = [f"float_{row.get('float_id', 'UNK')}_{row.get('file_name', '')}_{i}"
               for i, (_, row) in enumerate(batch.iterrows())]
        # Ensure IDs are URL-safe strings
        ids = [str(id_).replace(" ", "_")[:128] for id_ in ids]

        # Build metadata dicts
        metadatas = []
        for _, row in batch.iterrows():
            time_val = row.get("time", None)
            time_str = pd.Timestamp(time_val).isoformat() if pd.notna(time_val) else ""
            lat = row.get("latitude", np.nan)
            lon = row.get("longitude", np.nan)
            metadatas.append({
                "float_id": str(row.get("float_id", "UNKNOWN")),
                "latitude": float(lat) if not np.isnan(lat) else 0.0,
                "longitude": float(lon) if not np.isnan(lon) else 0.0,
                "time": time_str,
                "file_name": str(row.get("file_name", "")),
                "region": classify_region(lat, lon),
            })

        # Add to ChromaDB
        collection.add(
            ids=ids,
            documents=summaries,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        total_indexed += len(batch)
        elapsed = time.time() - t_start
        rate = total_indexed / elapsed if elapsed > 0 else 0

        if batch_num % 10 == 0 or batch_start + EMBED_BATCH_SIZE >= len(meta_df):
            print(f"  Batch {batch_num:>4} | Indexed {total_indexed:>7,}/{len(meta_df):,} | "
                  f"{rate:.0f} records/sec | {elapsed:.1f}s elapsed")

    elapsed_total = time.time() - t_start

    # ── Verify ────────────────────────────────────────────────────────────
    count = collection.count()
    print()
    print("=== CHROMA INDEX BUILD COMPLETE ===")
    print(f"ChromaDB path     : {chroma_dir}")
    print(f"Collection        : {settings.chroma_collection_name}")
    print(f"Total indexed     : {count:,}")
    print(f"Time elapsed      : {elapsed_total:.1f} seconds")
    print(f"Avg rate          : {total_indexed / elapsed_total:.0f} records/sec")
    print()

    # Test query
    print("[INFO] Running test semantic query...")
    test_results = collection.query(
        query_texts=["Bay of Bengal temperature profiles 2023"],
        n_results=3
    )
    print("[INFO] Test results:")
    for i, (doc, meta) in enumerate(zip(
        test_results["documents"][0],
        test_results["metadatas"][0]
    )):
        time_value = meta.get("time") or ""
        short_time = time_value[:10] if isinstance(time_value, str) else ""
        print(f"  [{i+1}] {doc[:100]}...")
        print(f"       float_id={meta.get('float_id')}, region={meta.get('region')}, time={short_time}")
    print()


if __name__ == "__main__":
    main()
