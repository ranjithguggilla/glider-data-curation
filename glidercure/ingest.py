"""
Glider data ingestion from IOOS Glider DAC.

Downloads mission segment NetCDFs from the IOOS Glider DAC
ERDDAP server. Supports both individual segment downloads and
full-mission bulk retrieval via the ERDDAP tabledap API.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional

import requests

from glidercure.config import GLIDER_DAC_ERDDAP, MissionConfig

logger = logging.getLogger(__name__)

# Timeout for ERDDAP requests (seconds)
REQUEST_TIMEOUT = 120


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_mission_netcdf(
    mission: MissionConfig,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Path:
    """
    Download the full mission dataset as a single NetCDF from ERDDAP.

    Uses the ERDDAP tabledap API to request all variables for the
    mission's dataset ID in NetCDF format.

    Args:
        mission: Mission configuration.
        output_dir: Override output directory.
        dry_run: If True, log what would happen without downloading.

    Returns:
        Path to the downloaded NetCDF file.
    """
    output_dir = output_dir or mission.raw_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_id = mission.erddap_dataset_id or mission.mission_id
    filename = f"{dataset_id}.nc"
    output_path = output_dir / filename

    # Build ERDDAP tabledap URL for NetCDF download
    variables = ",".join(mission.variables)
    url = f"{GLIDER_DAC_ERDDAP}/tabledap/{dataset_id}.nc?{variables}"

    if dry_run:
        logger.info("DRY RUN: would download %s → %s", url, output_path)
        return output_path

    logger.info("Downloading mission %s from ERDDAP...", dataset_id)
    logger.info("URL: %s", url)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        digest = sha256_file(output_path)
        logger.info("Downloaded %.1f MB → %s (sha256: %s...)", size_mb, output_path, digest[:16])

        # Write checksum sidecar
        sidecar = output_path.with_suffix(".nc.sha256")
        sidecar.write_text(f"{digest}  {filename}\n")

        return output_path

    except requests.RequestException as e:
        logger.error("Download failed for %s: %s", dataset_id, e)
        raise


def list_available_missions(
    search_term: str = "Gulf",
) -> List[dict]:
    """
    Search IOOS Glider DAC ERDDAP for available missions.

    Args:
        search_term: Search string (e.g., "Gulf", "Slocum").

    Returns:
        List of dicts with dataset_id, title, institution.
    """
    url = (
        f"{GLIDER_DAC_ERDDAP}/search/index.json"
        f"?page=1&itemsPerPage=20&searchFor={search_term}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error("ERDDAP search failed: %s", e)
        return []

    rows = data.get("table", {}).get("rows", [])
    col_names = data.get("table", {}).get("columnNames", [])

    missions = []
    for row in rows:
        entry = dict(zip(col_names, row))
        missions.append({
            "dataset_id": entry.get("Dataset ID", ""),
            "title": entry.get("Title", ""),
            "institution": entry.get("Institution", ""),
        })

    return missions


def ingest_from_local(
    segment_files: List[Path],
    output_dir: Path,
    mission_id: str,
) -> List[Path]:
    """
    Ingest local segment NetCDF files into the raw directory.

    Copies segment files and generates SHA-256 sidecars.

    Args:
        segment_files: List of local segment NetCDF paths.
        output_dir: Destination directory.
        mission_id: Mission identifier.

    Returns:
        List of ingested file paths.
    """
    import shutil

    dest_dir = output_dir / mission_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    ingested = []
    for src in sorted(segment_files):
        dst = dest_dir / src.name
        shutil.copy2(src, dst)

        digest = sha256_file(dst)
        sidecar = dst.with_suffix(dst.suffix + ".sha256")
        sidecar.write_text(f"{digest}  {dst.name}\n")

        ingested.append(dst)
        logger.info("Ingested %s (%s...)", dst.name, digest[:16])

    logger.info("Ingested %d segment files for mission %s", len(ingested), mission_id)
    return ingested
