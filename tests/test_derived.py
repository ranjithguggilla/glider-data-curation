"""Tests for derived variable computation."""

from __future__ import annotations

import numpy as np
import xarray as xr

from glidercure.derived import compute_derived_variables, compute_mixed_layer_depth


class TestDerivedVariables:
    def test_adds_absolute_salinity(self, sample_trajectory):
        ds = compute_derived_variables(sample_trajectory)
        assert "absolute_salinity" in ds.data_vars
        sa = ds["absolute_salinity"].values
        valid = sa[np.isfinite(sa)]
        assert len(valid) > 0
        assert np.all(valid > 0)

    def test_adds_conservative_temperature(self, sample_trajectory):
        ds = compute_derived_variables(sample_trajectory)
        assert "conservative_temperature" in ds.data_vars
        ct = ds["conservative_temperature"].values
        valid = ct[np.isfinite(ct)]
        assert len(valid) > 0

    def test_adds_sigma0(self, sample_trajectory):
        ds = compute_derived_variables(sample_trajectory)
        assert "sigma0" in ds.data_vars
        sig = ds["sigma0"].values
        valid = sig[np.isfinite(sig)]
        assert len(valid) > 0
        # Sigma0 for seawater should be roughly 20-30 kg/m^3
        assert np.mean(valid) > 15
        assert np.mean(valid) < 35

    def test_adds_sound_speed(self, sample_trajectory):
        ds = compute_derived_variables(sample_trajectory)
        assert "sound_speed" in ds.data_vars
        ss = ds["sound_speed"].values
        valid = ss[np.isfinite(ss)]
        assert len(valid) > 0
        # Sound speed in seawater: ~1450-1560 m/s
        assert np.mean(valid) > 1400
        assert np.mean(valid) < 1600

    def test_preserves_original_variables(self, sample_trajectory):
        original_vars = set(sample_trajectory.data_vars)
        ds = compute_derived_variables(sample_trajectory)
        for var in original_vars:
            assert var in ds.data_vars

    def test_derived_have_attributes(self, sample_trajectory):
        ds = compute_derived_variables(sample_trajectory)
        for var in ["absolute_salinity", "conservative_temperature", "sigma0", "sound_speed"]:
            assert "units" in ds[var].attrs
            assert "long_name" in ds[var].attrs


class TestMixedLayerDepth:
    def test_returns_float(self, sample_trajectory):
        mld = compute_mixed_layer_depth(sample_trajectory)
        assert isinstance(mld, (float, type(None)))

    def test_positive_depth(self, sample_trajectory):
        mld = compute_mixed_layer_depth(sample_trajectory)
        if mld is not None:
            assert mld > 0

    def test_missing_density_returns_none(self):
        ds = xr.Dataset(
            {"temperature": ("obs", [20.0, 19.5, 19.0])},
            coords={"time": ("obs", [0, 1, 2])},
        )
        mld = compute_mixed_layer_depth(ds)
        assert mld is None
