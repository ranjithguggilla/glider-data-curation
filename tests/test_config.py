"""Tests for mission configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from glidercure.config import (
    EXAMPLE_MISSIONS,
    GLIDER_DAC_ERDDAP,
    MissionConfig,
    load_mission_config,
)


class TestMissionConfig:
    def test_default_values(self):
        cfg = MissionConfig(mission_id="test-001")
        assert cfg.mission_id == "test-001"
        assert cfg.glider_name == ""
        assert cfg.data_root == Path("data")

    def test_custom_values(self):
        cfg = MissionConfig(
            mission_id="usf-bass-2024",
            glider_name="bass",
            institution="USF",
            pi_name="Dr. Smith",
            region="Gulf of Mexico",
        )
        assert cfg.institution == "USF"
        assert cfg.pi_name == "Dr. Smith"


class TestExampleMissions:
    def test_examples_exist(self):
        assert len(EXAMPLE_MISSIONS) > 0

    def test_example_keys(self):
        for key, cfg in EXAMPLE_MISSIONS.items():
            assert isinstance(key, str)
            assert isinstance(cfg, MissionConfig)
            assert cfg.mission_id != ""


class TestLoadMissionConfig:
    def test_load_yaml(self, tmp_path):
        yaml_content = """
mission_id: test-glider-2024
glider_name: unit200
institution: Test University
pi_name: Dr. Test
region: Gulf of Mexico
variables:
  - temperature
  - salinity
"""
        cfg_file = tmp_path / "mission.yaml"
        cfg_file.write_text(yaml_content)

        cfg = load_mission_config(cfg_file)
        assert cfg.mission_id == "test-glider-2024"
        assert cfg.glider_name == "unit200"
        assert "temperature" in cfg.variables

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_mission_config(tmp_path / "nonexistent.yaml")


class TestErddapUrl:
    def test_url_format(self):
        assert GLIDER_DAC_ERDDAP.startswith("https://")
        assert "erddap" in GLIDER_DAC_ERDDAP.lower()
