"""Tests for segment merging."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from glidercure.merge import merge_from_single_file, merge_segments


class TestMergeSegments:
    def test_merge_two_segments(self, sample_segments, tmp_output, mission_id):
        out = tmp_output / "merged.nc"
        result_path, digest = merge_segments(sample_segments, out, mission_id)
        assert result_path.exists()
        assert len(digest) == 64

        ds = xr.open_dataset(result_path)
        assert ds.attrs.get("featureType") == "trajectory"
        assert ds.attrs.get("Conventions") == "CF-1.8, ACDD-1.3"
        ds.close()

    def test_merged_observation_count(self, sample_segments, tmp_output, mission_id):
        out = tmp_output / "merged.nc"
        merge_segments(sample_segments, out, mission_id)

        ds = xr.open_dataset(out)
        n_obs = ds.sizes.get("obs", 0)
        # Should have all 500 observations (250 + 250)
        assert n_obs == 500
        ds.close()

    def test_merged_sorted_by_time(self, sample_segments, tmp_output, mission_id):
        out = tmp_output / "merged.nc"
        merge_segments(sample_segments, out, mission_id)

        ds = xr.open_dataset(out)
        times = ds["time"].values
        assert np.all(times[:-1] <= times[1:])
        ds.close()

    def test_trajectory_variable(self, sample_segments, tmp_output, mission_id):
        out = tmp_output / "merged.nc"
        merge_segments(sample_segments, out, mission_id)

        ds = xr.open_dataset(out)
        assert "trajectory" in ds.data_vars
        assert ds["trajectory"].attrs.get("cf_role") == "trajectory_id"
        ds.close()

    def test_merge_creates_parent_dirs(self, sample_segments, tmp_path, mission_id):
        out = tmp_path / "deep" / "nested" / "merged.nc"
        result_path, _ = merge_segments(sample_segments, out, mission_id)
        assert result_path.exists()


class TestMergeFromSingleFile:
    def test_single_file_merge(self, sample_trajectory_nc, tmp_output, mission_id):
        out = tmp_output / "merged.nc"
        result_path, _ = merge_from_single_file(sample_trajectory_nc, out, mission_id)
        assert result_path.exists()

        ds = xr.open_dataset(result_path)
        assert "trajectory" in ds.data_vars
        assert ds.attrs.get("featureType") == "trajectory"
        ds.close()

    def test_single_file_preserves_data(
        self, sample_trajectory_nc, tmp_output, mission_id
    ):
        out = tmp_output / "merged.nc"
        merge_from_single_file(sample_trajectory_nc, out, mission_id)

        original = xr.open_dataset(sample_trajectory_nc)
        merged = xr.open_dataset(out)

        # Observation count should match
        assert merged.sizes.get("obs", 0) == original.sizes.get("obs", 0)
        original.close()
        merged.close()


class TestMergeEdgeCases:
    def test_empty_file_list(self, tmp_output, mission_id):
        out = tmp_output / "empty.nc"
        with pytest.raises(ValueError, match="No valid segments"):
            merge_segments([], out, mission_id)

    def test_single_segment_in_list(
        self, sample_trajectory_nc, tmp_output, mission_id
    ):
        out = tmp_output / "single.nc"
        result_path, _ = merge_segments([sample_trajectory_nc], out, mission_id)
        assert result_path.exists()
