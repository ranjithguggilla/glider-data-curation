"""Tests for QARTOD QC flag application."""

from __future__ import annotations

import numpy as np
import xarray as xr

from glidercure.qc import QCReport, apply_qc


class TestApplyQC:
    def test_adds_qc_variables(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        # Should have QC flag variables
        qc_vars = [v for v in ds.data_vars if v.endswith("_qc")]
        assert len(qc_vars) > 0

    def test_qc_flag_values(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        for var in ds.data_vars:
            if var.endswith("_qc"):
                flags = ds[var].values
                # All flags should be valid QARTOD values
                valid_flags = {1, 2, 3, 4, 9}
                unique = set(np.unique(flags))
                assert unique.issubset(valid_flags)

    def test_mostly_good_flags(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        for var in ds.data_vars:
            if var.endswith("_qc"):
                flags = ds[var].values
                good_pct = (flags == 1).sum() / len(flags) * 100
                # Synthetic data should be mostly good
                assert good_pct > 50

    def test_qc_flag_attributes(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        for var in ds.data_vars:
            if var.endswith("_qc"):
                assert "flag_values" in ds[var].attrs
                assert "flag_meanings" in ds[var].attrs

    def test_returns_qc_report(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        assert isinstance(report, QCReport)
        assert report.variables_checked > 0

    def test_overall_good_percentage(self, sample_trajectory):
        ds, report = apply_qc(sample_trajectory)
        assert 0 <= report.overall_good_pct <= 100

    def test_spike_detection(self, sample_trajectory):
        # Inject obvious spikes
        ds = sample_trajectory.copy(deep=True)
        temp = ds["temperature"].values.copy()
        temp[100] = 99.0  # extreme spike
        temp[200] = -50.0  # extreme spike
        ds["temperature"] = ("obs", temp)

        ds_qc, report = apply_qc(ds)
        temp_qc = ds_qc["temperature_qc"].values

        # At least some flags should be suspect or bad
        assert (temp_qc == 3).sum() + (temp_qc == 4).sum() > 0


class TestQCReport:
    def test_report_flags_summary(self, sample_trajectory):
        _, report = apply_qc(sample_trajectory)
        assert len(report.flags_summary) > 0
        for var, flags in report.flags_summary.items():
            assert "good" in flags or "suspect" in flags or "bad" in flags

    def test_report_spike_count(self, sample_trajectory):
        _, report = apply_qc(sample_trajectory)
        assert isinstance(report.spike_count, int)
        assert report.spike_count >= 0


class TestQCWithNaNs:
    def test_handles_nan_values(self):
        n = 100
        temp = np.full(n, 20.0, dtype=np.float32)
        temp[10:20] = np.nan

        ds = xr.Dataset(
            {
                "temperature": ("obs", temp),
                "salinity": ("obs", np.full(n, 35.0, dtype=np.float32)),
                "pressure": ("obs", np.linspace(0, 100, n).astype(np.float32)),
                "depth": ("obs", np.linspace(0, 100, n).astype(np.float32)),
            },
            coords={
                "time": ("obs", np.arange(n)),
                "latitude": ("obs", np.full(n, 27.5)),
                "longitude": ("obs", np.full(n, -90.0)),
            },
        )

        ds_qc, report = apply_qc(ds)
        temp_qc = ds_qc["temperature_qc"].values

        # NaN values should be flagged as missing (9)
        assert (temp_qc[10:20] == 9).all()
