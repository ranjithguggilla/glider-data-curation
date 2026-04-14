"""
Mission-level metrics computation.

Computes summary statistics for a glider mission including:
distance traveled, dive depth distribution, sensor uptime,
temperature/salinity ranges, and profile count.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


@dataclass
class MissionMetrics:
    """Computed metrics for a glider mission."""

    mission_id: str = ""

    # Spatial
    distance_km: float = 0.0
    lat_min: float = 0.0
    lat_max: float = 0.0
    lon_min: float = 0.0
    lon_max: float = 0.0

    # Temporal
    start_time: str = ""
    end_time: str = ""
    duration_days: float = 0.0

    # Depth
    max_depth_m: float = 0.0
    mean_depth_m: float = 0.0
    depth_bins: Dict[str, int] = field(default_factory=dict)
    n_dives: int = 0

    # Observations
    n_observations: int = 0
    n_profiles: int = 0

    # Sensor uptime (% of non-NaN values)
    sensor_uptime: Dict[str, float] = field(default_factory=dict)

    # Variable ranges
    temp_min: float = 0.0
    temp_max: float = 0.0
    sal_min: float = 0.0
    sal_max: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "spatial": {
                "distance_km": round(self.distance_km, 2),
                "lat_range": [round(self.lat_min, 4), round(self.lat_max, 4)],
                "lon_range": [round(self.lon_min, 4), round(self.lon_max, 4)],
            },
            "temporal": {
                "start": self.start_time,
                "end": self.end_time,
                "duration_days": round(self.duration_days, 1),
            },
            "depth": {
                "max_m": round(self.max_depth_m, 1),
                "mean_m": round(self.mean_depth_m, 1),
                "bins": self.depth_bins,
                "n_dives": self.n_dives,
            },
            "observations": self.n_observations,
            "n_profiles": self.n_profiles,
            "sensor_uptime_pct": {
                k: round(v, 1) for k, v in self.sensor_uptime.items()
            },
            "temperature_range": [round(self.temp_min, 2), round(self.temp_max, 2)],
            "salinity_range": [round(self.sal_min, 2), round(self.sal_max, 2)],
        }


def compute_metrics(ds: xr.Dataset, mission_id: str = "") -> MissionMetrics:
    """
    Compute mission-level metrics from a trajectory dataset.

    Args:
        ds: Merged trajectory dataset.
        mission_id: Mission identifier.

    Returns:
        MissionMetrics with computed values.
    """
    m = MissionMetrics(mission_id=mission_id)

    obs_dim = _detect_obs_dim(ds)
    m.n_observations = ds.sizes.get(obs_dim, 0)

    # Spatial metrics
    lat = _get_var(ds, ["latitude", "lat"])
    lon = _get_var(ds, ["longitude", "lon"])

    if lat is not None:
        lat_vals = lat.values[np.isfinite(lat.values)]
        if len(lat_vals) > 0:
            m.lat_min = float(np.nanmin(lat_vals))
            m.lat_max = float(np.nanmax(lat_vals))

    if lon is not None:
        lon_vals = lon.values[np.isfinite(lon.values)]
        if len(lon_vals) > 0:
            m.lon_min = float(np.nanmin(lon_vals))
            m.lon_max = float(np.nanmax(lon_vals))

    if lat is not None and lon is not None:
        m.distance_km = _compute_track_distance(lat.values, lon.values)

    # Temporal metrics
    if "time" in ds.coords or "time" in ds.data_vars:
        times = ds["time"].values
        valid_times = times[~np.isnat(times)] if hasattr(times[0], 'astype') else times
        if len(valid_times) > 0:
            m.start_time = str(valid_times[0])[:19]
            m.end_time = str(valid_times[-1])[:19]
            try:
                dt = (valid_times[-1] - valid_times[0])
                m.duration_days = float(dt / np.timedelta64(1, "D"))
            except (TypeError, ValueError):
                pass

    # Depth metrics
    depth = _get_var(ds, ["depth", "pressure"])
    if depth is not None:
        depth_vals = depth.values[np.isfinite(depth.values)]
        if len(depth_vals) > 0:
            m.max_depth_m = float(np.nanmax(depth_vals))
            m.mean_depth_m = float(np.nanmean(depth_vals))
            m.depth_bins = _compute_depth_bins(depth_vals)
            m.n_dives = _estimate_dive_count(depth_vals)

    # Sensor uptime
    for var_name in ["temperature", "salinity", "conductivity", "pressure",
                     "density", "depth"]:
        if var_name in ds.data_vars:
            values = ds[var_name].values
            total = len(values)
            valid = np.isfinite(values).sum()
            m.sensor_uptime[var_name] = (valid / total * 100) if total > 0 else 0.0

    # Variable ranges
    temp = _get_var(ds, ["temperature", "temp"])
    if temp is not None:
        tv = temp.values[np.isfinite(temp.values)]
        if len(tv) > 0:
            m.temp_min = float(np.nanmin(tv))
            m.temp_max = float(np.nanmax(tv))

    sal = _get_var(ds, ["salinity", "sal"])
    if sal is not None:
        sv = sal.values[np.isfinite(sal.values)]
        if len(sv) > 0:
            m.sal_min = float(np.nanmin(sv))
            m.sal_max = float(np.nanmax(sv))

    # Profile count (approximate)
    if depth is not None:
        m.n_profiles = m.n_dives * 2  # each dive has a down + up profile

    logger.info(
        "Mission %s: %.1f km, %.1f days, %d obs, max depth %.0f m",
        mission_id, m.distance_km, m.duration_days,
        m.n_observations, m.max_depth_m,
    )

    return m


def _compute_track_distance(lat: np.ndarray, lon: np.ndarray) -> float:
    """Compute total distance traveled using haversine formula."""
    R = 6371.0  # Earth radius in km

    mask = np.isfinite(lat) & np.isfinite(lon)
    lat_clean = np.radians(lat[mask])
    lon_clean = np.radians(lon[mask])

    if len(lat_clean) < 2:
        return 0.0

    dlat = np.diff(lat_clean)
    dlon = np.diff(lon_clean)

    a = np.sin(dlat / 2) ** 2 + np.cos(lat_clean[:-1]) * np.cos(lat_clean[1:]) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    distances = R * c

    return float(np.nansum(distances))


def _compute_depth_bins(depth_vals: np.ndarray) -> Dict[str, int]:
    """Bin depth observations into depth ranges."""
    bins = {
        "0-50m": 0,
        "50-100m": 0,
        "100-200m": 0,
        "200-500m": 0,
        "500-1000m": 0,
        ">1000m": 0,
    }
    for d in depth_vals:
        if d <= 50:
            bins["0-50m"] += 1
        elif d <= 100:
            bins["50-100m"] += 1
        elif d <= 200:
            bins["100-200m"] += 1
        elif d <= 500:
            bins["200-500m"] += 1
        elif d <= 1000:
            bins["500-1000m"] += 1
        else:
            bins[">1000m"] += 1
    return bins


def _estimate_dive_count(depth_vals: np.ndarray) -> int:
    """Estimate number of dives by counting depth zero-crossings."""
    if len(depth_vals) < 10:
        return 0

    # Use median depth as threshold
    threshold = max(5.0, np.nanmedian(depth_vals) * 0.3)

    # Count transitions from shallow to deep
    above = depth_vals < threshold
    transitions = np.diff(above.astype(int))
    dives = int(np.sum(transitions == -1))  # shallow → deep

    return max(dives, 0)


def _get_var(ds: xr.Dataset, names: list):
    for name in names:
        if name in ds.data_vars:
            return ds[name]
        if name in ds.coords:
            return ds[name]
    return None


def _detect_obs_dim(ds: xr.Dataset) -> str:
    for dim in ["obs", "time", "row", "profile"]:
        if dim in ds.dims:
            return dim
    return list(ds.dims.keys())[0]
