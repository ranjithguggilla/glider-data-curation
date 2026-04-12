"""
Quality control for glider trajectory data.

Applies range checks, spike detection, and gap flagging to
merged trajectory datasets. QC flags follow the IOOS QARTOD
(Quality Assurance / Quality Control of Real-Time Oceanographic Data)
convention:
    1 = good
    2 = not evaluated
    3 = suspect
    4 = bad
    9 = missing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# QARTOD flag values
QC_GOOD = 1
QC_NOT_EVALUATED = 2
QC_SUSPECT = 3
QC_BAD = 4
QC_MISSING = 9

QC_FLAG_MEANINGS = "good not_evaluated suspect bad missing"
QC_FLAG_VALUES = [1, 2, 3, 4, 9]

# Physical range limits for glider variables
RANGE_LIMITS = {
    "temperature": (-2.0, 40.0),
    "salinity": (0.0, 42.0),
    "conductivity": (0.0, 10.0),
    "pressure": (0.0, 2000.0),
    "depth": (0.0, 1200.0),
    "density": (990.0, 1040.0),
    "absolute_salinity": (0.0, 45.0),
    "conservative_temperature": (-2.0, 40.0),
    "sigma0": (-5.0, 40.0),
    "sound_speed": (1400.0, 1600.0),
}


@dataclass
class QCReport:
    """Quality control summary for a mission."""

    mission_id: str = ""
    total_obs: int = 0
    variables_checked: int = 0
    flags_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    gaps: List[Dict] = field(default_factory=list)
    spike_count: int = 0

    @property
    def overall_good_pct(self) -> float:
        """Percentage of good flags across all variables."""
        total_good = 0
        total_flags = 0
        for var_flags in self.flags_summary.values():
            total_good += var_flags.get("good", 0)
            total_flags += sum(var_flags.values())
        if total_flags == 0:
            return 0.0
        return (total_good / total_flags) * 100.0


def apply_qc(
    ds: xr.Dataset,
    mission_id: str = "",
    spike_threshold: float = 3.0,
    gap_threshold_hours: float = 6.0,
) -> Tuple[xr.Dataset, QCReport]:
    """
    Apply quality control checks to a merged trajectory dataset.

    Performs:
    1. Range checks against physical limits
    2. Spike detection using rolling median
    3. Gap identification in time series
    4. NaN flagging

    Args:
        ds: Merged trajectory dataset.
        mission_id: Mission identifier for reporting.
        spike_threshold: Standard deviations for spike detection.
        gap_threshold_hours: Hours between observations to flag as gap.

    Returns:
        (qc_flagged_dataset, qc_report)
    """
    ds = ds.copy()
    report = QCReport(mission_id=mission_id)

    obs_dim = _detect_obs_dim(ds)
    report.total_obs = ds.sizes.get(obs_dim, 0)

    # Range checks + NaN flagging
    for var_name, (vmin, vmax) in RANGE_LIMITS.items():
        if var_name not in ds.data_vars:
            continue

        values = ds[var_name].values
        flags = np.full_like(values, QC_GOOD, dtype=np.int8)

        # Missing
        nan_mask = ~np.isfinite(values)
        flags[nan_mask] = QC_MISSING

        # Out of range
        oor_mask = np.isfinite(values) & ((values < vmin) | (values > vmax))
        flags[oor_mask] = QC_BAD

        # Spike detection
        spike_mask = _detect_spikes(values, threshold=spike_threshold)
        flags[spike_mask & (flags == QC_GOOD)] = QC_SUSPECT
        report.spike_count += int(spike_mask.sum())

        # Add QC variable
        qc_var_name = f"{var_name}_qc"
        ds[qc_var_name] = xr.DataArray(
            data=flags,
            dims=ds[var_name].dims,
            attrs={
                "long_name": f"Quality flag for {var_name}",
                "standard_name": "status_flag",
                "flag_values": np.array(QC_FLAG_VALUES, dtype=np.int8),
                "flag_meanings": QC_FLAG_MEANINGS,
                "references": "https://ioos.noaa.gov/project/qartod/",
            },
        )

        report.flags_summary[var_name] = {
            "good": int((flags == QC_GOOD).sum()),
            "suspect": int((flags == QC_SUSPECT).sum()),
            "bad": int((flags == QC_BAD).sum()),
            "missing": int((flags == QC_MISSING).sum()),
        }
        report.variables_checked += 1

    # Gap detection
    report.gaps = _detect_gaps(ds, gap_threshold_hours)

    logger.info(
        "QC complete: %d obs, %d vars checked, %.1f%% good, %d gaps, %d spikes",
        report.total_obs, report.variables_checked, report.overall_good_pct,
        len(report.gaps), report.spike_count,
    )

    return ds, report


def _detect_spikes(values: np.ndarray, threshold: float = 3.0, window: int = 5) -> np.ndarray:
    """Detect spikes using deviation from rolling median."""
    mask = np.zeros(len(values), dtype=bool)
    finite_mask = np.isfinite(values)

    if finite_mask.sum() < window * 2:
        return mask

    # Simple rolling median approach
    for i in range(window, len(values) - window):
        if not finite_mask[i]:
            continue
        local = values[max(0, i - window):i + window + 1]
        local_finite = local[np.isfinite(local)]
        if len(local_finite) < 3:
            continue
        median = np.median(local_finite)
        mad = np.median(np.abs(local_finite - median))
        if mad == 0:
            continue
        if abs(values[i] - median) / (mad * 1.4826) > threshold:
            mask[i] = True

    return mask


def _detect_gaps(ds: xr.Dataset, threshold_hours: float) -> List[Dict]:
    """Detect temporal gaps exceeding the threshold."""
    gaps = []

    if "time" not in ds.coords and "time" not in ds.data_vars:
        return gaps

    times = ds["time"].values
    if len(times) < 2:
        return gaps

    # Convert to datetime64 for diff
    try:
        diffs = np.diff(times.astype("datetime64[s]").astype(np.float64))
    except (TypeError, ValueError):
        return gaps

    threshold_sec = threshold_hours * 3600

    for i, dt in enumerate(diffs):
        if dt > threshold_sec:
            gaps.append({
                "start_index": i,
                "end_index": i + 1,
                "duration_hours": float(dt / 3600),
                "start_time": str(times[i]),
                "end_time": str(times[i + 1]),
            })

    return gaps


def _detect_obs_dim(ds: xr.Dataset) -> str:
    """Detect observation dimension."""
    for dim in ["obs", "time", "row", "profile"]:
        if dim in ds.dims:
            return dim
    return list(ds.dims.keys())[0]
