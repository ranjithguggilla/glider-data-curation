"""Tests for DataCite XML generation."""

from __future__ import annotations

import pytest
from lxml import etree

from glidercure.datacite import generate_datacite_xml, write_datacite_xml
from glidercure.metrics import MissionMetrics


@pytest.fixture
def sample_metrics():
    return MissionMetrics(
        mission_id="test-mission-001",
        distance_km=145.3,
        lat_min=27.5,
        lat_max=28.2,
        lon_min=-90.1,
        lon_max=-89.5,
        start_time="2024-03-15T00:00",
        end_time="2024-03-20T12:00",
        duration_days=5.5,
        max_depth_m=200.0,
        n_observations=50000,
    )


class TestGenerateDataCiteXML:
    def test_returns_xml_string(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert isinstance(xml, str)
        assert xml.startswith("<?xml")

    def test_valid_xml(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        root = etree.fromstring(xml.encode("utf-8"))
        assert root.tag.endswith("resource")

    def test_contains_identifier(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"dc": "http://datacite.org/schema/kernel-4"}
        ident = root.find("dc:identifier", ns)
        assert ident is not None
        assert "test-mission-001" in ident.text

    def test_custom_doi(self, sample_metrics):
        xml = generate_datacite_xml(
            sample_metrics, "test-mission-001",
            doi="10.5281/zenodo.12345",
        )
        assert "10.5281/zenodo.12345" in xml

    def test_contains_creator(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "Ranjith Guggilla" in xml

    def test_custom_creator(self, sample_metrics):
        xml = generate_datacite_xml(
            sample_metrics, "test-mission-001",
            creator_name="Jane Doe",
        )
        assert "Jane Doe" in xml

    def test_contains_title(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "test-mission-001" in xml
        assert "trajectory data" in xml.lower()

    def test_contains_geo_location(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "geoLocationBox" in xml
        assert "27.5" in xml

    def test_contains_subjects(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        for kw in ["glider", "Slocum", "oceanography"]:
            assert kw in xml

    def test_datacite_44_schema(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "kernel-4" in xml
        assert "kernel-4.4" in xml

    def test_cc_by_license(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "CC-BY-4.0" in xml

    def test_description_includes_metrics(self, sample_metrics):
        xml = generate_datacite_xml(sample_metrics, "test-mission-001")
        assert "145.3 km" in xml
        assert "5.5 days" in xml
        assert "50,000 observations" in xml


class TestWriteDataCiteXML:
    def test_writes_file(self, sample_metrics, tmp_path):
        out = tmp_path / "datacite.xml"
        result = write_datacite_xml(sample_metrics, "test-001", out)
        assert result.exists()
        content = result.read_text()
        assert "<?xml" in content

    def test_creates_parent_dirs(self, sample_metrics, tmp_path):
        out = tmp_path / "deep" / "nested" / "datacite.xml"
        result = write_datacite_xml(sample_metrics, "test-001", out)
        assert result.exists()
