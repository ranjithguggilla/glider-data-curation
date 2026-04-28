"""Tests for interactive mission map generation."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from glidercure.mission_map import _depth_color, generate_mission_map


class TestGenerateMissionMap:
    def test_creates_html(self, sample_trajectory, tmp_output, mission_id):
        out = tmp_output / "map.html"
        result = generate_mission_map(sample_trajectory, out, mission_id)
        assert result.exists()
        content = result.read_text()
        assert "html" in content.lower()

    def test_contains_folium(self, sample_trajectory, tmp_output, mission_id):
        out = tmp_output / "map.html"
        generate_mission_map(sample_trajectory, out, mission_id)
        content = out.read_text()
        # Folium maps include leaflet
        assert "leaflet" in content.lower()

    def test_contains_mission_id(self, sample_trajectory, tmp_output, mission_id):
        out = tmp_output / "map.html"
        generate_mission_map(sample_trajectory, out, mission_id)
        content = out.read_text()
        assert mission_id in content

    def test_creates_parent_dirs(self, sample_trajectory, tmp_path, mission_id):
        out = tmp_path / "deep" / "nested" / "map.html"
        result = generate_mission_map(sample_trajectory, out, mission_id)
        assert result.exists()


class TestMapEdgeCases:
    def test_missing_lat_lon(self, tmp_output):
        ds = xr.Dataset(
            {"temperature": ("obs", [20.0, 21.0, 22.0])},
        )
        with pytest.raises(ValueError, match="Missing latitude"):
            generate_mission_map(ds, tmp_output / "map.html")

    def test_no_valid_coordinates(self, tmp_output):
        ds = xr.Dataset(
            {"temperature": ("obs", [20.0, 21.0])},
            coords={
                "latitude": ("obs", [np.nan, np.nan]),
                "longitude": ("obs", [np.nan, np.nan]),
            },
        )
        with pytest.raises(ValueError, match="No valid coordinates"):
            generate_mission_map(ds, tmp_output / "map.html")

    def test_small_dataset(self, tmp_output, mission_id):
        ds = xr.Dataset(
            {"temperature": ("obs", [20.0, 21.0, 22.0])},
            coords={
                "latitude": ("obs", [27.5, 27.6, 27.7]),
                "longitude": ("obs", [-90.0, -89.9, -89.8]),
            },
        )
        result = generate_mission_map(ds, tmp_output / "map.html", mission_id)
        assert result.exists()


class TestDepthColor:
    def test_shallow(self):
        assert _depth_color(10) == "#64B5F6"

    def test_medium(self):
        assert _depth_color(75) == "#2196F3"  # 50-100m range

    def test_deep(self):
        assert _depth_color(600) == "#0D47A1"

    def test_boundary_values(self):
        # Just verify they return valid hex colors
        for d in [0, 20, 50, 100, 200, 500, 1000]:
            color = _depth_color(d)
            assert color.startswith("#")
            assert len(color) == 7
