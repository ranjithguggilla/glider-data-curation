#!/usr/bin/env python3
"""
Demo: Run the full glider-data-curation pipeline with synthetic data.

This shows every output the pipeline produces — from raw data
through to a complete mission archive package.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

from glidercure.datacite import generate_datacite_xml
from glidercure.derived import compute_derived_variables, compute_mixed_layer_depth
from glidercure.merge import merge_segments
from glidercure.metrics import compute_metrics
from glidercure.mission_map import generate_mission_map
from glidercure.package import package_mission, verify_package
from glidercure.qc import apply_qc
from glidercure.report import generate_mission_report

MISSION_ID = "demo-gulf-2026"
OUTPUT_DIR = Path("demo_output")


def create_synthetic_segments(out_dir: Path) -> list[Path]:
    """Create two fake glider segment files simulating a Gulf of Mexico mission."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    segments = []
    for seg_idx, (start_obs, n) in enumerate([(0, 300), (300, 200)]):
        base_time = np.datetime64("2026-04-10T00:00:00")
        times = base_time + (np.arange(n) + start_obs) * np.timedelta64(15, "m")

        lat = 27.5 + np.cumsum(rng.normal(0.001, 0.0005, n))
        lon = -90.0 + np.cumsum(rng.normal(0.0005, 0.0003, n))

        period = 40
        phase = np.linspace(0, n / period * 2 * np.pi, n)
        depth = 100 * (1 - np.cos(phase)) + rng.normal(0, 2, n)
        depth = np.clip(depth, 0, 250)

        pressure = depth * 1.01
        temp = 25 - 0.05 * depth + rng.normal(0, 0.3, n)
        sal = 35.0 + 0.005 * depth + rng.normal(0, 0.05, n)
        conductivity = sal * 0.001 * (1 + 0.02 * temp)

        ds = xr.Dataset(
            {
                "temperature": ("obs", temp.astype(np.float32)),
                "salinity": ("obs", sal.astype(np.float32)),
                "pressure": ("obs", pressure.astype(np.float32)),
                "depth": ("obs", depth.astype(np.float32)),
                "conductivity": ("obs", conductivity.astype(np.float32)),
            },
            coords={
                "time": ("obs", times),
                "latitude": ("obs", lat),
                "longitude": ("obs", lon),
            },
        )

        path = out_dir / f"segment_{seg_idx + 1:03d}.nc"
        ds.to_netcdf(path)
        segments.append(path)

    return segments


