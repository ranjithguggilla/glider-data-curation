"""
Segment merge into CF trajectory NetCDF.

Merges multiple glider segment NetCDFs into a single mission-level
CF-compliant trajectory file following the IOOS Glider DAC trajectory
specification and CF-1.8 discrete sampling geometry conventions.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# CF-1.8 trajectory feature type attributes
CF_TRAJECTORY_ATTRS = {
    "Conventions": "CF-1.8, ACDD-1.3",
    "featureType": "trajectory",
    "cdm_data_type": "Trajectory",
    "standard_name_vocabulary": "CF Standard Name Table v79",
}

# Standard variable metadata
VARIABLE_ATTRS = {
    "temperature": {
        "standard_name": "sea_water_temperature",
        "units": "degree_Celsius",
        "long_name": "Sea Water Temperature",
        "valid_min": -2.0,
        "valid_max": 40.0,
    },
    "conductivity": {
        "standard_name": "sea_water_electrical_conductivity",
        "units": "S m-1",
        "long_name": "Sea Water Electrical Conductivity",
        "valid_min": 0.0,
        "valid_max": 10.0,
    },
    "salinity": {
        "standard_name": "sea_water_practical_salinity",
        "units": "1",
        "long_name": "Sea Water Practical Salinity",
        "valid_min": 0.0,
        "valid_max": 42.0,
    },
    "pressure": {
        "standard_name": "sea_water_pressure",
        "units": "dbar",
        "long_name": "Sea Water Pressure",
        "valid_min": 0.0,
        "valid_max": 2000.0,
    },
    "density": {
        "standard_name": "sea_water_density",
        "units": "kg m-3",
        "long_name": "Sea Water Density",
        "valid_min": 990.0,
        "valid_max": 1040.0,
    },
    "depth": {
        "standard_name": "depth",
        "units": "m",
        "long_name": "Depth",
        "positive": "down",
        "valid_min": 0.0,
        "valid_max": 1200.0,
    },
    "latitude": {
        "standard_name": "latitude",
        "units": "degrees_north",
        "long_name": "Latitude",
        "valid_min": -90.0,
        "valid_max": 90.0,
    },
    "longitude": {
        "standard_name": "longitude",
        "units": "degrees_east",
        "long_name": "Longitude",
        "valid_min": -180.0,
        "valid_max": 180.0,
    },
}


def merge_segments(
    segment_files: List[Path],
    output_path: Path,
    mission_id: str,
    glider_name: str = "",
    institution: str = "",
    pi_name: str = "",
) -> Tuple[Path, str]:
    """
    Merge glider segment files into a single CF trajectory NetCDF.

    Concatenates along the observation dimension, sorts by time,
    removes duplicates, and applies CF-1.8 trajectory feature type
    metadata per the IOOS Glider DAC specification.

    Args:
        segment_files: List of segment NetCDF paths to merge.
        output_path: Output path for merged file.
        mission_id: Mission identifier string.
        glider_name: Glider platform name.
        institution: Operating institution.
        pi_name: Principal investigator.

    Returns:
        (output_path, sha256_digest)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Merging %d segments for mission %s", len(segment_files), mission_id)

    datasets = []
    for seg_path in sorted(segment_files):
        try:
            ds = xr.open_dataset(seg_path)
            datasets.append(ds)
            logger.debug("Loaded segment: %s (%d obs)", seg_path.name, ds.sizes.get("obs", ds.sizes.get("time", 0)))
        except Exception as e:
            logger.warning("Skipping segment %s: %s", seg_path.name, e)

    if not datasets:
        raise ValueError(f"No valid segments found for mission {mission_id}")

    # Concatenate along observation dimension
    obs_dim = _detect_obs_dimension(datasets[0])
    merged = xr.concat(datasets, dim=obs_dim)

    # Sort by time
    if "time" in merged.coords:
        merged = merged.sortby("time")
    elif "time" in merged.data_vars:
        time_idx = np.argsort(merged["time"].values)
        merged = merged.isel({obs_dim: time_idx})

    # Remove duplicate timestamps
    if "time" in merged.coords:
        _, unique_idx = np.unique(merged["time"].values, return_index=True)
        if len(unique_idx) < merged.sizes[obs_dim]:
            n_dupes = merged.sizes[obs_dim] - len(unique_idx)
            logger.info("Removed %d duplicate timestamps", n_dupes)
            merged = merged.isel({obs_dim: unique_idx})

    # Apply CF trajectory attributes
    now_utc = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    merged.attrs.update(CF_TRAJECTORY_ATTRS)
    merged.attrs.update({
        "title": f"Glider mission {mission_id} — merged trajectory",
        "summary": (
            f"Merged trajectory data from {len(segment_files)} segment files "
            f"for glider mission {mission_id}."
        ),
        "source": "IOOS Glider DAC",
        "platform": f"Slocum Glider {glider_name}" if glider_name else "Slocum Glider",
        "platform_type": "Slocum Glider",
        "instrument": "CTD, pressure sensor",
        "institution": institution or "Unknown",
        "creator_name": pi_name or "Unknown",
        "date_created": now_utc,
        "date_modified": now_utc,
        "history": f"Merged from {len(segment_files)} segments by glider-data-curation v1.0.0",
        "license": "CC-BY-4.0",
        "references": "https://gliders.ioos.us/",
        "id": mission_id,
        "naming_authority": "io.github.ranjithguggilla",
    })

    # Add trajectory variable
    merged["trajectory"] = xr.DataArray(
        data=mission_id,
        attrs={
            "long_name": "Trajectory/mission identifier",
            "cf_role": "trajectory_id",
        },
    )

    # Apply variable metadata
    for var_name, attrs in VARIABLE_ATTRS.items():
        if var_name in merged.data_vars or var_name in merged.coords:
            target = merged[var_name]
            for k, v in attrs.items():
                target.attrs[k] = v

    # Write NetCDF
    encoding = _build_encoding(merged, obs_dim)
    merged.to_netcdf(output_path, encoding=encoding)

    # Compute checksum
    digest = _sha256_file(output_path)
    sidecar = output_path.with_suffix(".nc.sha256")
    sidecar.write_text(f"{digest}  {output_path.name}\n")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        "Merged trajectory: %s (%.1f MB, %d observations, sha256: %s...)",
        output_path, size_mb, merged.sizes[obs_dim], digest[:16],
    )

    # Close datasets
    for ds in datasets:
        ds.close()
    merged.close()

    return output_path, digest


