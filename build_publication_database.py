#!/usr/bin/env python

"""
This script builds a database of publications from a curated list of genome assemblies.

The point of this script is to enable this processing to be done in a single step,
  as it requires several API calls for every genome assembly.

"""

import argparse

def parse_args():
    """
    The arguments we need
    """
    parser = argparse.ArgumentParser(description="Build a database of publications associated with genomes.")
    parser.add_argument("-t", "-tsvs", nargs="+", help="List of csvs that contain the annotated and unannotated genomes.")
    # default is the present working directory
    args = parser.parse_args()
    return args

def main():
    args = parse_args()

if __name__ == '__main__':
    main()