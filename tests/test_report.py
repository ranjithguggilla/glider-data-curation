"""Tests for mission report generation."""

from __future__ import annotations

import pytest

from glidercure.metrics import MissionMetrics
from glidercure.qc import QCReport
from glidercure.report import generate_mission_report


@pytest.fixture
def sample_qc_report():
    return QCReport(
        variables_checked=5,
        spike_count=3,
        flags_summary={
            "temperature": {"good": 480, "suspect": 15, "bad": 2, "missing": 3},
            "salinity": {"good": 490, "suspect": 5, "bad": 0, "missing": 5},
        },
        gaps=[],
    )


@pytest.fixture
def report_metrics():
    return MissionMetrics(
        mission_id="test-glider-2024",
        distance_km=145.3,
        lat_min=27.5,
        lat_max=28.2,
        lon_min=-90.1,
        lon_max=-89.5,
        start_time="2024-03-15T00:00",
        end_time="2024-03-20T12:00",
        duration_days=5.5,
        max_depth_m=200.0,
        mean_depth_m=85.0,
        n_observations=500,
        n_dives=25,
        n_profiles=50,
        temp_min=18.5,
        temp_max=26.3,
        sal_min=34.8,
        sal_max=36.2,
        depth_bins={"0-50m": 200, "50-100m": 150, "100-200m": 100,
                    "200-500m": 50, "500-1000m": 0, ">1000m": 0},
        sensor_uptime={"temperature": 99.2, "salinity": 98.5,
                       "pressure": 100.0, "depth": 100.0},
    )


class TestGenerateReport:
    def test_creates_html(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        result = generate_mission_report(
            report_metrics, sample_qc_report, out, "test-glider-2024"
        )
        assert result.exists()
        content = result.read_text()
        assert "<!DOCTYPE html>" in content

    def test_contains_mission_id(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        generate_mission_report(report_metrics, sample_qc_report, out, "test-glider-2024")
        content = out.read_text()
        assert "test-glider-2024" in content

    def test_contains_metrics(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        generate_mission_report(report_metrics, sample_qc_report, out, "test-glider-2024")
        content = out.read_text()
        assert "145.3" in content  # distance
        assert "5.5" in content  # duration

    def test_contains_qc_summary(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        generate_mission_report(report_metrics, sample_qc_report, out, "test-glider-2024")
        content = out.read_text()
        assert "Quality Control" in content

    def test_writes_json_sidecar(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        generate_mission_report(report_metrics, sample_qc_report, out, "test-glider-2024")
        json_path = out.with_suffix(".json")
        assert json_path.exists()

    def test_creates_parent_dirs(self, report_metrics, sample_qc_report, tmp_path):
        out = tmp_path / "deep" / "nested" / "report.html"
        result = generate_mission_report(
            report_metrics, sample_qc_report, out, "test-glider-2024"
        )
        assert result.exists()

    def test_with_map_path(self, report_metrics, sample_qc_report, tmp_output):
        out = tmp_output / "report.html"
        map_path = tmp_output / "mission_map.html"
        map_path.write_text("<html>map</html>")
        generate_mission_report(
            report_metrics, sample_qc_report, out, "test-glider-2024",
            map_path=map_path,
        )
        content = out.read_text()
        assert "mission_map.html" in content
