# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-07-02

### Added
- Python package `genbargo` with a `genbargo` command-line interface exposing
  `scrape`, `filter`, `pubs`, `report`, and `all` subcommands.
- `genbargo scrape`: self-contained NCBI metadata scraper (NCBI `datasets` /
  `dataformat` + ete4 lineage) so the repository no longer depends on an
  external pipeline to produce its input.
- Publication linking (`genbargo/publications.py`): finishes the former
  `build_publication_database.py` prototype, linking assemblies to publications
  via a curated manual table and cached NCBI Entrez lookups. A published VGP
  assembly now has its embargo lifted (step 5 of the pipeline, previously a
  TODO).
- Markdown dashboard of embargoed assemblies, regenerated weekly and rendered on
  the GitHub repository page (`dashboard/README.md`).
- GitHub Actions: `ci.yml` (pytest + ruff on push/PR) and `weekly.yml`
  (scheduled scrape → annotate → dashboard, committed back to the repo).
- Packaging and project metadata: `pyproject.toml`, `environment.yml`,
  `genbargo.config.yaml`, `LICENSE` (MIT), `CITATION.cff`, tests, and
  `docs/embargo_policies.md`.

### Changed
- Core embargo logic moved from `filter_assemblies.py` into `genbargo/embargo.py`.
  The reference "today" is now injectable (`set_now`) so the date logic is
  testable. `filter_assemblies.py` and `build_publication_database.py` remain as
  backward-compatible entry-point shims.
- Text columns are coerced to strings on load, fixing a crash on assemblies with
  an empty BioSample description comment.
- The text report now emits the repository URL instead of `Github: TBD`.
