"""
Configuration and mission registry.

Defines the IOOS Glider DAC ERDDAP/THREDDS endpoints and mission
metadata structures used throughout the pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

logger = logging.getLogger(__name__)

# IOOS Glider DAC ERDDAP base URL
GLIDER_DAC_ERDDAP = "https://gliders.ioos.us/erddap"

# IOOS Glider DAC THREDDS catalog
GLIDER_DAC_THREDDS = "https://gliders.ioos.us/thredds"

# Default data directory layout
DEFAULT_DATA_ROOT = Path("data")
DEFAULT_RAW_DIR = "raw"
DEFAULT_MERGED_DIR = "merged"
DEFAULT_PRODUCTS_DIR = "products"
DEFAULT_PACKAGES_DIR = "packages"


@dataclass
class MissionConfig:
    """Configuration for a single glider mission."""

    mission_id: str
    glider_name: str = ""
    institution: str = ""
    pi_name: str = ""
    region: str = "Gulf of Mexico"
    start_date: str = ""
    end_date: str = ""
    variables: List[str] = field(default_factory=lambda: [
        "time", "latitude", "longitude", "depth",
        "temperature", "conductivity", "salinity", "density",
        "pressure",
    ])
    erddap_dataset_id: str = ""
    data_root: Path = DEFAULT_DATA_ROOT

    @property
    def raw_dir(self) -> Path:
        return self.data_root / DEFAULT_RAW_DIR / self.mission_id

    @property
    def merged_dir(self) -> Path:
        return self.data_root / DEFAULT_MERGED_DIR

    @property
    def products_dir(self) -> Path:
        return self.data_root / DEFAULT_PRODUCTS_DIR / self.mission_id

    @property
    def packages_dir(self) -> Path:
        return self.data_root / DEFAULT_PACKAGES_DIR


def load_mission_config(path: Path) -> MissionConfig:
    """Load mission configuration from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)

    return MissionConfig(
        mission_id=data["mission_id"],
        glider_name=data.get("glider_name", ""),
        institution=data.get("institution", ""),
        pi_name=data.get("pi_name", ""),
        region=data.get("region", "Gulf of Mexico"),
        start_date=data.get("start_date", ""),
        end_date=data.get("end_date", ""),
        variables=data.get("variables", [
            "time", "latitude", "longitude", "depth",
            "temperature", "conductivity", "salinity", "density",
            "pressure",
        ]),
        erddap_dataset_id=data.get("erddap_dataset_id", ""),
        data_root=Path(data.get("data_root", str(DEFAULT_DATA_ROOT))),
    )


# Example Gulf of Mexico missions from IOOS Glider DAC
EXAMPLE_MISSIONS = {
    "unit_507-20230815T0000": MissionConfig(
        mission_id="unit_507-20230815T0000",
        glider_name="unit_507",
        institution="USF",
        pi_name="C. Lembke",
        region="Gulf of Mexico",
        erddap_dataset_id="unit_507-20230815T0000",
    ),
    "sam-20190815T0000": MissionConfig(
        mission_id="sam-20190815T0000",
        glider_name="sam",
        institution="TAMU",
        region="Gulf of Mexico",
        erddap_dataset_id="sam-20190815T0000",
    ),
}
