"""Tests for mission archive packaging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glidercure.metrics import MissionMetrics
from glidercure.package import (
    build_manifest,
    package_mission,
    sha256_file,
    verify_package,
)


@pytest.fixture
def mock_nc(tmp_path) -> Path:
    """Create a mock NetCDF file."""
    nc = tmp_path / "test_trajectory.nc"
    nc.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
    return nc


@pytest.fixture
def pkg_metrics():
    return MissionMetrics(
        mission_id="test-001",
        distance_km=100.5,
        lat_min=27.5,
        lat_max=28.0,
        lon_min=-90.0,
        lon_max=-89.5,
        start_time="2024-03-15T00:00",
        end_time="2024-03-18T12:00",
        duration_days=3.5,
        max_depth_m=150.0,
        n_observations=10000,
    )


class TestSha256:
    def test_hash_known_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = sha256_file(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex length

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same content")
        f2.write_text("same content")
        assert sha256_file(f1) == sha256_file(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A")
        f2.write_text("content B")
        assert sha256_file(f1) != sha256_file(f2)


class TestBuildManifest:
    def test_manifest_entries(self, tmp_path):
        (tmp_path / "file1.txt").write_text("one")
        (tmp_path / "file2.txt").write_text("two")
        manifest = build_manifest(tmp_path)
        assert "file1.txt" in manifest
        assert "file2.txt" in manifest

    def test_excludes_manifest_file(self, tmp_path):
        (tmp_path / "data.txt").write_text("data")
        (tmp_path / "MANIFEST.json").write_text("{}")
        manifest = build_manifest(tmp_path)
        assert "MANIFEST.json" not in manifest


class TestPackageMission:
    def test_creates_package_dir(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert pkg_dir.exists()
        assert pkg_dir.is_dir()

    def test_contains_netcdf(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        nc_files = list(pkg_dir.glob("*.nc"))
        assert len(nc_files) == 1

    def test_contains_datacite(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert (pkg_dir / "datacite.xml").exists()

    def test_contains_manifest(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert (pkg_dir / "MANIFEST.json").exists()
        manifest = json.loads((pkg_dir / "MANIFEST.json").read_text())
        assert len(manifest) > 0

    def test_contains_metrics_json(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert (pkg_dir / "metrics.json").exists()

    def test_contains_package_json(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert (pkg_dir / "package.json").exists()
        desc = json.loads((pkg_dir / "package.json").read_text())
        assert desc["mission_id"] == "test-001"
        assert desc["version"] == "1.0.0"

    def test_contains_readme(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        assert (pkg_dir / "README.txt").exists()


class TestVerifyPackage:
    def test_valid_package(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        errors = verify_package(pkg_dir)
        assert len(errors) == 0

    def test_missing_file(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        # Remove a file
        nc_files = list(pkg_dir.glob("*.nc"))
        nc_files[0].unlink()
        errors = verify_package(pkg_dir)
        assert len(errors) > 0
        assert any("Missing" in e for e in errors)

    def test_corrupted_file(self, mock_nc, pkg_metrics, tmp_output):
        pkg_dir = package_mission("test-001", mock_nc, pkg_metrics, tmp_output)
        # Corrupt a file
        nc_files = list(pkg_dir.glob("*.nc"))
        nc_files[0].write_text("corrupted data")
        errors = verify_package(pkg_dir)
        assert len(errors) > 0
        assert any("Hash mismatch" in e for e in errors)

    def test_missing_manifest(self, tmp_path):
        errors = verify_package(tmp_path)
        assert len(errors) == 1
        assert "MANIFEST.json" in errors[0]
