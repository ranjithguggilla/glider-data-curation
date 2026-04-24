"""
Command-line interface for glidercure.

Provides commands for ingesting, merging, analyzing, and packaging
Slocum glider mission data.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from glidercure import __version__

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.version_option(version=__version__, prog_name="glidercure")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Slocum glider mission data curation toolkit."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


@main.command()
@click.argument("mission_id")
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output directory (default: data/<mission_id>/raw).",
)
@click.option(
    "--dataset-id", default=None,
    help="ERDDAP dataset ID (auto-detected if omitted).",
)
@click.option(
    "--config", type=click.Path(exists=True), default=None,
    help="Mission config YAML file.",
)
@click.pass_context
def ingest(
    ctx: click.Context,
    mission_id: str,
    output: Optional[str],
    dataset_id: Optional[str],
    config: Optional[str],
) -> None:
    """Download mission data from IOOS Glider DAC."""
    from glidercure.config import load_mission_config
    from glidercure.ingest import fetch_mission_netcdf

    if config:
        cfg = load_mission_config(Path(config))
        mission_id = cfg.mission_id
        dataset_id = dataset_id or cfg.erddap_dataset_id

    if not dataset_id:
        click.echo(f"Error: --dataset-id required for mission {mission_id}", err=True)
        sys.exit(1)

    out_dir = Path(output) if output else Path("data") / mission_id / "raw"

    click.echo(f"Ingesting mission {mission_id} from ERDDAP...")
    try:
        result = fetch_mission_netcdf(dataset_id, out_dir, mission_id=mission_id)
        click.echo(f"Downloaded: {result}")
    except Exception as exc:
        click.echo(f"Ingest failed: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.argument("mission_id")
@click.option(
    "-i", "--input-dir", type=click.Path(exists=True), default=None,
    help="Directory with raw segment files.",
)
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output merged NetCDF path.",
)
@click.pass_context
def merge(
    ctx: click.Context,
    mission_id: str,
    input_dir: Optional[str],
    output: Optional[str],
) -> None:
    """Merge segment files into a single CF trajectory NetCDF."""
    from glidercure.merge import merge_from_single_file, merge_segments

    raw_dir = Path(input_dir) if input_dir else Path("data") / mission_id / "raw"
    out_path = (
        Path(output) if output
        else Path("data") / mission_id / f"{mission_id}_trajectory.nc"
    )

    if not raw_dir.exists():
        click.echo(f"Error: input directory not found: {raw_dir}", err=True)
        sys.exit(1)

    nc_files = sorted(raw_dir.glob("*.nc"))
    if not nc_files:
        click.echo(f"Error: no NetCDF files in {raw_dir}", err=True)
        sys.exit(1)

    click.echo(f"Merging {len(nc_files)} segment(s) for {mission_id}...")

    try:
        if len(nc_files) == 1:
            result_path, digest = merge_from_single_file(nc_files[0], out_path, mission_id)
        else:
            result_path, digest = merge_segments(nc_files, out_path, mission_id)
        click.echo(f"Merged trajectory: {result_path}")
        click.echo(f"SHA-256: {digest}")
    except Exception as exc:
        click.echo(f"Merge failed: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.argument("mission_id")
@click.option(
    "-i", "--input", "input_nc", type=click.Path(exists=True), default=None,
    help="Merged trajectory NetCDF.",
)
@click.option(
    "--json", "output_json", type=click.Path(), default=None,
    help="Output metrics JSON path.",
)
@click.pass_context
def metrics(
    ctx: click.Context,
    mission_id: str,
    input_nc: Optional[str],
    output_json: Optional[str],
) -> None:
    """Compute mission-level metrics and statistics."""
    import json

    import xarray as xr

    from glidercure.metrics import compute_metrics

    nc_path = (
        Path(input_nc) if input_nc
        else Path("data") / mission_id / f"{mission_id}_trajectory.nc"
    )

    if not nc_path.exists():
        click.echo(f"Error: trajectory not found: {nc_path}", err=True)
        sys.exit(1)

    click.echo(f"Computing metrics for {mission_id}...")
    ds = xr.open_dataset(nc_path)
    m = compute_metrics(ds, mission_id)
    ds.close()

    # Display summary
    click.echo(f"  Distance:     {m.distance_km:.1f} km")
    click.echo(f"  Duration:     {m.duration_days:.1f} days")
    click.echo(f"  Observations: {m.n_observations:,}")
    click.echo(f"  Max depth:    {m.max_depth_m:.0f} m")
    click.echo(f"  Dives:        ~{m.n_dives}")

    if output_json:
        json_path = Path(output_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(m.to_dict(), indent=2))
        click.echo(f"Metrics saved: {json_path}")


@main.command(name="map")
@click.argument("mission_id")
@click.option(
    "-i", "--input", "input_nc", type=click.Path(exists=True), default=None,
    help="Merged trajectory NetCDF.",
)
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output map HTML path.",
)
@click.pass_context
def mission_map(
    ctx: click.Context,
    mission_id: str,
    input_nc: Optional[str],
    output: Optional[str],
) -> None:
    """Generate interactive Folium map of mission track."""
    import xarray as xr

    from glidercure.mission_map import generate_mission_map

    nc_path = (
        Path(input_nc) if input_nc
        else Path("data") / mission_id / f"{mission_id}_trajectory.nc"
    )
    out_path = (
        Path(output) if output
        else Path("data") / mission_id / f"{mission_id}_map.html"
    )

    if not nc_path.exists():
        click.echo(f"Error: trajectory not found: {nc_path}", err=True)
        sys.exit(1)

    click.echo(f"Generating map for {mission_id}...")
    ds = xr.open_dataset(nc_path)
    result = generate_mission_map(ds, out_path, mission_id)
    ds.close()
    click.echo(f"Map saved: {result}")


@main.command()
@click.argument("mission_id")
@click.option(
    "-i", "--input", "input_nc", type=click.Path(exists=True), default=None,
    help="Merged trajectory NetCDF.",
)
@click.option(
    "-o", "--output-dir", type=click.Path(), default=None,
    help="Output package directory.",
)
@click.option("--version", "pkg_version", default="1.0.0", help="Package version.")
@click.option("--creator", default="Ranjith Guggilla", help="Creator name.")
@click.option(
    "--no-report", is_flag=True, help="Skip report generation.",
)
@click.option(
    "--no-map", is_flag=True, help="Skip map generation.",
)
@click.pass_context
def package(
    ctx: click.Context,
    mission_id: str,
    input_nc: Optional[str],
    output_dir: Optional[str],
    pkg_version: str,
    creator: str,
    no_report: bool,
    no_map: bool,
) -> None:
    """Build a complete mission archive package."""
    import xarray as xr

    from glidercure.derived import compute_derived_variables
    from glidercure.metrics import compute_metrics
    from glidercure.mission_map import generate_mission_map
    from glidercure.package import package_mission
    from glidercure.qc import apply_qc
    from glidercure.report import generate_mission_report

    nc_path = (
        Path(input_nc) if input_nc
        else Path("data") / mission_id / f"{mission_id}_trajectory.nc"
    )
    out_dir = Path(output_dir) if output_dir else Path("data") / mission_id / "pkg"

    if not nc_path.exists():
        click.echo(f"Error: trajectory not found: {nc_path}", err=True)
        sys.exit(1)

    click.echo(f"Packaging mission {mission_id}...")

    # Load dataset
    ds = xr.open_dataset(nc_path)

    # Derived variables
    click.echo("  Computing derived variables...")
    ds = compute_derived_variables(ds)

    # QC
    click.echo("  Applying QARTOD QC...")
    ds, qc_report = apply_qc(ds)

    # Metrics
    click.echo("  Computing metrics...")
    m = compute_metrics(ds, mission_id)

    # Report
    report_path = None
    if not no_report:
        click.echo("  Generating report...")
        report_path = out_dir / f"{mission_id}_report.html"
        generate_mission_report(m, qc_report, report_path, mission_id)

    # Map
    map_path = None
    if not no_map:
        click.echo("  Generating map...")
        map_path = out_dir / f"{mission_id}_map.html"
        try:
            generate_mission_map(ds, map_path, mission_id)
        except Exception as exc:
            click.echo(f"  Map generation skipped: {exc}", err=True)
            map_path = None

    ds.close()

    # Package
    click.echo("  Assembling package...")
    pkg_dir = package_mission(
        mission_id, nc_path, m, out_dir,
        version=pkg_version, report_html=report_path,
        map_html=map_path, creator_name=creator,
    )

    click.echo(f"Package assembled: {pkg_dir}")


@main.command()
@click.argument("mission_id")
@click.option(
    "-i", "--input-dir", type=click.Path(exists=True), default=None,
    help="Package directory to verify.",
)
@click.pass_context
def verify(ctx: click.Context, mission_id: str, input_dir: Optional[str]) -> None:
    """Verify package integrity against MANIFEST."""
    from glidercure.package import verify_package

    pkg_dir = (
        Path(input_dir) if input_dir
        else Path("data") / mission_id / "pkg" / f"{mission_id}_v1.0.0"
    )

    if not pkg_dir.exists():
        click.echo(f"Error: package not found: {pkg_dir}", err=True)
        sys.exit(1)

    click.echo(f"Verifying package: {pkg_dir.name}...")
    errors = verify_package(pkg_dir)

    if errors:
        click.echo(f"FAILED: {len(errors)} error(s)")
        for err in errors:
            click.echo(f"  - {err}")
        sys.exit(1)
    else:
        click.echo("PASSED: all checksums verified")


@main.command()
@click.argument("mission_id")
@click.option("--version", "pkg_version", default="1.0.0", help="Release version.")
@click.option("--creator", default="Ranjith Guggilla", help="Creator name.")
@click.option(
    "--doi", default=None, help="Pre-registered DOI.",
)
@click.pass_context
def release(
    ctx: click.Context,
    mission_id: str,
    pkg_version: str,
    creator: str,
    doi: Optional[str],
) -> None:
    """Generate release metadata (DataCite XML, tag info)."""
    import json

    from glidercure.datacite import generate_datacite_xml
    from glidercure.metrics import MissionMetrics

    metrics_path = Path("data") / mission_id / "pkg" / f"{mission_id}_v{pkg_version}" / "metrics.json"

    if not metrics_path.exists():
        click.echo(f"Error: metrics not found: {metrics_path}", err=True)
        click.echo("Run 'glidercure package' first.")
        sys.exit(1)

    data = json.loads(metrics_path.read_text())

    # Reconstruct metrics from JSON
    m = MissionMetrics(
        mission_id=data.get("mission_id", mission_id),
        distance_km=data.get("spatial", {}).get("distance_km", 0),
        lat_min=data.get("spatial", {}).get("lat_range", [0, 0])[0],
        lat_max=data.get("spatial", {}).get("lat_range", [0, 0])[1],
        lon_min=data.get("spatial", {}).get("lon_range", [0, 0])[0],
        lon_max=data.get("spatial", {}).get("lon_range", [0, 0])[1],
        start_time=data.get("temporal", {}).get("start", ""),
        end_time=data.get("temporal", {}).get("end", ""),
        duration_days=data.get("temporal", {}).get("duration_days", 0),
        max_depth_m=data.get("depth", {}).get("max_m", 0),
        n_observations=data.get("observations", 0),
    )

    xml = generate_datacite_xml(
        m, mission_id, version=pkg_version,
        creator_name=creator, doi=doi,
    )

    out_path = Path("data") / mission_id / "pkg" / f"{mission_id}_v{pkg_version}" / "datacite.xml"
    out_path.write_text(xml)

    click.echo(f"DataCite XML: {out_path}")
    click.echo(f"Tag: v{pkg_version}-{mission_id}")
    click.echo(f"DOI: {doi or f'10.5281/zenodo.DRAFT-{mission_id}'}")


if __name__ == "__main__":
    main()
