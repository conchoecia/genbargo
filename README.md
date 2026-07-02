# genbargo

[![ci](https://github.com/conchoecia/genbargo/actions/workflows/ci.yml/badge.svg)](https://github.com/conchoecia/genbargo/actions/workflows/ci.yml)
[![weekly dashboard](https://github.com/conchoecia/genbargo/actions/workflows/weekly.yml/badge.svg)](https://github.com/conchoecia/genbargo/actions/workflows/weekly.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**genbargo** works out whether a genome assembly is still under embargo.

Many genome consortia (the Vertebrate Genomes Project and affiliates, the
Wellcome Sanger Institute, DNA Zoo, …) release assemblies publicly *before*
publishing on them, under data-use policies that embargo third-party
genome-wide analyses for a period of time. genbargo reads assembly metadata from
NCBI/ENA, applies each submitter's policy, links assemblies to the publications
that release them early, and reports which assemblies are safe to use.

➡️ **[See the current embargo dashboard](dashboard/README.md)** (updated weekly).

## What it does

1. **Scrape** assembly metadata from NCBI (`genbargo scrape`).
2. **Annotate** each assembly's embargo status from its submitter's policy
   (`genbargo filter`). See [`docs/embargo_policies.md`](docs/embargo_policies.md).
3. **Link publications** — a published VGP assembly is released from its embargo
   (`genbargo pubs`; manual table + cached NCBI Entrez lookups).
4. **Report** — write per-status spreadsheets, a text report, and a Markdown
   dashboard (`genbargo report`).

## Install

```bash
git clone https://github.com/conchoecia/genbargo.git
cd genbargo
conda env create -f environment.yml   # pandas, biopython, ete4, ncbi-datasets-cli, ...
conda activate genbargo
```

Or, into an existing environment: `pip install -e .` (the NCBI `datasets` /
`dataformat` binaries, needed only for `scrape`, come from `ncbi-datasets-cli`).

## Usage

```bash
# End-to-end (what the weekly Action runs): scrape -> annotate -> dashboard
genbargo all --config genbargo.config.yaml

# Or step by step:
genbargo scrape --taxon 33208 --outdir input          # 33208 = Metazoa; 7742 = Vertebrata
genbargo filter -t input/33208_YYYYMMDD.tsv -c -d output
```

`genbargo filter` is also available as the backward-compatible script
`filter_assemblies.py` (same flags: `-t -c -p -d -r -n`).

Key outputs:
- `dashboard/README.md` — the human-readable dashboard (+ `all.tsv`, `embargoed.tsv`).
- `output/<prefix>_{all,embargoed,notembargoed}_<date>.tsv` — full spreadsheets.
- `output/<prefix>_report_<date>.txt` — text summary.

## Automation

A weekly [GitHub Action](.github/workflows/weekly.yml) regenerates the dashboard
from fresh NCBI data and commits it back. Set the repository secrets
`ENTREZ_EMAIL` (required by NCBI) and, optionally, `NCBI_API_KEY` (higher Entrez
rate limit). Configure the scraped taxon and other options in
[`genbargo.config.yaml`](genbargo.config.yaml).

## Development

```bash
pip install -e ".[dev]"
pytest          # embargo-date logic (uses a pinned "today")
ruff check genbargo tests
```

## License

MIT — see [LICENSE](LICENSE). If you use genbargo, please cite it
([CITATION.cff](CITATION.cff)).