def merge_from_single_file(
    input_path: Path,
    output_path: Path,
    mission_id: str,
    glider_name: str = "",
    institution: str = "",
    pi_name: str = "",
) -> Tuple[Path, str]:
    """
    Process a single mission NetCDF (already merged by ERDDAP).

    Applies CF trajectory metadata and standardizes variable attributes.

    Args:
        input_path: Path to single-file mission NetCDF.
        output_path: Output path for standardized file.
        mission_id: Mission identifier.

    Returns:
        (output_path, sha256_digest)
    """
    return merge_segments(
        [input_path], output_path, mission_id,
        glider_name=glider_name,
        institution=institution,
        pi_name=pi_name,
    )


def _detect_obs_dimension(ds: xr.Dataset) -> str:
    """Detect the observation dimension name."""
    for dim in ["obs", "time", "row", "profile"]:
        if dim in ds.dims:
            return dim
    # Fall back to first dimension
    return list(ds.dims.keys())[0]


def _build_encoding(ds: xr.Dataset, obs_dim: str) -> Dict:
    """Build NetCDF encoding dict for consistent output."""
    encoding = {}
    for var in ds.data_vars:
        if ds[var].dtype in (np.float32, np.float64):
            encoding[var] = {
                "dtype": "float32",
                "zlib": True,
                "complevel": 4,
                "_FillValue": np.float32(-9999.0),
            }
        elif ds[var].dtype in (np.int32, np.int64):
            encoding[var] = {
                "dtype": "int32",
                "zlib": True,
                "complevel": 4,
                "_FillValue": np.int32(-9999),
            }

    if "time" in ds.coords or "time" in ds.data_vars:
        encoding["time"] = {
            "units": "seconds since 1970-01-01T00:00:00Z",
            "calendar": "standard",
            "dtype": "float64",
        }

    return encoding


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
