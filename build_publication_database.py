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
import pprint
import sys
import time



def fetch_assembly_numbers_from_accession(accession, max_retries=10, delay=1):
    """
    This function fetches the assembly ID for a given genome assembly accession
    from NCBI Entrez, with retry logic in case of failure.

    Parameters:
    - accession: The accession ID to search for (e.g., "GCF_000001405.40").
    - max_retries: The maximum number of retries if the query fails (default is 10).
    - delay: The delay time (in seconds) between retries (default is 1 second).

    Returns:
    - A list of assembly IDs found for the given accession.
    """
    retries = 0

    while retries < max_retries:
        try:
            # Perform the search query to the NCBI assembly database
            with Entrez.esearch(db="assembly", term=accession) as handle:
                record = Entrez.read(handle)

            # Get the list of assembly IDs from the response
            entries = record.get("IdList", [])

            if len(entries) > 1:
                print(f"Multiple assembly IDs found for accession: {accession}")
                for entry in entries:
                    print(f"Assembly ID: {entry}")

            return entries  # Return the list of assembly IDs

        except RuntimeError as e:
            # Handle any errors (e.g., network issues, NCBI server unavailability)
            print(f"Attempt {retries + 1} failed: {e}")
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {delay} second(s)...")
                time.sleep(delay)  # Wait before retrying
            else:
                print("Max retries reached. Raising exception.")
                raise  # Re-raise the error after max retries are reached
        except Exception as e:
            # Handle other unexpected exceptions
            print(f"An unexpected error occurred: {e}")
            raise


def fetch_assembly_number_to_summary(assembly_id, max_retries=10, delay=1):
    """
    Fetches assembly summary from NCBI Entrez for a given assembly ID,
    with retry logic for transient errors.
    """
    retries = 0

    while retries < max_retries:
        try:
            with Entrez.esummary(db="assembly", id=assembly_id, report="full") as handle:
                summary = Entrez.read(handle, validate=False)  # Set validate=False to handle unexpected tags
            return dict(summary)
        except RuntimeError as e:
            print(f"Attempt {retries + 1} failed: {e}")
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {delay} second(s)...")
                time.sleep(delay)
            else:
                print("Max retries reached. Raising exception.")
                raise

def dictify(obj):
    """
    Recursively convert DictElement or similar objects to a regular dictionary.
    """
    if isinstance(obj, dict):
        return {key: dictify(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [dictify(element) for element in obj]
    elif hasattr(obj, "items"):  # Handle DictElement
        return {key: dictify(value) for key, value in obj.items()}
    else:
        return obj

def print_summary(summary):
    """
    Print the assembly summary.
    """
    #custom = dict(summary["DocumentSummarySet"]["DocumentSummary"])
    #print(custom)
    summary_dict = dictify(summary)
    #print(type(summary_dict["DocumentSummarySet"]["DocumentSummary"]))
    #print(summary_dict["DocumentSummarySet"]["DocumentSummary"])
    print("- DocumentSummarySet - DocumentSummary")
    for i in range(len(summary_dict["DocumentSummarySet"]["DocumentSummary"])):
        for key in summary_dict["DocumentSummarySet"]["DocumentSummary"][i]:
            if type(summary_dict["DocumentSummarySet"]["DocumentSummary"][i][key]) == dict:
                for key2 in summary_dict["DocumentSummarySet"]["DocumentSummary"][i][key]:
                    print("    - ", key2, " : ", summary_dict["DocumentSummarySet"]["DocumentSummary"][i][key][key2])
            else:
                print("  - ", key, " : ", summary_dict["DocumentSummarySet"]["DocumentSummary"][i][key])


def summary_to_dict_entry(assembly_info):
    """
    Extracts GB_BioProjects, RS_BioProjects, and associated publication information from assembly summary.
    """
    bioprojects = []
    publications = []

    assembly_info = dict(assembly_info)

    # get all of the information

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
                print_summary(assembly_info)
                sys.exit()
            else:
                print("No publications found for this assembly: {}".format(assembly_info['DocumentSummarySet']['DocumentSummary'][0]['AssemblyAccession']))
    return bioprojects, publications

def assembly_accession_to_dict_entries(assembly_accession):
    """
    Takes an Assembly Accession and returns a list of dictionary entries.
      - This list of dictionary entries will be appended to the main list in the
        calling function. Then, this will be converted to a dataframe.

    Input:
      - assembly_accession: The assembly accession ID to search for (e.g., "GCF_000001405.40").

    Output:
        - A list of dictionary entries for the given assembly accession. Headers TBD.

    There are sometimes multiple assembly IDs, because the function sometimes seems
      to pull multiple genome assembly accessions. For example, the accession
      "GCA_000002265.1" for Rattus norvegicus yielded two assembly IDs, which actually
      correspond to different assembly accessions: "GCA_000002265.1" and "GCA_000002265.2".
    """
    list_of_entry_dicts = []
    headers = set()
    # 1. Fetch the assembly ID for the given accession. There may be multiple.
    assembly_ids = fetch_assembly_numbers_from_accession(assembly_accession)
    # 2. If there are multiple assembly IDs, get the info for each one.
    for assembly_id in assembly_ids:
        # collect the summary
        summary = fetch_assembly_number_to_summary(assembly_id, max_retries=10, delay=1)
        print_summary(summary)
        sys.exit()
    #bioprojects, publications = extract_bioprojects_and_publications(assembly_info)



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
    list_of_dict_entries = []
    for index, row in df.iterrows():
        accession_id = row["Assembly Accession"]
        # add the genome assembly information to the dictionary.
        for entry in assembly_accession_to_dict_entries(accession_id):
            list_of_dict_entries.append(entry)

        ## Print the results
        #print("BioProjects:")
        #for bioproject in bioprojects:
        #    print(f"Type: {bioproject['Type']}, Accession: {bioproject['BioprojectAccn']}, ID: {bioproject['BioprojectId']}")

        #print("\nPublications:")
        #for pub in publications:
        #    print(f"PubMed ID: {pub}")

if __name__ == '__main__':
    main()