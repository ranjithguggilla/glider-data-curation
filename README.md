# glider-data-curation

Slocum glider mission archive pipeline. Ingests IOOS Glider DAC segment files, merges into CF-1.8 trajectory NetCDF, computes derived oceanographic variables, applies QARTOD quality control, and produces publication-ready archive packages with interactive maps, mission reports, and DataCite DOI metadata.

[![CI](https://github.com/ranjithguggilla/glider-data-curation/actions/workflows/ci.yml/badge.svg)](https://github.com/ranjithguggilla/glider-data-curation/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Architecture

```
IOOS Glider DAC (ERDDAP)
         │
         ▼
   ┌─────────────┐
   │   Ingest     │  Download segments, SHA-256 checksums
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │    Merge     │  Concatenate → CF-1.8 trajectory NetCDF
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │   Derived    │  GSW: SA, CT, sigma0, sound speed
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │     QC       │  QARTOD flags: range, spike, gap
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │   Metrics    │  Distance, depth, dives, uptime
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │   Package    │  NetCDF + report + map + DataCite XML
   └─────────────┘
```

## Installation

```bash
git clone https://github.com/ranjithguggilla/glider-data-curation.git
cd glider-data-curation
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Usage

### Ingest from IOOS Glider DAC

```bash
# Download mission data from ERDDAP
glidercure ingest usf-bass-2024 --dataset-id allDatasets

# Or use a config file
glidercure ingest usf-bass-2024 --config missions/bass.yaml
```

### Merge segments

```bash
# Merge downloaded segments into a single CF trajectory file
glidercure merge usf-bass-2024 -i data/usf-bass-2024/raw

# Or specify output path
glidercure merge usf-bass-2024 -i data/raw/ -o output/trajectory.nc
```

### Compute metrics

```bash
# Compute and display mission statistics
glidercure metrics usf-bass-2024

# Export as JSON
glidercure metrics usf-bass-2024 --json output/metrics.json
```

### Generate mission map

```bash
# Create interactive Folium map
glidercure map usf-bass-2024 -o output/map.html
```

### Build archive package

```bash
# Full pipeline: derived vars → QC → metrics → report → map → package
glidercure package usf-bass-2024 --version 1.0.0

# Skip optional outputs
glidercure package usf-bass-2024 --no-map --no-report
```

### Verify package integrity

```bash
# Check all SHA-256 checksums against MANIFEST
glidercure verify usf-bass-2024
```

### Generate release metadata

```bash
# DataCite XML for DOI registration
glidercure release usf-bass-2024 --version 1.0.0 --doi 10.5281/zenodo.12345
```

## Configuration

Mission configuration uses YAML files:

```yaml
mission_id: usf-bass-2024
glider_name: bass
institution: University of South Florida
pi_name: Dr. Chad Lembke
region: Gulf of Mexico
variables:
  - temperature
  - salinity
  - conductivity
  - pressure
  - depth
erddap_dataset_id: usf-bass
```

## Output Structure

```
usf-bass-2024_v1.0.0/
├── usf-bass-2024_trajectory.nc    # CF-1.8 trajectory NetCDF
├── datacite.xml                    # DataCite 4.4 DOI metadata
├── metrics.json                    # Machine-readable metrics
├── usf-bass-2024_report.html      # Mission summary report
├── usf-bass-2024_map.html         # Interactive Folium map
├── package.json                    # Package descriptor
├── MANIFEST.json                   # SHA-256 checksums
└── README.txt                      # Package documentation
```

## Standards Compliance

| Standard | Implementation |
|----------|---------------|
| CF-1.8 | Trajectory discrete sampling geometry, standard variable attributes |
| ACDD-1.3 | Global discovery metadata attributes |
| IOOS QARTOD | Flag values 1/2/3/4/9 with range, spike, and gap tests |
| TEOS-10 | GSW-derived absolute salinity, conservative temperature, sigma0 |
| DataCite 4.4 | DOI registration XML with geospatial bounding box |
| CC-BY-4.0 | Default license for archive packages |

## Derived Variables

Computed using the Gibbs SeaWater (GSW) library following TEOS-10:

- **Absolute Salinity (SA)**: from practical salinity, pressure, and position
- **Conservative Temperature (CT)**: from in-situ temperature
- **Potential Density Anomaly (sigma0)**: referenced to 0 dbar
- **Sound Speed**: for acoustic applications
- **Mixed Layer Depth**: density threshold criterion (0.03 kg/m³)

## Quality Control

QARTOD flag application per variable:

1. **Range test** — physically plausible bounds (bad if outside, suspect near edges)
2. **Spike test** — rolling median MAD outlier detection
3. **Gap test** — temporal discontinuity detection

## Testing

```bash
# Run all tests
make test

# With coverage
make test-cov

# Lint
make lint
```

## Project Structure

```
glidercure/
├── __init__.py          # Package metadata
├── cli.py               # Click CLI entry point
├── config.py            # Mission configuration
├── ingest.py            # ERDDAP data download
├── merge.py             # Segment merge + CF attributes
├── derived.py           # TEOS-10 derived variables
├── qc.py                # QARTOD quality control
├── metrics.py           # Mission-level statistics
├── mission_map.py       # Folium interactive map
├── report.py            # Jinja2 HTML report
├── datacite.py          # DataCite 4.4 XML
├── package.py           # Archive assembly
└── templates/
    └── mission_report.html
```

## Technical Details

See [docs/METHODS.md](docs/METHODS.md) for detailed documentation of algorithms, standards compliance, and references.

## License

MIT License. See [LICENSE](LICENSE) for details.
