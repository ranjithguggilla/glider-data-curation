"""
DataCite DOI metadata XML generation.

Produces DataCite 4.4 schema-compliant XML for DOI registration.
Each tagged release of a mission package generates a fresh XML
document suitable for submission to DataCite or Zenodo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lxml import etree

from glidercure.metrics import MissionMetrics

logger = logging.getLogger(__name__)


def generate_datacite_xml(
    metrics: MissionMetrics,
    mission_id: str,
    version: str = "1.0.0",
    creator_name: str = "Ranjith Guggilla",
    publisher: str = "Self-published",
    doi: Optional[str] = None,
) -> str:
    """
    Generate DataCite 4.4 metadata XML for a mission package.

    Args:
        metrics: Computed mission metrics.
        mission_id: Mission identifier.
        version: Package version.
        creator_name: Dataset creator name.
        publisher: Publishing organization.
        doi: Pre-registered DOI (if known).

    Returns:
        DataCite XML as string.
    """
    year = datetime.now(timezone.utc).strftime("%Y")

    nsmap = {
        None: "http://datacite.org/schema/kernel-4",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    root = etree.Element("resource", nsmap=nsmap)
    root.set(
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
        "http://datacite.org/schema/kernel-4 "
        "https://schema.datacite.org/meta/kernel-4.4/metadata.xsd",
    )

    # Identifier
    identifier = etree.SubElement(root, "identifier", identifierType="DOI")
    identifier.text = doi or f"10.5281/zenodo.DRAFT-{mission_id}"

    # Creators
    creators = etree.SubElement(root, "creators")
    creator = etree.SubElement(creators, "creator")
    name_elem = etree.SubElement(creator, "creatorName", nameType="Personal")
    name_elem.text = creator_name

    # Titles
    titles = etree.SubElement(root, "titles")
    title = etree.SubElement(titles, "title")
    title.text = f"Slocum glider mission {mission_id} — curated trajectory data"

    # Publisher
    pub = etree.SubElement(root, "publisher")
    pub.text = publisher

    # Publication year
    pub_year = etree.SubElement(root, "publicationYear")
    pub_year.text = year

    # Resource type
    rt = etree.SubElement(root, "resourceType", resourceTypeGeneral="Dataset")
    rt.text = "Glider trajectory dataset"

    # Subjects
    subjects = etree.SubElement(root, "subjects")
    for kw in ["glider", "Slocum", "oceanography", "trajectory", "CTD",
               "Gulf of Mexico", "IOOS"]:
        subj = etree.SubElement(subjects, "subject")
        subj.text = kw

    # Dates
    dates = etree.SubElement(root, "dates")
    if metrics.start_time and metrics.end_time:
        collected = etree.SubElement(dates, "date", dateType="Collected")
        collected.text = f"{metrics.start_time[:10]}/{metrics.end_time[:10]}"
    created = etree.SubElement(dates, "date", dateType="Created")
    created.text = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Language
    lang = etree.SubElement(root, "language")
    lang.text = "en"

    # Version
    ver = etree.SubElement(root, "version")
    ver.text = version

    # Rights
    rights_list = etree.SubElement(root, "rightsList")
    rights = etree.SubElement(
        rights_list, "rights",
        rightsURI="https://creativecommons.org/licenses/by/4.0/",
    )
    rights.text = "CC-BY-4.0"

    # Description
    descriptions = etree.SubElement(root, "descriptions")
    desc = etree.SubElement(descriptions, "description", descriptionType="Abstract")
    desc.text = (
        f"Curated trajectory data from Slocum glider mission {mission_id}. "
        f"Duration: {metrics.duration_days:.1f} days, "
        f"distance: {metrics.distance_km:.1f} km, "
        f"max depth: {metrics.max_depth_m:.0f} m, "
        f"{metrics.n_observations:,} observations. "
        f"CF-1.8 trajectory NetCDF with TEOS-10 derived variables, "
        f"IOOS QARTOD quality flags, and SHA-256 fixity."
    )

    # GeoLocation
    if metrics.lat_min and metrics.lon_min:
        geo_locations = etree.SubElement(root, "geoLocations")
        geo = etree.SubElement(geo_locations, "geoLocation")
        box = etree.SubElement(geo, "geoLocationBox")
        etree.SubElement(box, "westBoundLongitude").text = str(round(metrics.lon_min, 4))
        etree.SubElement(box, "eastBoundLongitude").text = str(round(metrics.lon_max, 4))
        etree.SubElement(box, "southBoundLatitude").text = str(round(metrics.lat_min, 4))
        etree.SubElement(box, "northBoundLatitude").text = str(round(metrics.lat_max, 4))

    # Related identifiers
    related = etree.SubElement(root, "relatedIdentifiers")
    rel_id = etree.SubElement(
        related, "relatedIdentifier",
        relatedIdentifierType="URL",
        relationType="IsDerivedFrom",
    )
    rel_id.text = "https://gliders.ioos.us/"

    xml_str = etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")

    return xml_str


def write_datacite_xml(
    metrics: MissionMetrics,
    mission_id: str,
    output_path: Path,
    **kwargs,
) -> Path:
    """Generate and write DataCite XML to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    xml = generate_datacite_xml(metrics, mission_id, **kwargs)
    output_path.write_text(xml)
    logger.info("Wrote DataCite XML: %s", output_path)
    return output_path
