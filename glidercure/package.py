"""
Mission archive packaging.

Assembles all mission artifacts into a self-contained archive
directory with MANIFEST, checksums, metadata, and README.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from glidercure.datacite import write_datacite_xml
from glidercure.metrics import MissionMetrics

logger = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(directory: Path) -> Dict[str, str]:
    """Build a SHA-256 manifest for all files in a directory."""
    manifest = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            rel = str(path.relative_to(directory))
            manifest[rel] = sha256_file(path)
    return manifest


def package_mission(
    mission_id: str,
    merged_nc: Path,
    metrics: MissionMetrics,
    output_dir: Path,
    version: str = "1.0.0",
    report_html: Optional[Path] = None,
    map_html: Optional[Path] = None,
    creator_name: str = "Ranjith Guggilla",
    publisher: str = "Self-published",
) -> Path:
    """
    Assemble a mission archive package.

    Creates a directory containing the merged NetCDF, DataCite XML,
    metrics JSON, optional report and map, a SHA-256 MANIFEST, and
    a machine-readable package descriptor.

    Args:
        mission_id: Mission identifier.
        merged_nc: Path to merged trajectory NetCDF.
        metrics: Computed mission metrics.
        output_dir: Root output directory.
        version: Package version string.
        report_html: Optional path to HTML mission report.
        map_html: Optional path to interactive map HTML.
        creator_name: Dataset creator name.
        publisher: Publishing organization.

    Returns:
        Path to assembled package directory.
    """
    pkg_name = f"{mission_id}_v{version}"
    pkg_dir = output_dir / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Copy merged NetCDF
    nc_dest = pkg_dir / f"{mission_id}_trajectory.nc"
    shutil.copy2(merged_nc, nc_dest)
    logger.info("Copied trajectory NetCDF: %s", nc_dest.name)

    # Write DataCite XML
    datacite_path = pkg_dir / "datacite.xml"
    write_datacite_xml(
        metrics, mission_id, datacite_path,
        version=version, creator_name=creator_name, publisher=publisher,
    )

    # Write metrics JSON
    metrics_path = pkg_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics.to_dict(), indent=2))
    logger.info("Wrote metrics: %s", metrics_path.name)

    # Copy optional artifacts
    if report_html and report_html.exists():
        shutil.copy2(report_html, pkg_dir / report_html.name)
        logger.info("Included report: %s", report_html.name)

    if map_html and map_html.exists():
        shutil.copy2(map_html, pkg_dir / map_html.name)
        logger.info("Included map: %s", map_html.name)

    # Package descriptor
    descriptor = {
        "package": pkg_name,
        "mission_id": mission_id,
        "version": version,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "creator": creator_name,
        "publisher": publisher,
        "contents": {
            "trajectory_nc": nc_dest.name,
            "datacite_xml": "datacite.xml",
            "metrics_json": "metrics.json",
        },
        "conventions": "CF-1.8, ACDD-1.3",
        "license": "CC-BY-4.0",
    }
    if report_html and report_html.exists():
        descriptor["contents"]["report_html"] = report_html.name
    if map_html and map_html.exists():
        descriptor["contents"]["map_html"] = map_html.name

    desc_path = pkg_dir / "package.json"
    desc_path.write_text(json.dumps(descriptor, indent=2))

    # Build MANIFEST
    manifest = build_manifest(pkg_dir)
    manifest_path = pkg_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Built MANIFEST with %d entries", len(manifest))

    # Write package README
    readme = _generate_package_readme(mission_id, version, metrics, manifest)
    (pkg_dir / "README.txt").write_text(readme)

    logger.info("Assembled package: %s (%d files)", pkg_dir, len(manifest) + 1)
    return pkg_dir


def verify_package(pkg_dir: Path) -> List[str]:
    """
    Verify package integrity against MANIFEST.

    Args:
        pkg_dir: Path to package directory.

    Returns:
        List of verification errors (empty if all pass).
    """
    manifest_path = pkg_dir / "MANIFEST.json"
    if not manifest_path.exists():
        return ["MANIFEST.json not found"]

    manifest = json.loads(manifest_path.read_text())
    errors = []

    for rel_path, expected_hash in manifest.items():
        file_path = pkg_dir / rel_path
        if not file_path.exists():
            errors.append(f"Missing: {rel_path}")
            continue
        actual_hash = sha256_file(file_path)
        if actual_hash != expected_hash:
            errors.append(f"Hash mismatch: {rel_path}")

    return errors


def _generate_package_readme(
    mission_id: str,
    version: str,
    metrics: MissionMetrics,
    manifest: Dict[str, str],
) -> str:
    """Generate a human-readable README for the package."""
    lines = [
        f"Slocum Glider Mission Package: {mission_id}",
        "=" * 50,
        "",
        f"Version:      {version}",
        f"Mission ID:   {mission_id}",
        f"Duration:     {metrics.duration_days:.1f} days",
        f"Distance:     {metrics.distance_km:.1f} km",
        f"Max Depth:    {metrics.max_depth_m:.0f} m",
        f"Observations: {metrics.n_observations:,}",
        "",
        "Contents:",
        "-" * 30,
    ]
    for rel_path in sorted(manifest.keys()):
        lines.append(f"  {rel_path}")
    lines.extend([
        "",
        "Conventions: CF-1.8, ACDD-1.3",
        "License: CC-BY-4.0",
        "",
        "All files have SHA-256 checksums in MANIFEST.json.",
        "Verify with: glidercure verify <package_dir>",
    ])
    return "\n".join(lines) + "\n"
