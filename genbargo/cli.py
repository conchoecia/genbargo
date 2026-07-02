#!/usr/bin/env python
"""
Command-line interface for genbargo.

Subcommands
-----------
  scrape   Download NCBI assembly metadata into a genbargo input TSV.
  filter   Annotate embargo status of one or more input TSVs (the core tool).
  pubs     Build/refresh the publication cache for a set of assemblies.
  report   Regenerate the Markdown dashboard from an existing "*_all_*.tsv".
  all      scrape -> filter (+publications) -> dashboard, driven by config.
           This is what the weekly GitHub Action runs.
"""

import argparse
import os
import types

import pandas as pd

from genbargo import __version__, embargo, publications, report, scrape

DEFAULT_CONFIG = {
    "taxon": 33208,
    "input_dir": "input",
    "output_dir": "output",
    "dashboard_dir": "dashboard",
    "prefix": "spreadsheet_genomes",
    "conservative": True,
    "query_publications": True,
    "email": "dts@lehigh.edu",
    "api_key": None,
}


def load_config(path):
    """Load a YAML config, falling back to defaults for missing keys."""
    cfg = dict(DEFAULT_CONFIG)
    if path and os.path.exists(path):
        import yaml  # noqa: PLC0415
        with open(path) as fh:
            loaded = yaml.safe_load(fh) or {}
        cfg.update({k: v for k, v in loaded.items() if v is not None})
    # Environment overrides (used in CI).
    cfg["email"] = os.environ.get("ENTREZ_EMAIL", cfg.get("email"))
    cfg["api_key"] = os.environ.get("NCBI_API_KEY", cfg.get("api_key"))
    return cfg


def _datestamp():
    return pd.Timestamp.today().strftime("%Y%m%d")


# --------------------------------------------------------------------------- #
# Subcommand implementations
# --------------------------------------------------------------------------- #
def cmd_scrape(args):
    tsv = scrape.scrape(
        taxon=args.taxon,
        outdir=args.outdir,
        datestamp=_datestamp(),
        datasets_bin=args.datasets_bin,
        dataformat_bin=args.dataformat_bin,
        add_lineage=not args.no_lineage,
        taxdump_dir=args.taxdump,
    )
    print(tsv)
    return tsv


def _filter_namespace(tsvs, output_dir, dashboard_dir, prefix, conservative,
                      query_publications, email, api_key, no_dashboard=False):
    return types.SimpleNamespace(
        tsvs=tsvs,
        conservative=conservative,
        prefix=prefix,
        rbh_directory=None,
        output_directory=output_dir,
        no_transfer=False,
        publications_manual=embargo.DEFAULT_MANUAL_PUBS,
        publications_cache=embargo.DEFAULT_CACHE_PUBS,
        query_publications=query_publications,
        email=email,
        api_key=api_key,
        dashboard_dir=dashboard_dir,
        no_dashboard=no_dashboard,
    )


def cmd_filter(args):
    ns = _filter_namespace(
        tsvs=args.tsvs,
        output_dir=args.output_directory,
        dashboard_dir=args.dashboard_dir,
        prefix=args.prefix,
        conservative=args.conservative,
        query_publications=args.query_publications,
        email=args.email,
        api_key=args.api_key,
        no_dashboard=args.no_dashboard,
    )
    for tsv in ns.tsvs:
        if not os.path.exists(tsv):
            raise IOError("The file {} does not exist.".format(tsv))
    embargo.main(ns)


def cmd_pubs(args):
    frames = [pd.read_csv(x, sep="\t", dtype=str) for x in args.tsvs]
    df = pd.concat(frames).reset_index(drop=True)
    accessions = sorted(set(df["Assembly Accession"].astype(str)))
    cache_df = publications.load_pub_table(args.output)
    _, updated = publications.build_lookup(
        accessions, publications._empty_pub_frame(), cache_df,
        args.email, args.api_key, query_api=True,
        today_string=pd.Timestamp.today().strftime("%Y-%m-%d"),
    )
    publications.save_pub_table(updated, args.output)
    print("Wrote {} publication rows to {}".format(len(updated), args.output))


def cmd_report(args):
    df = pd.read_csv(args.tsv, sep="\t")
    md = report.write_markdown_dashboard(df, args.dashboard_dir)
    print("Wrote dashboard to {}".format(md))


def cmd_all(args):
    cfg = load_config(args.config)
    datestamp = _datestamp()
    tsv = scrape.scrape(
        taxon=cfg["taxon"],
        outdir=cfg["input_dir"],
        datestamp=datestamp,
        add_lineage=True,
        taxdump_dir=args.taxdump,
    )
    ns = _filter_namespace(
        tsvs=[tsv],
        output_dir=cfg["output_dir"],
        dashboard_dir=cfg["dashboard_dir"],
        prefix=cfg["prefix"],
        conservative=cfg["conservative"],
        query_publications=cfg["query_publications"],
        email=cfg["email"],
        api_key=cfg["api_key"],
    )
    embargo.main(ns)


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def build_parser():
    parser = argparse.ArgumentParser(prog="genbargo", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="genbargo " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scrape", help="Download NCBI assembly metadata into a TSV.")
    p.add_argument("--taxon", default="33208", help="NCBI taxon id (default 33208 = Metazoa).")
    p.add_argument("--outdir", default="input", help="Output directory for the TSV.")
    p.add_argument("--no-lineage", action="store_true", help="Skip the ete4 Lineage column.")
    p.add_argument("--datasets-bin", default=None, help="Path to the `datasets` binary.")
    p.add_argument("--dataformat-bin", default=None, help="Path to the `dataformat` binary.")
    p.add_argument("--taxdump", default=None, help="Path to an ete4 taxonomy sqlite db.")
    p.set_defaults(func=cmd_scrape)

    p = sub.add_parser("filter", help="Annotate embargo status of input TSV(s).")
    p.add_argument("-t", "--tsvs", nargs="+", required=True)
    p.add_argument("-c", "--conservative", action="store_true", default=False)
    p.add_argument("-p", "--prefix", default="spreadsheet_genomes")
    p.add_argument("-d", "--output_directory", default=os.getcwd())
    p.add_argument("--dashboard-dir", default=embargo.DEFAULT_DASHBOARD_DIR)
    p.add_argument("--no-dashboard", action="store_true", default=False)
    p.add_argument("--query-publications", action="store_true", default=False)
    p.add_argument("--email", default=None)
    p.add_argument("--api-key", default=None)
    p.set_defaults(func=cmd_filter)

    p = sub.add_parser("pubs", help="Build/refresh the publication cache.")
    p.add_argument("-t", "--tsvs", nargs="+", required=True)
    p.add_argument("-e", "--email", required=True)
    p.add_argument("--api-key", default=None)
    p.add_argument("-o", "--output", default="assembly_specifications/publications_cache.tsv")
    p.set_defaults(func=cmd_pubs)

    p = sub.add_parser("report", help="Regenerate the dashboard from an existing TSV.")
    p.add_argument("-t", "--tsv", required=True, help="An existing *_all_*.tsv spreadsheet.")
    p.add_argument("--dashboard-dir", default=embargo.DEFAULT_DASHBOARD_DIR)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("all", help="scrape -> filter -> dashboard (config-driven).")
    p.add_argument("--config", default="genbargo.config.yaml")
    p.add_argument("--taxdump", default=None, help="Path to an ete4 taxonomy sqlite db.")
    p.set_defaults(func=cmd_all)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
