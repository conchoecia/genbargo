#!/usr/bin/env python

"""
The point of this is to filter a directory of pregenerated rbh files to remove those that may be under embargo

(1) First load the directory of existing files
(2) Load a csv of annotated and unannotated genomes.
(3) Find the files that do not have an accession in the dataframe of assemblies.
     Print these out for the user and make them type something
     to continue or not.
(4) Identify accessions that are possibly under embargo still
     First, we calculate the embargo dates
     a) If the genome was released before May 1st 2024
       i) If the genome is annotated
         - if the annotation was released more than two years
           after the assembly, the annotation date is two
           years after the assembly release date.
         - else (the annotation was
           - the embargo date is two years after the
             annotation’s release date.
       ii) else (the genome is not annotated here)
         - The embargo lift date is two years after the
           assembly upload date
     b) else (released on or after May 1st, 2024)
       i) If the genome is annotated
         - If the annotation was released more than one year
           after the assembly
           - the embargo lift date is one year from the
             assembly upload date.
         - else (the annotation was released less than one
           year after the assembly)
           - the embargo lift date is one year from the
             annotation upload date.
       ii) else (the genome is not annotated)
         - The embargo lift date is one year from the assembly
           upload date
(5) From the list of embargo’d genomes, flag them as out of embargo if they have been published. Give specific publications if they truly have been published.
(6) Write the files:
  - Make a folder that has embargo’d genomes
  - a folder that has genomes that are not embargo’d
  - a folder of genomes that were not on the spreadsheet
  - Output a log file that is dated to reflect the latest changes
  - Touch a file in each directory stating the latest date at which the files in that directory were updated.
  - Make a spreadsheet with the genome assemblies, the embargo status, and a description of why it is or is not under embargo.
"""

import argparse
import os
import sys
import pandas as pd

def _required_column_check(df):
    """
    Just checks that the required columns are in the dataframe.

    List of required columns:
      - "Embargo"
      - "EmbargoPolicy"
      - "EmbargoPolicyLink"
      - "EmbargoReason"
      - "EmbargoLiftPublication"
      - "EmbargoLiftPublicationPMID"
      - "EmbargoLiftPublicationDOI"
      - "EmbargoLiftDate"
      - "EmbargoDaysUntil"
    """
    required_columns = ["Embargo",
                        "EmbargoPolicy",
                        "EmbargoPolicyLink",
                        "EmbargoReason",
                        "EmbargoLiftPublication",
                        "EmbargoLiftPublicationPMID",
                        "EmbargoLiftPublicationDOI",
                        "EmbargoLiftDate",
                        "EmbargoDaysUntil"]
    for column in required_columns:
        if column not in df.columns:
            raise IOError("The column '{}' is not in the dataframe.".format(column))

