"""Shared test fixtures for glider-data-curation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


@pytest.fixture
def sample_trajectory() -> xr.Dataset:
    """Create a synthetic glider trajectory dataset."""
    n = 500
    rng = np.random.default_rng(42)

    # Time series: ~5 days
    base_time = np.datetime64("2024-03-15T00:00:00")
    times = base_time + np.arange(n) * np.timedelta64(15, "m")

    # Simulate a south-to-north track in the Gulf of Mexico
    lat_start, lon_start = 27.5, -90.0
    lat = lat_start + np.cumsum(rng.normal(0.001, 0.0005, n))
    lon = lon_start + np.cumsum(rng.normal(0.0005, 0.0003, n))

    # Depth: sawtooth dive pattern (0-200m)
    period = 40  # observations per dive
    phase = np.linspace(0, n / period * 2 * np.pi, n)
    depth = 100 * (1 - np.cos(phase)) + rng.normal(0, 2, n)
    depth = np.clip(depth, 0, 250)

    # Pressure (dbar ~ depth in meters for seawater)
    pressure = depth * 1.01

    # Temperature: decreasing with depth, slight warming trend
    temp = 25 - 0.05 * depth + rng.normal(0, 0.3, n) + np.linspace(0, 0.5, n)

    # Salinity: increasing with depth
    sal = 35.0 + 0.005 * depth + rng.normal(0, 0.05, n)

    # Conductivity (approximate)
    conductivity = sal * 0.001 * (1 + 0.02 * temp)

    ds = xr.Dataset(
        {
            "temperature": ("obs", temp.astype(np.float32)),
            "salinity": ("obs", sal.astype(np.float32)),
            "pressure": ("obs", pressure.astype(np.float32)),
            "depth": ("obs", depth.astype(np.float32)),
            "conductivity": ("obs", conductivity.astype(np.float32)),
        },
        coords={
            "time": ("obs", times),
            "latitude": ("obs", lat.astype(np.float64)),
            "longitude": ("obs", lon.astype(np.float64)),
        },
        attrs={
            "Conventions": "CF-1.8, ACDD-1.3",
            "featureType": "trajectory",
            "title": "Test glider trajectory",
        },
    )

    return ds


@pytest.fixture
def sample_trajectory_nc(sample_trajectory, tmp_path) -> Path:
    """Write sample trajectory to a NetCDF file."""
    nc_path = tmp_path / "test_trajectory.nc"
    sample_trajectory.to_netcdf(nc_path)
    return nc_path


@pytest.fixture
def sample_segments(sample_trajectory, tmp_path) -> list[Path]:
    """Split sample trajectory into two segment files."""
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()

    ds = sample_trajectory
    mid = len(ds.obs) // 2

    seg1 = ds.isel(obs=slice(0, mid))
    seg2 = ds.isel(obs=slice(mid, None))

    path1 = seg_dir / "segment_001.nc"
    path2 = seg_dir / "segment_002.nc"
    seg1.to_netcdf(path1)
    seg2.to_netcdf(path2)

    return [path1, path2]


@pytest.fixture
def mission_id() -> str:
    return "test-glider-2024"


@pytest.fixture
def tmp_output(tmp_path) -> Path:
    """Temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out
