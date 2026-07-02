#!/usr/bin/env python
"""
Backward-compatible entry point for building the publication database.

The implementation now lives in ``genbargo/publications.py``. This shim builds
a standalone publication table for a set of NCBI TSVs by querying NCBI Entrez,
writing/refreshing the cache table.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import pandas as pd  # noqa: E402

from genbargo import publications as pubs  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a database of publications associated with genomes."
    )
    parser.add_argument("-t", "--tsvs", nargs="+", required=True,
                        help="List of TSVs that contain the genome assemblies.")
    parser.add_argument("-e", "--email", required=True,
                        help="Email address for NCBI Entrez API.")
    parser.add_argument("--api-key", default=None,
                        help="NCBI Entrez API key (optional, raises the rate limit).")
    parser.add_argument("-o", "--output", default="publications_cache.tsv",
                        help="Output/cache TSV to write.")
    return parser.parse_args()


def main():
    args = parse_args()
    frames = [pd.read_csv(x, sep="\t", dtype=str) for x in args.tsvs]
    df = pd.concat(frames).reset_index(drop=True)
    accessions = sorted(set(df["Assembly Accession"].astype(str)))

    cache_df = pubs.load_pub_table(args.output)
    _, updated = pubs.build_lookup(
        accessions, pubs._empty_pub_frame(), cache_df,
        args.email, args.api_key, query_api=True,
        today_string=pd.Timestamp.today().strftime("%Y-%m-%d"),
    )
    pubs.save_pub_table(updated, args.output)
    print("Wrote {} publication rows to {}".format(len(updated), args.output))


if __name__ == "__main__":
    main()
