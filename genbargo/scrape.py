#!/usr/bin/env python
"""
Fetch genome-assembly metadata from NCBI and shape it into a genbargo input TSV.

This makes genbargo self-contained: it can regenerate the exact TSV the embargo
annotator consumes, without depending on an external pipeline. It is a thin,
metadata-only wrapper around the official NCBI ``datasets`` / ``dataformat``
command-line tools (no sequence or annotation downloads), plus an ete4 step that
adds the ``Lineage`` column (the semicolon-delimited taxid path, e.g. ``;7742;``,
that the embargo report uses to detect vertebrates).

Recipe (mirrors the chrombase scrape):
    datasets summary genome taxon --as-json-lines <taxid> > <taxid>.json
    dataformat tsv genome --inputfile <taxid>.json --fields <FIELDS> > <taxid>.tsv
    (+ add the Lineage column via ete4 NCBITaxa)
"""

import os
import shutil
import subprocess

import pandas as pd

# dataformat field list (vendored from chrombase src/InferDB.py `fields_to_print`).
# dataformat renames each of these to the human-readable column names that the
# embargo annotator reads (e.g. "accession" -> "Assembly Accession").
FIELDS_TO_PRINT = [
    "accession",
    "annotinfo-busco-complete", "annotinfo-busco-duplicated",
    "annotinfo-busco-fragmented", "annotinfo-busco-lineage",
    "annotinfo-busco-missing", "annotinfo-busco-singlecopy",
    "annotinfo-busco-totalcount", "annotinfo-busco-version",
    "annotinfo-featcount-gene-non-coding", "annotinfo-featcount-gene-other",
    "annotinfo-featcount-gene-protein-coding", "annotinfo-featcount-gene-pseudogene",
    "annotinfo-featcount-gene-total", "annotinfo-method", "annotinfo-name",
    "annotinfo-pipeline", "annotinfo-provider", "annotinfo-release-date",
    "annotinfo-report-url", "annotinfo-software-version", "annotinfo-status",
    "assminfo-assembly-method", "assminfo-atypicalis-atypical",
    "assminfo-atypicalwarnings", "assminfo-biosample-accession",
    "assminfo-biosample-bioproject-accession",
    "assminfo-biosample-bioproject-parent-accession",
    "assminfo-biosample-bioproject-parent-accessions",
    "assminfo-biosample-bioproject-title",
    "assminfo-biosample-description-comment",
    "assminfo-biosample-description-organism-common-name",
    "assminfo-biosample-description-organism-infraspecific-breed",
    "assminfo-biosample-description-organism-infraspecific-cultivar",
    "assminfo-biosample-description-organism-infraspecific-ecotype",
    "assminfo-biosample-description-organism-infraspecific-isolate",
    "assminfo-biosample-description-organism-infraspecific-sex",
    "assminfo-biosample-description-organism-infraspecific-strain",
    "assminfo-biosample-description-organism-name",
    "assminfo-biosample-description-organism-pangolin",
    "assminfo-biosample-description-organism-tax-id",
    "assminfo-biosample-description-title", "assminfo-biosample-ids-db",
    "assminfo-biosample-last-updated", "assminfo-biosample-models",
    "assminfo-biosample-owner-contact-lab", "assminfo-biosample-owner-name",
    "assminfo-biosample-package", "assminfo-biosample-publication-date",
    "assminfo-biosample-status-status", "assminfo-biosample-status-when",
    "assminfo-blast-url", "assminfo-description", "assminfo-level",
    "assminfo-linked-assm-accession", "assminfo-linked-assm-type",
    "assminfo-name", "assminfo-notes", "assminfo-paired-assm-accession",
    "assminfo-paired-assm-changed", "assminfo-paired-assm-manual-diff",
    "assminfo-paired-assm-name", "assminfo-paired-assm-only-genbank",
    "assminfo-paired-assm-only-refseq", "assminfo-paired-assm-status",
    "assminfo-refseq-category", "assminfo-release-date",
    "assminfo-sequencing-tech", "assminfo-status", "assminfo-submitter",
    "assminfo-type", "assmstats-contig-l50", "assmstats-contig-n50",
    "assmstats-gaps-between-scaffolds-count", "assmstats-gc-percent",
    "assmstats-genome-coverage", "assmstats-number-of-component-sequences",
    "assmstats-number-of-contigs", "assmstats-number-of-organelles",
    "assmstats-number-of-scaffolds", "assmstats-scaffold-l50",
    "assmstats-scaffold-n50", "assmstats-total-number-of-chromosomes",
    "assmstats-total-sequence-len", "assmstats-total-ungapped-len",
    "current-accession", "organelle-assembly-name",
    "organelle-bioproject-accessions", "organelle-description",
    "organelle-infraspecific-name", "organelle-submitter",
    "organelle-total-seq-length", "organism-common-name",
    "organism-infraspecific-breed", "organism-infraspecific-isolate",
    "organism-infraspecific-sex", "organism-name", "organism-pangolin",
    "organism-tax-id", "source_database", "type_material-display_text",
    "wgs-contigs-url", "wgs-project-accession", "wgs-url",
]

