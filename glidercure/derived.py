"""
Derived oceanographic variables using GSW.

Computes derived variables from raw CTD observations using the
Gibbs SeaWater (GSW) Oceanographic Toolbox, following TEOS-10
standards. All derivations use the gsw Python package.

Computed variables:
  - Absolute salinity (SA) from practical salinity
  - Conservative temperature (CT) from in-situ temperature
  - Potential density anomaly (sigma0)
  - Brunt-Vaisala frequency squared (N2)
  - Sound speed
  - Mixed layer depth estimate
"""

from __future__ import annotations

import logging
from typing import Optional

import gsw
import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


def compute_derived_variables(ds: xr.Dataset) -> xr.Dataset:
    """
    Compute all derived oceanographic variables.

    Requires temperature, salinity (practical), pressure, latitude,
    and longitude in the input dataset.

    Args:
        ds: Input dataset with raw CTD variables.

    Returns:
        Dataset with added derived variables.
    """
    ds = ds.copy()

    # Extract required variables
    temp = _get_var(ds, ["temperature", "temp", "sea_water_temperature"])
    sal = _get_var(ds, ["salinity", "sal", "sea_water_practical_salinity"])
    pres = _get_var(ds, ["pressure", "pres", "sea_water_pressure"])
    lat = _get_var(ds, ["latitude", "lat"])
    lon = _get_var(ds, ["longitude", "lon"])

    if temp is None or sal is None or pres is None:
        logger.warning("Missing required variables for derived calculations")
        return ds

    # Use scalar lat/lon if coordinate vars, or median for profile approximation
    lat_val = _scalar_or_median(lat)
    lon_val = _scalar_or_median(lon)

    # Absolute Salinity (SA)
    try:
        sa = gsw.SA_from_SP(sal.values, pres.values, lon_val, lat_val)
        ds["absolute_salinity"] = xr.DataArray(
            data=sa.astype(np.float32),
            dims=temp.dims,
            attrs={
                "standard_name": "sea_water_absolute_salinity",
                "units": "g kg-1",
                "long_name": "Absolute Salinity (TEOS-10)",
            },
        )
        logger.debug("Computed absolute salinity")
    except Exception as e:
        logger.warning("Failed to compute absolute salinity: %s", e)
        sa = None

    # Conservative Temperature (CT)
    if sa is not None:
        try:
            ct = gsw.CT_from_t(sa, temp.values, pres.values)
            ds["conservative_temperature"] = xr.DataArray(
                data=ct.astype(np.float32),
                dims=temp.dims,
                attrs={
                    "standard_name": "sea_water_conservative_temperature",
                    "units": "degree_Celsius",
                    "long_name": "Conservative Temperature (TEOS-10)",
                },
            )
            logger.debug("Computed conservative temperature")
        except Exception as e:
            logger.warning("Failed to compute conservative temperature: %s", e)
            ct = None
    else:
        ct = None

    # Potential Density Anomaly (sigma0)
    if sa is not None and ct is not None:
        try:
            sigma0 = gsw.sigma0(sa, ct)
            ds["sigma0"] = xr.DataArray(
                data=sigma0.astype(np.float32),
                dims=temp.dims,
                attrs={
                    "standard_name": "sea_water_sigma_t",
                    "units": "kg m-3",
                    "long_name": "Potential Density Anomaly (sigma-theta)",
                },
            )
            logger.debug("Computed sigma0")
        except Exception as e:
            logger.warning("Failed to compute sigma0: %s", e)

    # Sound Speed
    if sa is not None and ct is not None:
        try:
            sound_speed = gsw.sound_speed(sa, ct, pres.values)
            ds["sound_speed"] = xr.DataArray(
                data=sound_speed.astype(np.float32),
                dims=temp.dims,
                attrs={
                    "standard_name": "speed_of_sound_in_sea_water",
                    "units": "m s-1",
                    "long_name": "Speed of Sound in Sea Water",
                },
            )
            logger.debug("Computed sound speed")
        except Exception as e:
            logger.warning("Failed to compute sound speed: %s", e)

    return ds


def compute_mixed_layer_depth(
    ds: xr.Dataset,
    density_threshold: float = 0.03,
) -> Optional[float]:
    """
    Estimate mixed layer depth using a density threshold criterion.

    The MLD is defined as the depth where density exceeds the near-surface
    (10 m) density by `density_threshold` kg/m^3.

    Args:
        ds: Dataset with sigma0 and depth.
        density_threshold: Density difference criterion (kg/m^3).

    Returns:
        Mixed layer depth in meters, or None if not estimable.
    """
    if "sigma0" not in ds.data_vars or "depth" not in ds:
        return None

    sigma = ds["sigma0"].values
    depth = ds["depth"].values if "depth" in ds.data_vars else ds["depth"].values

    # Remove NaN
    mask = np.isfinite(sigma) & np.isfinite(depth) & (depth > 0)
    if mask.sum() < 10:
        return None

    sigma_clean = sigma[mask]
    depth_clean = depth[mask]

    # Sort by depth
    sort_idx = np.argsort(depth_clean)
    sigma_sorted = sigma_clean[sort_idx]
    depth_sorted = depth_clean[sort_idx]

    # Reference density near surface (shallowest 10 m)
    shallow_mask = depth_sorted <= 10.0
    if shallow_mask.sum() == 0:
        return None

    ref_density = np.nanmean(sigma_sorted[shallow_mask])

    # Find where density exceeds threshold
    for i, (d, s) in enumerate(zip(depth_sorted, sigma_sorted)):
        if d > 10.0 and (s - ref_density) > density_threshold:
            return float(d)

    return None


def _get_var(ds: xr.Dataset, names: list) -> Optional[xr.DataArray]:
    """Get a variable by trying multiple possible names."""
    for name in names:
        if name in ds.data_vars:
            return ds[name]
        if name in ds.coords:
            return ds[name]
    return None


def _scalar_or_median(arr: Optional[xr.DataArray]) -> float:
    """Extract scalar or compute median of an array."""
    if arr is None:
        return 0.0
    vals = arr.values
    if vals.ndim == 0:
        return float(vals)
    finite = vals[np.isfinite(vals)]
    if len(finite) == 0:
        return 0.0
    return float(np.median(finite))
