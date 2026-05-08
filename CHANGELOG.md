# Changelog

## [1.0.0] - 2024-04-20

### Added
- IOOS Glider DAC ERDDAP ingestion with SHA-256 checksums
- Segment merge into CF-1.8 trajectory NetCDF
- TEOS-10 derived variables (absolute salinity, conservative temperature, sigma0, sound speed)
- Mixed layer depth estimation (density threshold criterion)
- IOOS QARTOD quality control flags with spike detection and gap analysis
- Mission-level metrics (distance, depth distribution, sensor uptime, dive count)
- Interactive Folium mission track map with depth-colored markers
- HTML mission report with Jinja2 template (print-to-PDF)
- DataCite 4.4 metadata XML generation for DOI registration
- Self-contained archive packaging with MANIFEST and integrity verification
- CLI with ingest, merge, metrics, map, package, verify, release commands
