"""
Interactive Folium map generation for glider mission tracks.

Produces an HTML map with the glider trajectory, dive markers,
depth-colored track, and mission summary popup.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


def generate_mission_map(
    ds: xr.Dataset,
    output_path: Path,
    mission_id: str = "",
    subsample: int = 50,
) -> Path:
    """
    Generate an interactive Folium map of the mission track.

    Args:
        ds: Merged trajectory dataset with lat/lon.
        output_path: Path for output HTML file.
        mission_id: Mission identifier for title.
        subsample: Plot every Nth point to keep map responsive.

    Returns:
        Path to generated HTML map.
    """
    import folium
    from folium.plugins import AntPath

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lat = _get_var(ds, ["latitude", "lat"])
    lon = _get_var(ds, ["longitude", "lon"])

    if lat is None or lon is None:
        logger.error("Cannot generate map: missing latitude/longitude")
        raise ValueError("Missing latitude or longitude in dataset")

    lat_vals = lat.values
    lon_vals = lon.values

    # Filter valid coordinates
    mask = np.isfinite(lat_vals) & np.isfinite(lon_vals)
    lat_clean = lat_vals[mask]
    lon_clean = lon_vals[mask]

    if len(lat_clean) == 0:
        raise ValueError("No valid coordinates in dataset")

    # Subsample for performance
    if len(lat_clean) > subsample * 10:
        indices = np.arange(0, len(lat_clean), max(1, len(lat_clean) // (subsample * 10)))
        lat_sub = lat_clean[indices]
        lon_sub = lon_clean[indices]
    else:
        lat_sub = lat_clean
        lon_sub = lon_clean

    # Center map
    center_lat = float(np.mean(lat_sub))
    center_lon = float(np.mean(lon_sub))

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles="CartoDB positron",
    )

    # Track line
    track_points = list(zip(lat_sub.tolist(), lon_sub.tolist()))
    folium.PolyLine(
        track_points,
        color="#2196F3",
        weight=2,
        opacity=0.7,
        tooltip=f"Mission: {mission_id}",
    ).add_to(m)

    # Animated track
    try:
        AntPath(
            track_points[::max(1, len(track_points) // 200)],
            color="#FF5722",
            weight=3,
            opacity=0.6,
            delay=1000,
        ).add_to(m)
    except Exception:
        pass  # AntPath is optional

    # Start marker
    folium.Marker(
        [float(lat_sub[0]), float(lon_sub[0])],
        popup=f"<b>Mission Start</b><br>{mission_id}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
        tooltip="Start",
    ).add_to(m)

    # End marker
    folium.Marker(
        [float(lat_sub[-1]), float(lon_sub[-1])],
        popup=f"<b>Mission End</b><br>{mission_id}",
        icon=folium.Icon(color="red", icon="stop", prefix="fa"),
        tooltip="End",
    ).add_to(m)

    # Depth-colored markers (every Nth point)
    depth = _get_var(ds, ["depth", "pressure"])
    if depth is not None:
        depth_vals = depth.values[mask]
        if len(depth_vals) == len(lat_clean):
            step = max(1, len(lat_clean) // subsample)
            for i in range(0, len(lat_clean), step):
                d = depth_vals[i]
                if not np.isfinite(d):
                    continue
                color = _depth_color(d)
                folium.CircleMarker(
                    [float(lat_clean[i]), float(lon_clean[i])],
                    radius=3,
                    color=color,
                    fill=True,
                    fill_opacity=0.6,
                    popup=f"Depth: {d:.1f} m",
                ).add_to(m)

    # Title
    title_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 1000;
                background: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-family: sans-serif;">
        <b>Mission:</b> {mission_id}<br>
        <b>Points:</b> {len(lat_clean):,}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    m.save(str(output_path))
    logger.info("Generated mission map: %s (%d points)", output_path, len(lat_sub))
    return output_path


def _depth_color(depth: float) -> str:
    """Map depth to color: shallow=blue, deep=dark blue/purple."""
    if depth < 20:
        return "#64B5F6"  # light blue
    elif depth < 50:
        return "#42A5F5"
    elif depth < 100:
        return "#2196F3"
    elif depth < 200:
        return "#1976D2"
    elif depth < 500:
        return "#1565C0"
    else:
        return "#0D47A1"  # dark blue


def _get_var(ds: xr.Dataset, names: list):
    for name in names:
        if name in ds.data_vars:
            return ds[name]
        if name in ds.coords:
            return ds[name]
    return None