def _row_helper_DToL(df, index, row):
    """
    This splits out the annotation task for onf row to apply the DToL open data use policy.
    required_columns = ["Embargo",
                        "EmbargoPolicy",
                        "EmbargoPolicyLink",
                        "EmbargoReason",
                        "EmbargoLiftPublication",
                        "EmbargoLiftPublicationPMID",
                        "EmbargoLiftPublicationDOI",
                        "EmbargoLiftDate",
                        "EmbargoDaysUntil"]

    """
    # check that all of the columns are in the dataframe
    _required_column_check(df)
    days_until = int((row["Assembly Release Date"] - pd.Timestamp.today()).days)
    # Add the lack of embargo information.
    embargo_message = ""
    embargo_message =  "This genome falls under the Darwin Tree of Life data use policy."
    embargo_message += " The policy text states, \"DToL data are released freely for reuse for any purpose upon deposition in ENA, and the DToL partners encourage such community reuse.\""
    embargo_message += " This assembly's 'Assembly Release Date' on NCBI/ENA is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))
    embargo_message += " Therefore, the genome has not been under an embargo since its publication date,"
    embargo_message += " {} years and {} days ago".format(-1 * days_until//365, -1 * days_until%365)
    embargo_message += " since this report was generated on {}.".format(pd.Timestamp.today().strftime("%Y-%m-%d"))
    df.at[index, "Embargo"]           = "Not Embargoed"
    df.at[index, "EmbargoPolicy"]     = "Darwin Tree of Life Open Data Release Policy v1.04"
    df.at[index, "EmbargoPolicyLink"] = "https://www.darwintreeoflife.org/wp-content/uploads/2024/10/DToL-Open-Data-Release-Policy.docx_.pdf"
    df.at[index, "EmbargoReason"]     = embargo_message
    df.at[index, "EmbargoLiftDate"]   = row["Assembly Release Date"].strftime("%Y-%m-%d")
    df.at[index, "EmbargoDaysUntil"]  = days_until

def _row_helper_VPG(df, index, row):
    """
    This splits out the annotation task for a specific row to apply the VGP embargo policy.
    This allows us to use this embargo policy against specific rows.

    The reason this was implemented was because all of the VGP genomes fall under this policy,
      and within the Wellcome Sanger Institute, there are some projects that fall under VGP, but
      most under another. Implementing the handling this way avoids copying and pasting the same
      code in multiple functions.
    """
    # check that all of the columns are in the dataframe
    _required_column_check(df)

    # First, check if the genome is annotated. Look for empty fields in the "Annotation Release Date" column.
    embargo_reason_message = ""
    timestamp = ""
    embargo_reason_message += " This genome assembly was uploaded by {} on {} (MMDDYYYY).".format(row["Assembly Submitter"], row["Assembly Release Date"])

    # Set the offset used to calculate the Embargo Lift date. Note the policy and link.
    offset_time = 0
    if row["Assembly Release Date"] < pd.Timestamp("2024-05-01"):
        # Genomes published before May 1st, 2024 fall under the 2018 VGP embargo policy.
        embargo_reason_message =  "This genome falls under the pre-May 1st, 2024 VGP embargo policy, originally published in 2018."
        df.at[index, "EmbargoPolicy"]     = "VGP, pre-May 1st, 2024 policy"
        df.at[index, "EmbargoPolicyLink"] = "https://genome10k.ucsc.edu/data-use-policies/ clarified here: https://vertebrategenomesproject.org/data-use-policies"
        offset_time = 2
    else:
        # These genomes were published on or after May 1st, 2024. These fall under the new VGP embargo policy.
        #  - https://vertebrategenomesproject.org/data-use-policies
        embargo_reason_message =  "This genome falls under the new, post-May 1st, 2024 VGP embargo policy, last updated July 8th, 2024."
        df.at[index, "EmbargoPolicy"]     = "VGP, post-May 1st, 2024 policy"
        df.at[index, "EmbargoPolicyLink"] = "https://vertebrategenomesproject.org/data-use-policies"
        offset_time = 1
    #embargo_reason_message += " The assembly accession number is {}".format(row["Assembly"])
    embargo_reason_message += " This assembly 'Assembly Release Date' on NCBI is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))

    if not pd.isna(row["Annotation Release Date"]):
        # The genome is annotated. We need to check the annotation release date.
        # First, split the assemblies into those published before May 1st, 2024 and those published on or after.
        if row["Annotation Release Date"] - row["Assembly Release Date"] < pd.Timedelta(days = 365 * offset_time):
            # The annotation was released less than two years after the assembly.
            # The Embargo Lift date is two years after the annotation release date.
            timestamp = row["Annotation Release Date"] + pd.DateOffset(years = offset_time)
            embargo_reason_message += " The annotation was released on {}, less than {} year(s) after the assembly upload date.".format(
                row["Annotation Release Date"].strftime("%Y-%m-%d"), offset_time)
            embargo_reason_message += " Under this embargo policy and based on the assembly and annotation release dates, the Embargo Lift Date of this assembly is {} year(s) after the annotation upload date.".format(offset_time)
        else:
            # The annotation was released more than two years after the assembly.
            # Under the 2018 VGP embargo policy, the annotation date is two years after the assembly release date.
            timestamp = row["Assembly Release Date"] + pd.DateOffset(years = offset_time)
            df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
            embargo_reason_message += " The annotation was released on {}, more than {} year(s) after the assembly upload date.".format(
                row["Annotation Release Date"].strftime("%Y-%m-%d"), offset_time)
            embargo_reason_message += " Under this embargo policy and based on the assembly and annotation release dates, the Embargo Lift Date of this assembly is {} year(s) after the assembly upload date.".format(offset_time)
        df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
        embargo_reason_message += " The Embargo Lift Date is therefore {}.".format(df.at[index, "EmbargoLiftDate"])
        df.at[index, "EmbargoReason"] = embargo_reason_message
    else:
        # The genome is not annotated. The Embargo Lift date is therefore 1 or 2 years after the Assembly Release Date
        timestamp = row["Assembly Release Date"] + pd.DateOffset(years = offset_time)
        df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
        embargo_reason_message += " There is no annotation released currently for this assembly. This may change at a later date."
        embargo_reason_message += " Therefore, the Embargo Lift Date is {} year(s) after the assembly upload date.".format(offset_time)
        embargo_reason_message += " The Embargo Lift Date is therefore {}.".format(df.at[index, "EmbargoLiftDate"])

    # Note how many days until (or after) the embargo is over. + means the embargo is still coming up, - means the embargo has passed that many days ago.
    if timestamp == "":
        raise IOError("We should have reinitialized the timestamp before we got here.")
    daysuntil = timestamp - pd.Timestamp.today()
    df.at[index, "EmbargoDaysUntil"] = int(daysuntil.days)

    # if today is after the embargo lift date, then the embargo is lifted.
    if pd.Timestamp.today() > timestamp:
        df.at[index, "Embargo"      ] = "Not Embargoed"
        embargo_reason_message += " This report was generated on {}, {} years and {} days after the Embargo Lift Date, and therefore the genome is no longer embargoed.".format(
            pd.Timestamp.today().strftime("%Y-%m-%d"), -1 * int(daysuntil.days)//365, -1 * int(daysuntil.days)%365)
    else:
        df.at[index, "Embargo"]       = "Embargoed"
        embargo_reason_message += " This report was generated on {}, {} days before the Embargo Lift Date, and therefore the genome is still embargoed.".format(
            pd.Timestamp.today().strftime("%Y-%m-%d"), daysuntil.days)
    # This is the end of the for loop for the rows where we will process the entries under the VGP
    df.at[index, "EmbargoReason"] = embargo_reason_message

def _annotate_embargo_status_VGP(df):
    """
    Helper function called by annotate_embargo_status. Only used to annotate the rows with VGP genomes.

    Takes in a pandas dataframe and annotates the rows with the VGP embargo status.
    The ingested dataframe should already contain the columns we need to annotate.
    Returns the pandas dataframe with the VGP embargo status annotated.

    Case for the following organizations, specified on the VGP website:
    - Vertebrate Genomes Project:
      - Website: https://vertebrategenomesproject.org/data-use-policies
      - Embargo: 2 years from the assembly release date for things prior to May 1st, 2024. 1 year for things after May 1st, 2024. It is more complicated this, so see their page.
      - "Assembly Submitter" values: ["Vertebrate Genomes Project"] Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
    - Bat1K - https://genome10k.ucsc.edu/data-use-policies/
      - Website: https://bat1k.com/
      - Embargo: Same as the VGP embargo, specified in the 2018 VGP page.
      - "Assembly Submitter" values: ["Bat1K"] Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
    - Bird10K - https://genome10k.ucsc.edu/data-use-policies/
      - Website: https://b10k.genomics.cn/
      - Embargo: Same as the VGP embargo, specified in the 2018 page.
      - "Assembly Submitter" values: ["Bird10K"] Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
    - Kakapo projects - https://genome10k.ucsc.edu/data-use-policies/
      - Website: Unknown, December 3rd, 2024
      - Embargo: Same as the VGP embargo
      - "Assembly Submitter" values: None found, but the 2018 page specifies that there are Kakapo projects under the VGP umbrella
    - G10K project - https://genome10k.ucsc.edu/data-use-policies/
      - Website: https://genome10k.ucsc.edu/data-use-policies/
      - Embargo: Same as the VGP embargo
      - "Assembly Submitter" values: ["G10K", "Genome 10K"] Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
    - Global Invertebrate Genomics Alliance (GIGA)
      - Website: http://www.gigacos.org/
      - Embargo: No embargo specified on access date of Tuesday, December 3rd, 2024
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024
    - Earth BioGenome Project (EBP)
      - Website: https://www.earthbiogenome.org/
      - Embargo: No embargo specified on their website on access date of Tuesday, December 3rd, 2024. Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024
    - Paratus Sciences Bat Project
      - Website: https://paratussciences.com/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. No embargo specified on their website on access date of Tuesday, December 3rd, 2024.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024
    - Cetaceans Genome Project
      - Website: https://www.fisheries.noaa.gov/international/science-data/cetacean-genomes-project
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. Also says they are affiliated with the DToL project on their page as of Tuesday, December 3rd, 2024. VGP and DToL have inherently different embargo policies, so it is not clear what this falls under.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Darwin Tree of Life (DToL)
      - Website: https://www.darwintreeoflife.org/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. However, DToL has a strictly non-embargo policy.
      - "Assembly Submitter" values: ["Wellcome Sanger Institute", "Wellcome Trust Sanger Institute"]
    - European Reference Genome Atlas (ERGA)
      - Website: https://www.erga-biodiversity.eu/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. Lets each project decide their own embargo policy: https://www.nature.com/articles/s44185-024-00054-6
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Catalan Initiative for the Earth Biogenome Project (CBP)
      - Website: https://www.biogenoma.cat/en/home/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. No embargo specified on their website on access date of Tuesday, December 3rd, 2024.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - African BioGenomes Project (AfricaBP)
      - Website: https://africanbiogenome.org/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. No embargo specified on their website on access date of Tuesday, December 3rd, 2024.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Minderoo Foundation: Australia and New Zealand Aquatic Vertebrates
      - Website: There is no website for this project as of Tuesday, December 3rd, 2024.
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. There is not website to even check the embargo
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - AmaZOOmics: Brazilian Biodiversity
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - California Conservation Genomes Project
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Earth BioGenome Project - Columbia
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Canadian Biogenome Project
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Revive & Restore
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Colossal BioSciences
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values:  None found on access date of Tuesday, December 3rd, 2024.
    - Sanger 25 Genomes Project
      - Website: https://www.sanger.ac.uk/collaboration/25-genomes-for-25-years/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. Note - this is a different project than the DToL project, so needs special parsing.
      - "Assembly Submitter" values: ["Wellcome Sanger Institute", "Wellcome Trust Sanger Institute"]
      - NCBI BioProject: PRJEB33226
      - Note: The Sanger 25 Genomes Project is a separate project from the DToL project.
              The Sanger 25 genomes project is under the umbrella of the VGP project and the VGP embargo.
              For this reason, genomes from Wellcome Sanger and Wellcome Trust Sanger Institute
              need to be specifically filtered out for the Sanger 25 genomes project.
              There is a file in `assembly_specifications/Sanger_25_genomes_project_genomes.txt` that has a list of assemblies
              to check for the embargo date.
      - List of umbrella project genomes:
         - PRJEB33202  Aquila chrysaetos chrysaetos	Aquila chrysaetos chrysaetos (European golden eagle) (Wellcome Sanger Institute)
         - PRJEB39551  Arvicola amphibius	Arvicola amphibius (European water vole) (Wellcome Sanger Institute)
         - PRJEB33975  Asterias rubens	Asterias rubens (common starfish) (Wellcome Sanger Institute)
         - PRJEB44423  Brachyptera putata	Brachyptera putata (Northern February red stonefly) (Wellcome Sanger Institute)
         - PRJEB44431  Dolomedes plantarius	Dolomedes plantarius (fen raft spider) (Wellcome Sanger Institute)
         - PRJEB38659  Erithacus rubecula	Erithacus rubecula (European robin) (Wellcome Sanger Institute)
         - PRJEB44426  Hemaris fuciformis	Hemaris fuciformis (broad-bordered bee hawk-moth) (Wellcome Sanger Institute)
         - PRJEB44452  Impatiens glandulifera	Impatiens glandulifera (Indian balsam) (WELLCOME SANGER INSTITUTE)
         - PRJEB35340  Lutra lutra	Lutra lutra (Eurasian otter) (Wellcome Sanger Institute)
         - PRJEB36757  Maniola hyperantus	Aphantopus hyperantus (ringlet butterfly) (Wellcome Sanger Institute)
         - PRJEB44457  Osmia bicornis	Osmia bicornis (red mason bee) (WELLCOME SANGER INSTITUTE)
         - PRJEB35331  Pecten maximus	Pecten maximus (king scallop) (Wellcome Sanger Institute)
         - PRJEB39566  Pipistrellus pipistrellus	Pipistrellus pipistrellus (common pipistrelle) (Wellcome Sanger Institute)
         - PRJEB33201  Salmo trutta	Salmo trutta (brown trout) (Wellcome Sanger Institute)
         - PRJEB35387  Sciurus carolinensis	Sciurus carolinensis (grey squirrel) (Wellcome Sanger Institute)
         - PRJEB35381  Sciurus vulgaris	Sciurus vulgaris (red squirrel) (Wellcome Sanger Institute)
         - PRJEB35946  Scyliorhinus canicula	Scyliorhinus canicula (smaller spotted catshark) (Wellcome Sanger Institute)
         - PRJEB46113  Senecio squalidus	Senecio squalidus (Oxford ragwort) (Wellcome Sanger Institute)
         - PRJEB32727  Streptopelia turtur	Streptopelia turtur (European turtle dove) (Wellcome Sanger Institute)
         - PRJEB46981  Vespa velutina	Vespa velutina (Asian hornet) (WELLCOME SANGER INSTITUTE)
    - Telomere-To-Telomere Consortium
      - Website: https://sites.google.com/ucsc.edu/t2tworkinggroup
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. Use the VGP embargo policy.
      - "Assembly Submitter" values: ["Telomere-to-Telomere Consortium"]
    - Human Pangenome Project
      - Website: https://humanpangenome.org/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. Use the VGP embargo policy.
      - "Assembly Submitter" values: ["Human Pangenome Reference Consortium"]
    - Allen Institute for Brain Science
      - Website: https://alleninstitute.org/division/brain-science/ is the closest, but nothing specifically for genomics.
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. None found on their website on access date of Tuesday, December 3rd, 2024.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Chan-Zuckerberg Initiative
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - Tabula Madagascar
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - HHMI COVID-19 project
      - Website:
      - Embargo:  Says they are affiliated with the VGP on the 2024 page.
      - "Assembly Submitter" values: None found on access date of Tuesday, December 3rd, 2024.
    - strings to match for VGP embargo are:
        ["Vertebrate Genomes Project", # Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
         "Bat1K",                      # Seen in the Assembly Submitter column on Tuesday December 3rd, 2024
         "Bird10K",                    # Not seen, but putting it here for good measure
         "Human Pangenome Reference Consortium", # Seen in the Assembly Submitter column on Tuesday December 3rd, 2024.
         "Kakapo",                     # Not seen, but the 2018 page specifies that there are Kakapo projects under the VGP umbrella
         "G10K",                       # Seen in the Assembly Submitter column on Tuesday December 3rd, 2024.
         "Genome 10K",                 # Seen in the Assembly Submitter column on Tuesday December 3rd, 2024.
         "Telomere-to-Telomere Consortium"]
    """
    VGP_policy_submitters = ["Bat1K",
                             "Bird10K",
                             "Human Pangenome Reference Consortium",
                             "G10K",
                             "Genome 10K",
                             "Telomere-to-Telomere Consortium",
                             "Vertebrate Genomes Project"]
    VGP_policy_submitters += [x.lower() for x in VGP_policy_submitters]

    # Iterate through all of the rows in the dataframe to determine the outcome assembly-by-assembly.
    # Not efficient, but good for this sort of thing.
    counter = 0
    for index, row in df.iterrows():
        if row["Assembly Submitter"] in VGP_policy_submitters:
            #print("- Looking at a genome submitted by {}".format(row["Assembly Submitter"]))
            # This is part of the VGP project, so we need to annotate it.
            _row_helper_VPG(df, index, row)
    return df

def _annotate_embargo_status_WellcomeSangerInstitute(df):
    """
    Helper function called by annotate_embargo_status.
    Only used to annotate the rows with genomes submitted by the The Wellcome Sanger Institute,
      previously known as The Sanger Centre and Wellcome Trust Sanger Institute.

    Takes in a pandas dataframe and annotates the rows with the embargo status based on Wellcome Sanger Institute policies.
    The ingested dataframe should already contain the columns we need to annotate.
    Returns the pandas dataframe with the embargo status annotated.

    The columns this function modifies are:
      - "Embargo"
      - "EmbargoPolicy"
      - "EmbargoPolicyLink"
      - "EmbargoReason"
      - "EmbargoLiftPublication"
      - "EmbargoLiftPublicationPMID"
      - "EmbargoLiftPublicationDOI"
      - "EmbargoLiftDate"

    Case for the following organizations, specified on the two websites:
    - Darwin Tree of Life project
      - Website: https://www.darwintreeoflife.org/
      - Embargo: DToL data are released freely for reuse for any purpose upon deposition in ENA, and the DToL
                 partners encourage such community reuse. Our intention is to rapidly publish all submitted
                 assemblies as Wellcome Open Research notes, which can be cited (see, for example, Boyes et
                 al. (2024) The genome sequence of the Figure of Eighty moth Tethea ocularis Linnaeus, 1767
                 https://wellcomeopenresearch.org/articles/9-348), and we expect that users of the data will
                 give appropriate acknowledgement and citation.
      - Embargo Website: https://www.darwintreeoflife.org/wp-content/uploads/2024/10/DToL-Open-Data-Release-Policy.docx_.pdf
      - Embargo Access Date: Thursday, December 5th, 2024
      - "Assembly Submitter" values: ["Wellcome Sanger Institute", "Wellcome Trust Sanger Institute"] seen in the Assembly Submitter column on Thursday December 5th, 2024
    - Aquatic Symbiosis Genomics Project
      - Website: https://www.sanger.ac.uk/collaboration/aquatic-symbiosis-genomics-project/
      - Embargo: The Sanger Institute project team encourages community reuse, and project data will be released freely for reuse for any purpose upon deposition in ENA.
                 Our intention is to rapidly publish all submitted assemblies as Wellcome Open Research notes, which can be cited (see, for example, Daniel Mead, Kathryn
                 Fingland, Rachel Cripps et al. [2020]. The genome sequence of the Eurasian red squirrel, Sciurus vulgaris Linnaeus 1758. Wellcome Open Research.
                 DOI: 10.12688/wellcomeopenres.15679.1). We scientists who use the genome sequence data give appropriate acknowledgement and citation in their own publications.
      - Embargo Website: https://www.sanger.ac.uk/collaboration/aquatic-symbiosis-genomics-project/
      - Embargo Access Date: Thursday, December 5th, 2024
      - "Assembly Submitter" values: ["Wellcome Sanger Institute", "Wellcome Trust Sanger Institute"]
    - Sanger 25 Genomes Project
      - Website: https://www.sanger.ac.uk/collaboration/25-genomes-for-25-years/
      - Embargo:  Says they are affiliated with the VGP on the 2024 page. On their NCBI page it also says that this is affiliated with DToL.
                  The most conservative embargo option is to apply the VGP 2-year embargo to this scenario.
                  Note - this is a different project than the DToL project, so needs special parsing.
      - Embargo Website: https://www.sanger.ac.uk/collaboration/25-genomes-for-25-years/
      - Embargo Access Date: Thursday, December 5th, 2024
      - "Assembly Submitter" values: ["Wellcome Sanger Institute", "Wellcome Trust Sanger Institute"]
      - NCBI BioProject: PRJEB33226
      - Note: The Sanger 25 Genomes Project is a separate project from the DToL project.
              The Sanger 25 genomes project is under the umbrella of the VGP project and the VGP embargo.
              For this reason, genomes from Wellcome Sanger and Wellcome Trust Sanger Institute
              need to be specifically filtered out for the Sanger 25 genomes project.
              There is a file in `assembly_specifications/Sanger_25_genomes_project_genomes.txt` that has a list of assemblies
              to check for the embargo date.
      - List of umbrella project genomes:
         - PRJEB33202  Aquila chrysaetos chrysaetos	Aquila chrysaetos chrysaetos (European golden eagle) (Wellcome Sanger Institute)
         - PRJEB39551  Arvicola amphibius	Arvicola amphibius (European water vole) (Wellcome Sanger Institute)
         - PRJEB33975  Asterias rubens	Asterias rubens (common starfish) (Wellcome Sanger Institute)
         - PRJEB44423  Brachyptera putata	Brachyptera putata (Northern February red stonefly) (Wellcome Sanger Institute)
         - PRJEB44431  Dolomedes plantarius	Dolomedes plantarius (fen raft spider) (Wellcome Sanger Institute)
         - PRJEB38659  Erithacus rubecula	Erithacus rubecula (European robin) (Wellcome Sanger Institute)
         - PRJEB44426  Hemaris fuciformis	Hemaris fuciformis (broad-bordered bee hawk-moth) (Wellcome Sanger Institute)
         - PRJEB44452  Impatiens glandulifera	Impatiens glandulifera (Indian balsam) (WELLCOME SANGER INSTITUTE)
         - PRJEB35340  Lutra lutra	Lutra lutra (Eurasian otter) (Wellcome Sanger Institute)
         - PRJEB36757  Maniola hyperantus	Aphantopus hyperantus (ringlet butterfly) (Wellcome Sanger Institute)
         - PRJEB44457  Osmia bicornis	Osmia bicornis (red mason bee) (WELLCOME SANGER INSTITUTE)
         - PRJEB35331  Pecten maximus	Pecten maximus (king scallop) (Wellcome Sanger Institute)
         - PRJEB39566  Pipistrellus pipistrellus	Pipistrellus pipistrellus (common pipistrelle) (Wellcome Sanger Institute)
         - PRJEB33201  Salmo trutta	Salmo trutta (brown trout) (Wellcome Sanger Institute)
         - PRJEB35387  Sciurus carolinensis	Sciurus carolinensis (grey squirrel) (Wellcome Sanger Institute)
         - PRJEB35381  Sciurus vulgaris	Sciurus vulgaris (red squirrel) (Wellcome Sanger Institute)
         - PRJEB35946  Scyliorhinus canicula	Scyliorhinus canicula (smaller spotted catshark) (Wellcome Sanger Institute)
         - PRJEB46113  Senecio squalidus	Senecio squalidus (Oxford ragwort) (Wellcome Sanger Institute)
         - PRJEB32727  Streptopelia turtur	Streptopelia turtur (European turtle dove) (Wellcome Sanger Institute)
         - PRJEB46981  Vespa velutina	Vespa velutina (Asian hornet) (WELLCOME SANGER INSTITUTE)
      - These bioprojejcts above are not used on NCBI, so we need to compare actual assembly numbers.
        These files are located in the `assembly_specifications/Sanger_25_genomes.tsv` file.
    """
    Well_policy_submitters = ["Wellcome Sanger Institute",
                              "WELLCOME SANGER INSTITUTE",
                              "Wellcome Trust Sanger Institute"]
    Well_policy_submitters += [x.lower() for x in Well_policy_submitters]

    #load the list of genomes that are part of the Sanger 25 Genomes Project
    # the filepath is the runpath of the script + the filename
    filepath =  os.path.join(os.path.dirname(os.path.realpath(__file__)), "assembly_specifications/Sanger_25_genomes.tsv")
    sanger25df = pd.read_csv(filepath, sep = "\t")
    # get the assembly accession without the version number
    sanger25df["assembly_stripped"] = sanger25df["Assembly Accession"].apply(lambda x: x.split(".")[0])
    sanger25df_unique = list(sorted(sanger25df["assembly_stripped"].unique()))

    # Iterate through all of the rows in the dataframe to determine the outcome assembly-by-assembly.
    # Not efficient, but good for this sort of thing.
    counter = 0
    for index, row in df.iterrows():
        if row["Assembly Submitter"] in Well_policy_submitters:
            # first get the genomes that are part of the Sanger 25 Genomes Project
            thisassembly = row["Assembly Accession"].split(".")[0]
            #print("- Looking at a genome submitted by {}, accession {}".format(row["Assembly Submitter"], thisassembly))
            # check if the Assembly Accession is in the Sanger 25 Genomes Project. Just get the base number.
            if thisassembly in sanger25df_unique:
                # This genome is part of the Sanger 25 Genomes Project, so we need to annotate its embargo status with the VGP embargo policy.
                _row_helper_VPG(df, index, row)
                # Diagnostic print
                #df.at[index, "EmbargoReason"] = "This genome is part of the Sanger 25 Genomes Project. " + df.at[index, "EmbargoReason"]
                #for column in df.columns:
                #    if "Embargo" in column:
                #        print("{}: {}".format(column, df.at[index, column]))
            else:
                # Otherwise, this falls under the DToL open data use policy.
                _row_helper_DToL(df, index, row)
                # Diagnostic print
                #for column in df.columns:
                #    if "Embargo" in column:
                #        print("{}: {}".format(column, df.at[index, column]))
    return df

def _annotate_embargo_status_Unknown(df):
    """
    Helper function called by annotate_embargo_status.
      This function adds some information to the rows that have an unknown embargo status.

    Takes in a pandas dataframe and annotates the rows with the embargo status "Unknown".
    The ingested dataframe should already contain the columns we need to annotate.
    Returns the pandas dataframe with the embargo status annotated.
    """
    # Iterate through all of the rows in the dataframe to determine the outcome assembly-by-assembly.
    # Not efficient, but good for this sort of thing.
    counter = 0
    for index, row in df.iterrows():
        if (row["Embargo"] == "Unknown") and (row["EmbargoPolicy"] == "Unknown"):
            comment_text = str(row["Assembly BioSample Description Comment"]).lower()
            if "embargo" not in comment_text:
                df.at[index, "Embargo"]           = "Not Embargoed"
                df.at[index, "EmbargoPolicy"]     = "Darwin Tree of Life Open Data Release Policy v1.04"
                df.at[index, "EmbargoPolicyLink"] = "https://www.darwintreeoflife.org/wp-content/uploads/2024/10/DToL-Open-Data-Release-Policy.docx_.pdf"
                df.at[index, "EmbargoReason"]     = "We are not aware of an embargo policy for this genome, and there is no embargo policy specified in the \"Assembly BioSample Description Comment\" field."
                df.at[index, "EmbargoLiftDate"]   = row["Assembly Release Date"].strftime("%Y-%m-%d")
                days_until = row["Assembly Release Date"] - pd.Timestamp.today()
                df.at[index, "EmbargoDaysUntil"]  = days_until.days
            else:
                raise IOError("We should have caught all of the genomes that are not embargoed by now, but there was message about an embargo in the \"Assembly BioSample Description Comment\" field for assembly {}".format(row["Assembly Accession"]))
    return df

def annotate_embargo_status(df) -> pd.DataFrame:
    """
    This function will annotate the dataframe with the embargo status of the genomes.

    The relevant fields to fill out are the following:
    - Embargo
      - This field will be set to "Embargoed" if the genome is under embargo, and "Not Embargoed" if it is not.
    - EmbargoReason
      - This field will be set to a string that explains why the genome is under embargo.
    - EmbargoLiftPublication
      - This field will be set to the publication that lifted the embargo. Can be the whole publication string.
    - EmbargoLiftPublicationPMID
      - This field will be set to the PMID of the publication that lifted the embargo.
    - EmbargoLiftPublicationDOI
      - This field will be set to the DOI of the publication that lifted the embargo.
      - Just use the URL version of the DOI.
    - EmbargoLiftDate
      - This field will be set to the date that the embargo was lifted.
    - EmbargoDaysUntil
      - Positive number is the number of days until the embargo lift date, negative
        number is how many days after the embargo lift date.

    This function returns a pandas dataframe that has been annotated with the fields above.
    """
    # First, check that the type of the input is a pandas dataframe.
    if not isinstance(df, pd.DataFrame):
        raise TypeError("The input must be a pandas dataframe.")
    # Next, check that the indices of the dataframe are unique
    if not df.index.is_unique:
        raise IOError("There are conflicts in the indices of the spreadsheet, try resetting the indices of the input DataFrame.")
    # Next, check that the dataframe has the necessary embargo columns.
    # If it doesn't have any of these columns, add them.
    col_default_pair = {"Embargo"                    : "Unknown",
                        "EmbargoPolicy"              : "Unknown",
                        "EmbargoPolicyLink"          : "Unknown",
                        "EmbargoReason"              : "No explanation assigned.",
                        "EmbargoLiftPublication"     : "No publication assigned.",
                        "EmbargoLiftPublicationPMID" : "No PMID assigned.",
                        "EmbargoLiftPublicationDOI"  : "No DOI assigned.",
                        "EmbargoLiftDate"            : "No Assigned Date",
                        "EmbargoDaysUntil"           : 99999999}

    for thiscol in col_default_pair:
        if thiscol not in df.columns:
            df[thiscol] = col_default_pair[thiscol]
    # Each submitter has a different embargo, so we need to process this individually.
    #  - Note, this is only for chromosome-scale genome assemblies. These organizations may have contributed non-chromosomal assemblies and we therefore may have missed some "Assembly Submitte" values.

    # First, process the VGP embargo
    # I could probably just do these by reference later.
    df = _annotate_embargo_status_VGP(df)
    print("We're done checking which VGP genomes are embargoed.")
    # Next, process the Wellcome Sanger Institute genomes
    df = _annotate_embargo_status_WellcomeSangerInstitute(df)
    print("We're done checking the embargoes of the Wellcome Sanger Institute.")
    # Next, process the genomes for which we have not yet found some annotation information.
    df = _annotate_embargo_status_Unknown(df)
    print("We're done checking the embargoes of the remaining genomes.")

    return df

def parse_args():
    """
    The args we need are:
      - tsvs of annotated and unannotated genomes
      - directory of rbh files
    """
    parser = argparse.ArgumentParser(description="Filter assemblies based on their embargo status.")
    parser.add_argument("-t", "-tsvs", nargs="+", help="List of csvs that contain the annotated and unannotated genomes.")
    parser.add_argument("-d", "-rbh_directory", help="Directory of the rbh files.")
    args = parser.parse_args()
    print(args)

    # check that the tsvs exist
    for tsv in args.t:
        if not os.path.exists(tsv):
            raise IOError("The file {} does not exist.".format(tsv))
    # check that the directory exists
    if not os.path.exists(args.d):
        raise IOError("The directory {} does not exist.".format(args.rbh_directory))

    return args

def main():
    args = parse_args()
    list_of_NCBI_csvs = args.t
    directory_of_rbh_files = args.d
    #list_of_NCBI_csvs = ["/lisc/scratch/molevo/dts/ODP_genomes/GenDB_scraper/odp_ncbi_genome_scraper/output/annotated_genomes_chr_202312301553.tsv",
    #                     "/lisc/scratch/molevo/dts/ODP_genomes/GenDB_scraper/odp_ncbi_genome_scraper/output/unannotated_genomes_chr_202312301553.tsv"]
    #directory_of_rbh_files = "/lisc/scratch/molevo/dts/manifold/BCnSSimakov2022_current_rbh/"

    # (1) First load the directory of existing files
    rbhlist = [x for x in os.listdir(directory_of_rbh_files) if x.endswith(".rbh")]
    # Next we make a dictionary that stores information about each accession.
    #  This information will be saved and printed later.
    accession_dict = {x.split("_")[1].split("-")[2]:
                      {"filepath" : os.path.join(directory_of_rbh_files, x),
                       "filename" : x,
                       "ALGname"  : x.split("_")[0],
                       "binomial" : x.split("_")[1].split("-")[0],
                       "ncbitaxid": x.split("_")[1].split("-")[1],
                       "accession": x.split("_")[1].split("-")[2]}
                      for x in rbhlist}
    counter = 0
    for key in accession_dict:
        print(key, accession_dict[key])
        counter += 1
        if counter == 5:
            break

    # (2) Load a csv of annotated and unannotated genomes.
    list_of_dfs = [pd.read_csv(x, sep = "\t")
                   for x in list_of_NCBI_csvs]
    # concatenate these into one dataframe
    df = pd.concat(list_of_dfs)
    df = df.reset_index(drop = True)
    # We need to change the dates to datetime objects work with dates later.
    df["Assembly Release Date"]   = pd.to_datetime(df["Assembly Release Date"],    errors="coerce")
    df["Annotation Release Date"] = pd.to_datetime(df["Annotation Release Date"],  errors="coerce")
    # We should also add these columns to the dataframe.
    # Days until the embargo is lifted is initialized as an unrealistically large number
    df["Embargo"]                    = "Unknown"
    df["EmbargoPolicy"]              = "Unknown"
    df["EmbargoPolicyLink"]          = "Unknown"
    df["EmbargoReason"]              = "No explanation assigned."
    df["EmbargoLiftPublication"]     = "No publication assigned."
    df["EmbargoLiftPublicationPMID"] = "No PMID assigned."
    df["EmbargoLiftPublicationDOI"]  = "No DOI assigned."
    df["EmbargoLiftDate"]            = "No Assigned Date"
    df["EmbargoDaysUntil"]           = 99999999

    # Annotate the embargo status of the genomes in the spreadsheet.
    # This calls many helper functions that annotate the genomes based on the submitter.
    df = annotate_embargo_status(df)
    print(df)

    # this code prints out the unique genome submitters
    for entry in sorted([str(x) for x in df["Assembly Submitter"].unique().tolist()]):
        print(entry)

    # (3) Find the files that do not have an accession in the dataframe.
    files_missing_in_tsv = set()
    files_embargoed      = set()
    files_not_embargoed  = set()
    for key in accession_dict:
        if key not in df["Assembly Accession"].tolist():
            files_missing_in_tsv.add(key)

    if len(files_missing_in_tsv) > 0:
        print("There are {} files that are missing in the TSV.".format(len(files_missing_in_tsv)))
        #print("The following files are missing in the TSV:")
        #for key in files_missing_in_tsv:
        #    print(key, accession_dict[key])
    # 1 - 
    # 2
    # 3
    # 4
    # 5
    # 6 - write the files

if __name__ == "__main__":
    main()