def main():
    # Clean previous run
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    print("=" * 60)
    print("GLIDER-DATA-CURATION: Full Pipeline Demo")
    print("=" * 60)

    # ── Step 1: Create synthetic segment files ──
    print("\n[1/8] Creating synthetic glider segments...")
    seg_dir = OUTPUT_DIR / "raw"
    segments = create_synthetic_segments(seg_dir)
    for seg in segments:
        size_kb = seg.stat().st_size / 1024
        print(f"  Created: {seg.name} ({size_kb:.0f} KB)")

    # ── Step 2: Merge segments ──
    print("\n[2/8] Merging segments into CF-1.8 trajectory NetCDF...")
    merged_path = OUTPUT_DIR / f"{MISSION_ID}_trajectory.nc"
    result_path, digest = merge_segments(segments, merged_path, MISSION_ID)
    size_kb = result_path.stat().st_size / 1024
    print(f"  Output: {result_path.name} ({size_kb:.0f} KB)")
    print(f"  SHA-256: {digest[:32]}...")

    # ── Step 3: Compute derived variables ──
    print("\n[3/8] Computing TEOS-10 derived variables...")
    ds = xr.open_dataset(merged_path)
    ds = compute_derived_variables(ds)
    derived_vars = ["absolute_salinity", "conservative_temperature", "sigma0", "sound_speed"]
    for var in derived_vars:
        if var in ds.data_vars:
            vals = ds[var].values[np.isfinite(ds[var].values)]
            print(f"  {var}: min={vals.min():.2f}, max={vals.max():.2f}, units={ds[var].attrs.get('units', '?')}")

    mld = compute_mixed_layer_depth(ds)
    if mld:
        print(f"  Mixed layer depth: {mld:.1f} m")

    # ── Step 4: Apply QARTOD QC ──
    print("\n[4/8] Applying IOOS QARTOD quality control...")
    ds_qc, qc_report = apply_qc(ds)
    qc_vars = [v for v in ds_qc.data_vars if v.endswith("_qc")]
    print(f"  Variables checked: {qc_report.variables_checked}")
    print(f"  Overall good: {qc_report.overall_good_pct:.1f}%")
    print(f"  Spikes detected: {qc_report.spike_count}")
    print(f"  Gaps found: {len(qc_report.gaps)}")
    for var, flags in qc_report.flags_summary.items():
        print(f"  {var}: good={flags.get('good', 0)}, suspect={flags.get('suspect', 0)}, bad={flags.get('bad', 0)}, missing={flags.get('missing', 0)}")

    # ── Step 5: Compute metrics ──
    print("\n[5/8] Computing mission metrics...")
    metrics = compute_metrics(ds_qc, MISSION_ID)
    print(f"  Distance:     {metrics.distance_km:.1f} km")
    print(f"  Duration:     {metrics.duration_days:.1f} days")
    print(f"  Observations: {metrics.n_observations:,}")
    print(f"  Max depth:    {metrics.max_depth_m:.0f} m")
    print(f"  Dives:        ~{metrics.n_dives}")
    print(f"  Lat range:    {metrics.lat_min:.4f} to {metrics.lat_max:.4f}")
    print(f"  Lon range:    {metrics.lon_min:.4f} to {metrics.lon_max:.4f}")
    print(f"  Temp range:   {metrics.temp_min:.2f} to {metrics.temp_max:.2f} C")
    print(f"  Sal range:    {metrics.sal_min:.2f} to {metrics.sal_max:.2f}")
    print(f"  Depth bins:")
    for bin_name, count in metrics.depth_bins.items():
        pct = count / metrics.n_observations * 100 if metrics.n_observations > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"    {bin_name:>10s}: {count:5d} ({pct:5.1f}%) {bar}")
    print(f"  Sensor uptime:")
    for var, pct in metrics.sensor_uptime.items():
        bar = "#" * int(pct / 2)
        print(f"    {var:>15s}: {pct:5.1f}% {bar}")

    ds.close()

    # ── Step 6: Generate mission map ──
    print("\n[6/8] Generating interactive Folium map...")
    map_path = OUTPUT_DIR / f"{MISSION_ID}_map.html"
    ds_map = xr.open_dataset(merged_path)
    generate_mission_map(ds_map, map_path, MISSION_ID)
    ds_map.close()
    size_kb = map_path.stat().st_size / 1024
    print(f"  Output: {map_path.name} ({size_kb:.0f} KB)")
    print(f"  Open in browser: file://{map_path.resolve()}")

    # ── Step 7: Generate mission report ──
    print("\n[7/8] Generating HTML mission report...")
    report_path = OUTPUT_DIR / f"{MISSION_ID}_report.html"
    generate_mission_report(metrics, qc_report, report_path, MISSION_ID, map_path=map_path)
    size_kb = report_path.stat().st_size / 1024
    print(f"  Output: {report_path.name} ({size_kb:.0f} KB)")
    print(f"  Open in browser: file://{report_path.resolve()}")

    # ── Step 8: Package everything ──
    print("\n[8/8] Building archive package...")
    pkg_dir = package_mission(
        MISSION_ID, merged_path, metrics, OUTPUT_DIR / "pkg",
        version="1.0.0",
        report_html=report_path,
        map_html=map_path,
    )
    print(f"  Package: {pkg_dir.name}/")
    for f in sorted(pkg_dir.iterdir()):
        size = f.stat().st_size
        print(f"    {f.name:40s} {size:>8,} bytes")

    # Verify package
    errors = verify_package(pkg_dir)
    if not errors:
        print(f"\n  MANIFEST verification: PASSED (all checksums valid)")
    else:
        print(f"\n  MANIFEST verification: FAILED ({len(errors)} errors)")

    # Show DataCite XML snippet
    print("\n  DataCite XML preview:")
    xml = (pkg_dir / "datacite.xml").read_text()
    for line in xml.split("\n")[2:10]:
        print(f"    {line}")
    print("    ...")

    # Show metrics JSON
    print("\n  Metrics JSON preview:")
    mdata = json.loads((pkg_dir / "metrics.json").read_text())
    print(f"    {json.dumps(mdata, indent=2)[:500]}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"\nAll outputs in: {OUTPUT_DIR.resolve()}/")
    print(f"Open the map:    file://{map_path.resolve()}")
    print(f"Open the report: file://{report_path.resolve()}")


if __name__ == "__main__":
    main()
