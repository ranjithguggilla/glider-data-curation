"""Tests for mission metrics computation."""

from __future__ import annotations

import numpy as np
import pytest

from glidercure.metrics import (
    _compute_depth_bins,
    _compute_track_distance,
    _estimate_dive_count,
    compute_metrics,
)


class TestComputeMetrics:
    def test_basic_metrics(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.mission_id == mission_id
        assert m.n_observations == 500
        assert m.distance_km > 0
        assert m.duration_days > 0

    def test_spatial_bounds(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.lat_min < m.lat_max
        assert m.lon_min < m.lon_max
        assert 25 < m.lat_min < 30
        assert -92 < m.lon_min < -88

    def test_depth_metrics(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.max_depth_m > 0
        assert m.mean_depth_m > 0
        assert m.max_depth_m >= m.mean_depth_m

    def test_temporal_metrics(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.start_time != ""
        assert m.end_time != ""
        assert m.duration_days > 0

    def test_sensor_uptime(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert len(m.sensor_uptime) > 0
        for var, pct in m.sensor_uptime.items():
            assert 0 <= pct <= 100

    def test_depth_bins_populated(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert len(m.depth_bins) > 0
        total = sum(m.depth_bins.values())
        assert total > 0

    def test_temperature_range(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.temp_min < m.temp_max
        assert 10 < m.temp_min < 30
        assert 10 < m.temp_max < 35

    def test_salinity_range(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        assert m.sal_min < m.sal_max
        assert 30 < m.sal_min < 40


class TestMissionMetricsDict:
    def test_to_dict_keys(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        d = m.to_dict()
        assert "mission_id" in d
        assert "spatial" in d
        assert "temporal" in d
        assert "depth" in d
        assert "observations" in d
        assert "sensor_uptime_pct" in d

    def test_to_dict_values(self, sample_trajectory, mission_id):
        m = compute_metrics(sample_trajectory, mission_id)
        d = m.to_dict()
        assert d["observations"] == 500
        assert d["spatial"]["distance_km"] > 0


class TestTrackDistance:
    def test_known_distance(self):
        # ~111 km for 1 degree of latitude at equator
        lat = np.array([0.0, 1.0])
        lon = np.array([0.0, 0.0])
        dist = _compute_track_distance(lat, lon)
        assert 110 < dist < 112

    def test_zero_distance(self):
        lat = np.array([27.5, 27.5])
        lon = np.array([-90.0, -90.0])
        dist = _compute_track_distance(lat, lon)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_handles_nans(self):
        lat = np.array([27.5, np.nan, 27.6])
        lon = np.array([-90.0, np.nan, -90.0])
        dist = _compute_track_distance(lat, lon)
        assert dist > 0


class TestDepthBins:
    def test_bins_sum(self):
        depths = np.array([10, 25, 75, 150, 300, 800, 1200])
        bins = _compute_depth_bins(depths)
        assert sum(bins.values()) == 7

    def test_shallow_depths(self):
        depths = np.array([5, 10, 20, 30, 40])
        bins = _compute_depth_bins(depths)
        assert bins["0-50m"] == 5

    def test_deep_depths(self):
        depths = np.array([1100, 1200, 1500])
        bins = _compute_depth_bins(depths)
        assert bins[">1000m"] == 3


class TestDiveCount:
    def test_sawtooth_dives(self):
        n = 1000
        t = np.linspace(0, 10 * np.pi, n)
        depth = 100 * np.abs(np.sin(t))
        dives = _estimate_dive_count(depth)
        # Should detect multiple dives (exact count depends on threshold)
        assert 3 <= dives <= 15

    def test_short_data(self):
        depth = np.array([1, 2, 3])
        dives = _estimate_dive_count(depth)
        assert dives == 0

    def test_flat_depth(self):
        depth = np.full(100, 50.0)
        dives = _estimate_dive_count(depth)
        assert dives == 0
