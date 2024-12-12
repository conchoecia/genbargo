#!/usr/bin/env python

"""
This script builds a database of publications from a curated list of genome assemblies.

The point of this script is to enable this processing to be done in a single step,
  as it requires several API calls for every genome assembly.

# 1. Load a list of genome assemblies
# 2. Loop through the dataframe and query whether there is an associated publication.

"""

import argparse
from Bio import Entrez
import pandas as pd
import sys

def fetch_accession_info(accession_id):
    """
    Fetches assembly summary from NCBI Entrez for a given assembly ID.
    """
    assembly_id = get_assembly_id(accession_id)
    print("Assembly Accession: ", accession_id)
    print("  - corresponding assembly_id: ", assembly_id)
    print("The assembly ID is: ", assembly_id)
    sys.exit()
    with Entrez.esummary(db="assembly", id=assembly_id, report="full") as handle:
        summary = Entrez.read(handle, validate=False)  # Set validate=False to handle unexpected tags
    print(summary)
    sys.exit()
    return summary

def get_assembly_id(accession):
    with Entrez.esearch(db="assembly", term=accession) as handle:
        record = Entrez.read(handle)
    return record.get("IdList", [])

def extract_bioprojects_and_publications(assembly_info):
    """
    Extracts GB_BioProjects, RS_BioProjects, and associated publication information from assembly summary.
    """
    bioprojects = []
    publications = []

    # Extract GB_BioProjects and RS_BioProjects
    if 'DocumentSummarySet' in assembly_info:
        for doc_summary in assembly_info['DocumentSummarySet']['DocumentSummary']:
            # Extract GB_BioProjects
            if 'GB_BioProjects' in doc_summary:
                for bioproject in doc_summary['GB_BioProjects']:
                    bioprojects.append({
                        'Type': 'GB',
                        'BioprojectAccn': bioproject.get('BioprojectAccn', ''),
                        'BioprojectId': bioproject.get('BioprojectId', '')
                    })

            # Extract RS_BioProjects
            if 'RS_BioProjects' in doc_summary:
                for bioproject in doc_summary['RS_BioProjects']:
                    bioprojects.append({
                        'Type': 'RS',
                        'BioprojectAccn': bioproject.get('BioprojectAccn', ''),
                        'BioprojectId': bioproject.get('BioprojectId', '')
                    })

            # Extract associated publications if available
            if 'PubMedIds' in doc_summary:
                publications.extend(doc_summary['PubMedIds'])

    return bioprojects, publications


def parse_args():
    """
    The arguments we need
    """
    parser = argparse.ArgumentParser(description="Build a database of publications associated with genomes.")
    parser.add_argument("-t", "--tsvs", nargs="+", help="List of csvs that contain the annotated and unannotated genomes.")
    parser.add_argument("-e", "--email", required = True, help="Email address for NCBI Entrez API.")
    # default is the present working directory
    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    print(args)
    Entrez.email = args.email
    # 1. Load a list of genome assemblies
    list_of_NCBI_csvs = args.tsvs
     # (2) Load a csv of annotated and unannotated genomes.
    list_of_dfs = [pd.read_csv(x, sep = "\t")
                   for x in list_of_NCBI_csvs]
    # concatenate these into one dataframe
    df = pd.concat(list_of_dfs)
    df = df.reset_index(drop = True)

    # 2. Loop through the dataframe and query whether there is an associated publication.
    for index, row in df.iterrows():
        accession_id = row["Assembly Accession"]
        assembly_info = fetch_accession_info(accession_id)
        bioprojects, publications = extract_bioprojects_and_publications(assembly_info)

        # Print the results
        print("BioProjects:")
        for bioproject in bioprojects:
            print(f"Type: {bioproject['Type']}, Accession: {bioproject['BioprojectAccn']}, ID: {bioproject['BioprojectId']}")

        print("\nPublications:")
        for pub in publications:
            print(f"PubMed ID: {pub}")
        sys.exit()

if __name__ == '__main__':
    main()