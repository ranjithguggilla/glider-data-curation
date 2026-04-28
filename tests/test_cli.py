"""Tests for CLI commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from glidercure.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIMain:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "glider mission" in result.output.lower()

    def test_commands_listed(self, runner):
        result = runner.invoke(main, ["--help"])
        assert "ingest" in result.output
        assert "merge" in result.output
        assert "metrics" in result.output
        assert "map" in result.output
        assert "package" in result.output
        assert "verify" in result.output
        assert "release" in result.output


class TestIngestCommand:
    def test_requires_dataset_id(self, runner):
        result = runner.invoke(main, ["ingest", "test-mission"])
        assert result.exit_code != 0
        assert "dataset-id" in result.output.lower()


class TestMergeCommand:
    def test_missing_input_dir(self, runner):
        result = runner.invoke(main, ["merge", "nonexistent-mission"])
        assert result.exit_code != 0

    def test_merge_with_segments(self, runner, sample_segments, tmp_output, mission_id):
        seg_dir = sample_segments[0].parent
        out = tmp_output / "merged.nc"
        result = runner.invoke(main, [
            "merge", mission_id,
            "-i", str(seg_dir),
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestMetricsCommand:
    def test_missing_trajectory(self, runner):
        result = runner.invoke(main, ["metrics", "nonexistent-mission"])
        assert result.exit_code != 0

    def test_compute_metrics(self, runner, sample_trajectory_nc, tmp_output, mission_id):
        json_out = tmp_output / "metrics.json"
        result = runner.invoke(main, [
            "metrics", mission_id,
            "-i", str(sample_trajectory_nc),
            "--json", str(json_out),
        ])
        assert result.exit_code == 0
        assert "Distance" in result.output
        assert json_out.exists()


class TestMapCommand:
    def test_missing_trajectory(self, runner):
        result = runner.invoke(main, ["map", "nonexistent-mission"])
        assert result.exit_code != 0

    def test_generate_map(self, runner, sample_trajectory_nc, tmp_output, mission_id):
        out = tmp_output / "map.html"
        result = runner.invoke(main, [
            "map", mission_id,
            "-i", str(sample_trajectory_nc),
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestVerifyCommand:
    def test_missing_package(self, runner):
        result = runner.invoke(main, ["verify", "nonexistent-mission"])
        assert result.exit_code != 0