# Column that holds the organism NCBI taxid after dataformat renames the fields.
_TAXID_COLUMN = "Organism Taxonomic ID"


def _resolve_binary(name, explicit=None):
    """Find an NCBI CLI binary by explicit path, PATH, or a repo-local bin/."""
    if explicit:
        if not os.path.exists(explicit):
            raise IOError("{} not found at {}".format(name, explicit))
        return explicit
    found = shutil.which(name)
    if found:
        return found
    repo_bin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", name
    )
    if os.path.exists(repo_bin):
        return repo_bin
    raise IOError(
        "Could not find the '{}' binary. Install ncbi-datasets-cli "
        "(e.g. `conda install -c conda-forge ncbi-datasets-cli`) or pass its "
        "path explicitly.".format(name)
    )


def download_summary_json(taxon, out_json, datasets_bin=None):
    """Run `datasets summary genome taxon --as-json-lines`."""
    datasets_bin = _resolve_binary("datasets", datasets_bin)
    with open(out_json, "w") as fh:
        subprocess.run(
            [datasets_bin, "summary", "genome", "taxon", "--as-json-lines", str(taxon)],
            stdout=fh, check=True,
        )
    return out_json


def format_json_to_tsv(in_json, out_tsv, dataformat_bin=None):
    """Run `dataformat tsv genome --fields <FIELDS>`."""
    dataformat_bin = _resolve_binary("dataformat", dataformat_bin)
    with open(out_tsv, "w") as fh:
        subprocess.run(
            [dataformat_bin, "tsv", "genome", "--inputfile", in_json,
             "--fields", ",".join(FIELDS_TO_PRINT)],
            stdout=fh, check=True,
        )
    return out_tsv


def add_lineage_column(df, taxdump_dir=None):
    """Add the ``Lineage`` column (``;taxid;taxid;...;``) using ete4 NCBITaxa."""
    from ete4 import NCBITaxa  # noqa: PLC0415  (optional heavy dependency)

    ncbi = NCBITaxa(dbfile=taxdump_dir) if taxdump_dir else NCBITaxa()

    if _TAXID_COLUMN not in df.columns:
        raise IOError(
            "Expected column '{}' not found; cannot build lineage.".format(_TAXID_COLUMN)
        )

    unique_taxids = sorted({
        int(t) for t in pd.to_numeric(df[_TAXID_COLUMN], errors="coerce").dropna()
    })
    lineage_map = {}
    for taxid in unique_taxids:
        try:
            lineage = ncbi.get_lineage(taxid)
            lineage_map[taxid] = ";" + ";".join(str(x) for x in lineage) + ";"
        except Exception:  # noqa: BLE001 - taxid may be obsolete/unknown
            lineage_map[taxid] = ";{};".format(taxid)

    def _lookup(t):
        t = pd.to_numeric(t, errors="coerce")
        if pd.isna(t):
            return ""
        return lineage_map.get(int(t), ";{};".format(int(t)))

    df["Lineage"] = df[_TAXID_COLUMN].apply(_lookup)
    return df


def scrape(taxon, outdir, datestamp, datasets_bin=None, dataformat_bin=None,
           add_lineage=True, taxdump_dir=None):
    """Scrape NCBI metadata for ``taxon`` and write a genbargo input TSV.

    Returns the path to the final TSV (with the Lineage column added).
    """
    os.makedirs(outdir, exist_ok=True)
    base = "{}_{}".format(taxon, datestamp)
    json_path = os.path.join(outdir, base + ".json")
    tsv_path = os.path.join(outdir, base + ".tsv")

    print("Downloading NCBI genome summary for taxon {}...".format(taxon))
    download_summary_json(taxon, json_path, datasets_bin=datasets_bin)
    print("Formatting JSON to TSV...")
    format_json_to_tsv(json_path, tsv_path, dataformat_bin=dataformat_bin)

    df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    print("  {} assemblies retrieved.".format(len(df)))
    if add_lineage:
        print("Adding Lineage column via ete4 (this can be slow on first run)...")
        df = add_lineage_column(df, taxdump_dir=taxdump_dir)
        df.to_csv(tsv_path, sep="\t", index=False)
    return tsv_path
