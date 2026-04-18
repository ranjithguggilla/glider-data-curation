"""
PDF mission report generation via Jinja2 + HTML.

Produces a publication-grade mission summary report from computed
metrics, QC results, and mission configuration. The report is
rendered as HTML from a Jinja2 template and can be saved as HTML
(for browser-based PDF export) or viewed directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from glidercure.metrics import MissionMetrics
from glidercure.qc import QCReport

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_mission_report(
    metrics: MissionMetrics,
    qc_report: QCReport,
    output_path: Path,
    mission_id: str = "",
    map_path: Optional[Path] = None,
) -> Path:
    """
    Generate an HTML mission summary report.

    The report includes mission overview, trajectory statistics,
    depth distribution, sensor uptime, QC summary, and gap analysis.
    Designed for browser-based PDF printing with clean formatting.

    Args:
        metrics: Computed mission metrics.
        qc_report: QC summary report.
        output_path: Path for output HTML file.
        mission_id: Mission identifier.
        map_path: Optional path to mission map HTML (for embedding link).

    Returns:
        Path to generated report.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    template = env.get_template("mission_report.html")

    now_utc = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%d %H:%M UTC")
    )

    context = {
        "mission_id": mission_id or metrics.mission_id,
        "generated_at": now_utc,
        "metrics": metrics,
        "qc": qc_report,
        "map_filename": map_path.name if map_path else None,
        "depth_bins": metrics.depth_bins,
        "sensor_uptime": metrics.sensor_uptime,
        "gaps": qc_report.gaps,
        "flags_summary": qc_report.flags_summary,
    }

    html = template.render(**context)
    output_path.write_text(html)
    logger.info("Generated mission report: %s", output_path)

    # Also write metrics JSON
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(metrics.to_dict(), indent=2))
    logger.info("Wrote metrics JSON: %s", json_path)

    return output_path
