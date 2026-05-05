# Technical Methods

## Data Source

Raw segment files are obtained from the IOOS Glider Data Assembly Center (DAC), which aggregates Slocum, Spray, and Seaglider data from US-funded glider operators. This toolkit targets Slocum glider missions deployed in the Gulf of Mexico, accessing data through the DAC's ERDDAP tabledap API.

## Segment Merging

Individual dive-segment NetCDF files are concatenated along the observation dimension, sorted by timestamp, and deduplicated. The merged dataset conforms to CF-1.8 discrete sampling geometry (featureType = trajectory) with ACDD-1.3 discovery metadata. A `trajectory` variable with `cf_role = trajectory_id` links all observations to the mission identifier.

Encoding uses zlib compression (level 4) with chunked storage to balance file size against random-access performance.

## Derived Variables

Four TEOS-10 variables are computed using the Gibbs SeaWater (GSW) library:

- **Absolute Salinity (SA)**: Converted from Practical Salinity using `gsw.SA_from_SP` with in-situ pressure and position.
- **Conservative Temperature (CT)**: Converted from in-situ temperature using `gsw.CT_from_t`, providing a more accurate measure of heat content.
- **Potential Density Anomaly (sigma0)**: Referenced to 0 dbar via `gsw.sigma0`, used for stratification analysis and mixed layer depth estimation.
- **Sound Speed**: Computed from `gsw.sound_speed` for acoustic applications.

## Mixed Layer Depth

Estimated using the density threshold criterion: MLD is the shallowest depth where potential density exceeds the 10 m reference value by 0.03 kg/m³. This follows de Boyer Montégut et al. (2004) with the threshold adapted for coastal Gulf of Mexico conditions.

## Quality Control

IOOS QARTOD flag conventions are applied:

| Flag | Meaning       |
|------|---------------|
| 1    | Good          |
| 2    | Not evaluated |
| 3    | Suspect       |
| 4    | Bad           |
| 9    | Missing       |

Three QC tests are applied per variable:

1. **Range test**: Values outside physically plausible bounds are flagged bad (4). Values near range boundaries are flagged suspect (3).
2. **Spike test**: A rolling-window median absolute deviation (MAD) detector identifies statistical outliers. Points exceeding 5× MAD from the local median are flagged suspect.
3. **Gap test**: Temporal gaps exceeding a configurable threshold (default 1 hour) are recorded for reporting.

NaN values are automatically flagged as missing (9).

## Distance Computation

Total track distance is computed via the Haversine formula applied to sequential valid (non-NaN) latitude/longitude pairs. Earth radius is taken as 6371.0 km.

## Dive Estimation

Dive count is estimated by counting transitions from shallow (< threshold) to deep in the depth time series. The threshold is set at 30% of the median depth or 5 m, whichever is larger, to avoid counting surface noise as dives.

## Depth Binning

Observations are binned into six depth ranges: 0–50 m, 50–100 m, 100–200 m, 200–500 m, 500–1000 m, and >1000 m. This provides a quick overview of the sampling distribution across the water column.

## Mission Report

The HTML report is rendered from a Jinja2 template with CSS optimized for browser-based PDF export (A4 page size, print media queries). It includes stat cards for key metrics, depth distribution table, sensor uptime bars, QC flag summary, and gap analysis.

## DataCite Metadata

DOI registration metadata follows the DataCite 4.4 kernel schema. The XML includes geospatial bounding box (from trajectory extents), temporal coverage, resource type (Dataset), subjects, and related identifiers linking back to the IOOS Glider DAC.

## Archive Packaging

The final package is a self-contained directory with:

- Merged CF trajectory NetCDF
- DataCite 4.4 XML
- Metrics JSON
- HTML mission report
- Interactive Folium map
- SHA-256 MANIFEST for integrity verification
- Machine-readable package descriptor

## References

- CF Conventions 1.8: https://cfconventions.org/Data/cf-conventions/cf-conventions-1.8/cf-conventions.html
- IOOS QARTOD: https://ioos.noaa.gov/project/qartod/
- TEOS-10 / GSW: https://www.teos-10.org/
- DataCite 4.4: https://schema.datacite.org/meta/kernel-4.4/
- IOOS Glider DAC: https://gliders.ioos.us/
- de Boyer Montégut, C., et al. (2004). Mixed layer depth over the global ocean. JGR Oceans, 109(C12003).
