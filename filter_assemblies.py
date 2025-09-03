#!/usr/bin/env python

"""
The point of this is to filter a directory of pregenerated rbh files to remove those that may be under embargo

# If the user does not supply a directory containing rbh files
(1) Load a csv of annotated and unannotated genomes.
(2) Identify accessions that are possibly under embargo still
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
(3) Add publication information for each assembly, update the embargo information if they were released through publication.
(4) Write the files:
  - Make a spreadsheet with the genome assemblies, the embargo status, and a description of why it is or is not under embargo.

# If the user supplies a directory containing rbh files to look through
(1) First load the directory of existing files
(2) Load a csv of annotated and unannotated genomes.
(3) Find the files that do not have an accession in the dataframe of assemblies.
     Print these out for the user and make them type something
     to continue or not.
(4) Identify accessions that are possibly under embargo still
  - Same steps as above
(5) Add publication information for each assembly, update the embargo information if they were released through publication.
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
import shutil
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

def _row_helper_VPG(df, index, row, conservative = False):
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
        if conservative == True:
            # We multiply the offset time by 2 to get the maximum possible embargo date, under the assumption that we have possibly missed the annotation.
            # We could get more genomes if we knew the date on which this spreadsheet was generated, but to avoid overcomplicating this, we will just use the maximum possible embargo date.
            timestamp = row["Assembly Release Date"] + pd.DateOffset(years = offset_time*2)
            embargo_reason_message += " This embargo date has been conservatively estimated to be {} year(s) after the assembly upload date, on the chance that this report was generated before the annotation was released within the embargo lapse window.".format(offset_time*2)
        else:
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

def _annotate_embargo_status_VGP(df, conservative = False) -> pd.DataFrame:
    """
    Helper function called by annotate_embargo_status. Only used to annotate the rows with VGP genomes.

    Takes in a pandas dataframe and annotates the rows with the VGP embargo status.
    The ingested dataframe should already contain the columns we need to annotate.
    Returns the pandas dataframe with the VGP embargo status annotated.

    The conservative option is used to apply conservative options to specific projects.
      - VGP - the conservative flag applies the maxium possible embargo date (2 years for post-May 1st, 2024 genomes, 4 years for pre-May 1st, 2024 genomes)
        for unannotated genomes. This is to avoid the case in which the spreadsheet is not updated with the annotation release date.

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
    - Leibniz Institute for Zoo and Wildlife Research
      - Website:
      - Embargo: There is an elephant sequencing project that has the VGP embargo.
      - "Assembly Submitter" values: 1 elephant genome submitted on August 11th, 2025.
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
         "Telomere-to-Telomere Consortium",
         "Leibniz Institute for Zoo and Wildlife Research"]
    """
    VGP_policy_submitters = ["Bat1K",
                             "Bird10K",
                             "Human Pangenome Reference Consortium",
                             "G10K",
                             "Genome 10K",
                             "Leibniz Institute for Zoo and Wildlife Research",
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
            _row_helper_VPG(df, index, row, conservative = conservative)
    return df

def _annotate_embargo_status_DNAZoo(df) -> pd.DataFrame:
    """
    Helper function called by annotate_embargo_status.
    Only used to annotate the rows with the DNA Zoo as the assembly submitter.

    As of December 10th, 2024, there were 55 chromosome-scale genome assemblies
      available on NCBI from DNA Zoo. Genomes are submitted under the name "DNA Zoo".

    Takes in a pandas dataframe and annotates the rows with the DNA Zoo embargo status.
    Returns the pandas dataframe with the DNA Zoo embargo status annotated.

    The embargo information for DNA Zoo was collected on December 10th, 2024.
    The policy website is here: https://www.dnazoo.org/usage
    The policy is also saved in the file embargo_policies/DNAzoo_20241210.pdf
    Their policy states that, "All DNA Zoo data, including genome assemblies, genome annotations,
    DNA-Seq data, and Hi-C maps, are shared freely without any restriction."

    They request that users cite this specific paper if the individual genome assembly does not have
      an annotation.
      The paper: Dudchenko, Olga, Sanjit S. Batra, Arina D. Omer, Sarah K. Nyquist, Marie Hoeger,
                 Neva C. Durand, Muhammad S. Shamim, et al. 2017. "De Novo Assembly of the Aedes
                 Aegypti Genome Using Hi-C Yields Chromosome-Length Scaffolds." Science
                 (New York, N.Y.) 356 (6333): 92-95. https://doi.org/10.1126/science.aal3327.
      PMID: 28336562
    """
    # check that all of the columns are in the dataframe
    _required_column_check(df)

    DNAzoo_submitters = ["DNA Zoo"]
    DNAzoo_submitters += [x.lower() for x in DNAzoo_submitters]

    # Iterate through all of the rows in the dataframe to determine the outcome assembly-by-assembly.
    # Not efficient, but good for this sort of thing.
    counter = 0
    for index, row in df.iterrows():
        if row["Assembly Submitter"] in DNAzoo_submitters:
            days_until = int((row["Assembly Release Date"] - pd.Timestamp.today()).days)
            df.at[index, "Embargo"]                    = "Not Embargoed"
            df.at[index, "EmbargoPolicy"]              = "DNA Zoo Open Data Release Policy"
            df.at[index, "EmbargoPolicyLink"]          = "https://www.dnazoo.org/usage"
            # Add the Open Data Release embargo information.
            embargo_message = ""
            embargo_message =  "This genome falls under the DNA Zoo data use policy."
            embargo_message += " The policy text states, \"All DNA Zoo data, including genome assemblies, genome annotations, DNA-Seq data, and Hi-C maps, are shared freely without any restriction.\""
            embargo_message += " This assembly's 'Assembly Release Date' on NCBI/ENA is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))
            embargo_message += " Therefore, the genome has not been under an embargo since its publication date,"
            embargo_message += " {} years and {} days ago".format(-1 * days_until//365, -1 * days_until%365)
            embargo_message += " since this report was generated on {}.".format(pd.Timestamp.today().strftime("%Y-%m-%d"))
            embargo_message += " The authors request that publications using these genomes at least cite the article, Dudchenko et al. (2017) https://doi.org/10.1126/science.aal3327 ."
            df.at[index, "EmbargoReason"]              = embargo_message
            df.at[index, "EmbargoLiftPublication"]     = "Dudchenko, Batra, Omer,  et al. 2017. De Novo Assembly of the Aedes Aegypti Genome Using Hi-C Yields Chromosome-Length Scaffolds. Science (New York, N.Y.) 356 (6333): 92-95."
            df.at[index, "EmbargoLiftPublicationPMID"] = "28336562"
            df.at[index, "EmbargoLiftPublicationDOI"]  = "https://doi.org/10.1126/science.aal3327"
            df.at[index, "EmbargoLiftDate"]            = row["Assembly Release Date"].strftime("%Y-%m-%d")
            df.at[index, "EmbargoDaysUntil"]           = days_until
    return df

def _annotate_embargo_status_WellcomeSangerInstitute(df, conservative = False) -> pd.DataFrame:
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
                _row_helper_VPG(df, index, row, conservative = conservative)
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

def _annotate_embargo_status_Unknown(df) -> pd.DataFrame:
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
                df.at[index, "EmbargoReason"]     = "We are not aware of an embargo policy for this genome, and there is no embargo policy specified in the \"Assembly BioSample Description Comment\" field."
                df.at[index, "EmbargoLiftDate"]   = row["Assembly Release Date"].strftime("%Y-%m-%d")
                days_until = row["Assembly Release Date"] - pd.Timestamp.today()
                df.at[index, "EmbargoDaysUntil"]  = days_until.days
            else:
                e_msg =  "We should have caught all of the genomes that are not embargoed by now, but there was message about an embargo "
                e_msg += "in the \"Assembly BioSample Description Comment\" field for assembly {}. ".format(row["Assembly Accession"])
                e_msg += "The submitter of this assembly is {}.".format(row["Assembly Submitter"])
                raise IOError(e_msg)
    return df

def _annotate_embargo_status_embargoString(df):
    """
    Helper function called by annotate_embargo_status.
      This function adds some information to the rows that have the string "embargo"
      in the "Assembly BioSample Description Comment" field. Specifically, this function then marks them
      as embargoed, and changes the embargo status to "Embargoed".
    """
    # Iterate through all of the rows in the dataframe to determine the outcome assembly-by-assembly.
    # Not efficient, but good for this sort of thing.
    counter = 0
    for index, row in df.iterrows():
        comment_text = str(row["Assembly BioSample Description Comment"]).lower()
        if "embargo" in comment_text:
            if row["Embargo"] == "Embargoed":
                t = row["EmbargoReason"]
                t += " The assembly has the string \"embargo\" in the \"Assembly BioSample Description Comment\" field."
                t += " This is consistent with the embargo status of the genome."
                df.at[index, "EmbargoReason"]     = t
            elif row["Embargo"] == "Not Embargoed":
                df.at[index, "Embargo"] = "Embargo Ambiguous"
                t = row["EmbargoReason"]
                t += " On the other hand, there is a string \"embargo\" in the \"Assembly BioSample Description Comment\" field."
                t += " Please check that field to clarify why the word \"embargo\" is still present."
                t += " It is possible that this string should it have been removed,"
                t += " or that the intention is to extend the embargo past the policy data for this specific accession."
                df.at[index, "EmbargoReason"]     = t
            else:
                raise IOError("The embargo status should not be unknown at this point.")

    return df

def annotate_embargo_status(df, conservative = False) -> pd.DataFrame:
    """
    This function will annotate the dataframe with the embargo status of the genomes.

    The conservative option is used to apply conservative options to specific projects.
      - VGP - the conservative flag applies the maxium possible embargo date (2 years for post-May 1st, 2024 genomes, 4 years for pre-May 1st, 2024 genomes)
        for unannotated genomes. This is to avoid the case in which the spreadsheet is not updated with the annotation release date.

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
    df = _annotate_embargo_status_VGP(df, conservative = conservative)
    print("We're done checking which VGP genomes are embargoed.")
    # Next, process the Wellcome Sanger Institute genomes
    df = _annotate_embargo_status_WellcomeSangerInstitute(df, conservative = conservative)
    print("We're done checking the embargoes of the Wellcome Sanger Institute.")
    # Next process DNA Zoo genomes. These specify a publication that they want to be cited.
    df = _annotate_embargo_status_DNAZoo(df)
    print("We're done checking the embargoes of the DNA Zoo.")
    # Next, process the genomes for which we have not yet found some annotation information.
    df = _annotate_embargo_status_Unknown(df)
    print("We're done checking the embargoes of the remaining genomes.")

    # Lastly, in the conservative case, identify which of these genomes have the string "embargo"
    #  in the "Assembly BioSample Description Comment" field.
    if conservative == True:
        df = _annotate_embargo_status_embargoString(df)

    return df

def generate_report(output_filepath, df, files_not_in_spreadsheet=None, accession_dict=None):
    """Generate a text report summarising genome embargo information.

    When a directory of rbh files is not supplied the ``files_not_in_spreadsheet``
    and ``accession_dict`` parameters can be ``None`` or empty.  In that case the
    report omits any statistics about the rbh directory.
    """
    # Allow the caller to omit rbh information
    if files_not_in_spreadsheet is None:
        files_not_in_spreadsheet = set()
    if accession_dict is None:
        accession_dict = {}

    # Check to make sure that the output directory exists.
    output_directory = os.path.dirname(output_filepath)
    if not os.path.exists(output_directory):
        raise IOError("The output directory {} does not exist.".format(output_directory))
    #if os.path.exists(output_filepath):
    #    raise IOError("The output file {} already exists.".format(output_filepath))

    today_string = pd.Timestamp.today().strftime("%Y-%m-%d")

    # number of genomes in the spreadsheet
    num_genomes_spreadsheet = len(df)
    # number of genomes in the directory (0 if no directory provided)
    num_genomes_directory = len(accession_dict)
    # number of genomes in the directory but not in the spreadsheet
    num_genomes_not_in_spreadsheet = len(files_not_in_spreadsheet)
    # number of genomes in the spreadsheet but not in the directory
    num_genomes_not_in_directory = (
        len([x for x in df["Assembly Accession"] if x not in accession_dict])
        if accession_dict else 0
    )
    # number of genomes that are embargoed
    num_genomes_embargoed = len(df[df["Embargo"] == "Embargoed"])
    # Number of vertebrate genomes that are embargoed. Look for ;7742; in the lineage to determine if it is a vertebrate.
    num_genomes_embargoed_vertebrate = len(df[(df["Embargo"] == "Embargoed") & (df["Lineage"].str.contains(";7742;"))])
    # number of genomes that are not embargoed
    num_genomes_not_embargoed = len(df[df["Embargo"] == "Not Embargoed"])
    # Number of vertebrate genomes that are not embargoed. Look for ;7742; in the lineage to determine if it is a vertebrate.
    num_genomes_not_embargoed_vertebrate = len(df[(df["Embargo"] == "Not Embargoed") & (df["Lineage"].str.contains(";7742;"))])
    # number of non-embargoed genomes that have no policy specified. Use the "Embargo" column = "Unknown value"
    num_genomes_not_embargoed_unknown = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"] == "Unknown")])
    # number of non-embargoed genomes that have a policy explictly stating that they are not embargoed, like DToL. "Darwin Tree of Life" should be in the EmbargoPolicy column.
    num_genomes_not_embargoed_DToL = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"].str.contains("Darwin Tree of Life"))])
    # number of non-embargoed genomes that do have an embargo policy, but the date has passed (look for VGP in the string)
    num_genomes_not_embargoed_embargoed = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"].str.contains("VGP"))])

    # Get a df of just the vertebrates, then groupby and count by the embargo policy and whether it is embargoed
    vdf = df[df["Lineage"].str.contains(";7742;")]
    counts = vdf.groupby(["Embargo", "EmbargoPolicy"]).size().reset_index(name='counts')
    counts["PercentOfVertebrates"] = 100 * counts["counts"] / len(vdf)
    vdf_embargoPolicy_counts_percent = counts

    # make a df of the vertebrates, and sort it by the embargo policy and how many submitters are under each
    vdf2 = df[df["Lineage"].str.contains(";7742;")]
    counts2 = vdf2.groupby(["Embargo", "Assembly Submitter"]).size().reset_index(name='counts')
    counts2 = counts2.sort_values(by = ["Embargo", "counts"], ascending = [True, False])
    # get rid of every row where counts is fewer than 5
    counts2 = counts2[counts2["counts"] > 4]
    counts2["PercentOfVertebrates"] = 100 * counts2["counts"] / len(vdf2)
    vdf_embargoPolicy_submitter_counts_percent = counts2

    # make a similar df for all genomes, not just vertebrates
    counts_all = df.groupby(["Embargo", "Assembly Submitter"]).size().reset_index(name='counts')
    counts_all = counts_all.sort_values(by = ["Embargo", "counts"], ascending = [True, False])
    # get rid of every row where counts is fewer than 5
    counts_all = counts_all[counts_all["counts"] > 4]
    counts_all["PercentOfAllGenomes"] = 100 * counts_all["counts"] / len(df)


    # get a df of th
    # Total number of vertebrates in the dataset
    num_vertebrates = len(df[df["Lineage"].str.contains(";7742;")])
    # number of genomes that have the VGP policy and are vertebrates
    num_genomes_VGP_vertebrates = len(df[(df["EmbargoPolicy"].str.contains("Vertebrate Genomes Project")) & (df["Lineage"].str.contains(";7742;"))])
    # percent of vertebrate genomes that have VGP policy
    percent_genomes_VGP_vertebrates = 100 * num_genomes_VGP_vertebrates / num_vertebrates
    # number of vertebrate genomes that are DToL
    num_genomes_DToL_vertebrates = len(df[(df["EmbargoPolicy"].str.contains("Darwin Tree of Life")) & (df["Lineage"].str.contains(";7742;"))])
    # percent of vertebrate genomes that are DToL
    percent_genomes_DToL_vertebrates = 100 * num_genomes_DToL_vertebrates / num_vertebrates
    # number of DNA Zoo genomes that are also vertebrates
    num_genomes_DNAZoo_vertebrates = len(df[(df["EmbargoPolicy"].str.contains("DNA Zoo")) & (df["Lineage"].str.contains(";7742;"))])
    # percent of vertebrate genomes that are DNA Zoo.

    # number of embargoed vertebrates that are VGP
    num_embargoed_VGP_vertebrates = len(df[(df["Embargo"] == "Embargoed") & (df["EmbargoPolicy"].str.contains("Vertebrate Genomes Project")) & (df["Lineage"].str.contains(";7742;"))])
    # percent of all embargoed vertebrates that are VGP
    percent_embargoed_vertebrates_VGP = 100 * num_embargoed_VGP_vertebrates / num_genomes_embargoed_vertebrate
    # number of non-embargoed vertebrates that are VGP
    num_not_embargoed_VGP_vertebrates = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"].str.contains("Vertebrate Genomes Project")) & (df["Lineage"].str.contains(";7742;"))])
    # percent of all non-embargoed vertebrates that are VGP
    percent_not_embargoed_vertebrates_VGP = 100 * num_not_embargoed_VGP_vertebrates / num_genomes_not_embargoed_vertebrate

    # count the number of genomes of each policy type for the embargoed genomes
    policy_counts_embargoed     = df[df["Embargo"] == "Embargoed"]["EmbargoPolicy"].value_counts()
    # count the number of genomes of each policy type for the non-embargoed genomes
    policy_counts_not_embargoed = df[df["Embargo"] == "Not Embargoed"]["EmbargoPolicy"].value_counts()

    # count the number of genomes each submitter has in the spreadsheet for embargoed genomes
    submitter_counts_embargoed     = df[df["Embargo"] == "Embargoed"]["Assembly Submitter"].value_counts()
    # count the number of genomes each submitter has in the spreadsheet for non-embargoed genomes
    submitter_counts_not_embargoed = df[df["Embargo"] == "Not Embargoed"]["Assembly Submitter"].value_counts()

    # t is the output text that we will write to the file.
    t  =  "# Genome Embargo Report\n"
    t += "\n"
    t += "Program     : filter_assemblies.py\n"
    t += "Language    : python\n"
    t += "Report Date : {}\n".format(today_string)
    t += "Contact     : darrin.schultz@univie.ac.at\n"
    t += "Github      : TBD\n"
    t += "\n"
    t += "Description:\n"
    t += "  This report contains information about the embargo status of genomes.\n"
    t += "\n"
    t += "Summary:\n"
    t += "  - Number of genomes in the spreadsheet: {}\n".format(num_genomes_spreadsheet)
    if accession_dict:
        t += "  - Number of genomes in the directory: {}\n".format(num_genomes_directory)
        t += "  - Number of genomes in the directory but not in the spreadsheet: {}\n".format(num_genomes_not_in_spreadsheet)
        t += "  - Number of genomes in the spreadsheet but not in the directory: {}\n".format(num_genomes_not_in_directory)
    t += "  - Number of genomes that are embargoed: {}\n".format(num_genomes_embargoed)
    t += "    - # embargoed vertebrate (7742) genomes: {}\n".format(num_genomes_embargoed_vertebrate)
    t += "  - Number of genomes that are not embargoed: {}\n".format(num_genomes_not_embargoed)
    t += "    - # non-embargoed vertebrate (7742) genomes: {}\n".format(num_genomes_not_embargoed_vertebrate)
    t += "    - Number of genomes that are not embargoed, but have an unknown embargo policy: {}\n".format(num_genomes_not_embargoed_unknown)
    t += "    - Number of genomes that are not embargoed, but have an open (DToL) embargo policy: {}\n".format(num_genomes_not_embargoed_DToL)
    t += "    - Number of genomes that are not embargoed, but have an embargo policy that has passed: {}\n".format(num_genomes_not_embargoed_embargoed)
    t += "\n"
    t += "Assembly statistics on all genomes:\n"
    t += "\n"
    t += counts_all.to_string(index=False)
    t += "\n\n"
    t += "  - Total number of vertebrates in the dataset: {}\n".format(num_vertebrates)
    t += "\n"
    # print vdf_embargoPolicy_counts_percent without row numbers, and print sums at the bottom for columns counts, and PercentOfVertebrates
    t += vdf_embargoPolicy_counts_percent.to_string(index=False)
    t += "\n\n"
    # print vdf_embargoPolicy_submitter_counts_percent without row numbers, and print sums at the bottom for columns counts, and PercentOfVertebrates
    t += vdf_embargoPolicy_submitter_counts_percent.to_string(index=False)
    t += "\n\n"

    target_cols = ["Assembly Accession", "Assembly BioSample Description Comment", "Embargo",
                     "EmbargoPolicy", "EmbargoReason", "EmbargoLiftPublication",
                     "EmbargoLiftPublicationPMID", "EmbargoLiftPublicationDOI", "EmbargoLiftDate"]
    subdf = df[(df["Embargo"] == "Not Embargoed") & (df["Assembly BioSample Description Comment"].str.contains("embargo"))]
    if len(subdf) > 0:
        t += "The {} genomes that are listed as not embargoed, but have the string \"embargo\" in the \"Assembly BioSample Description Comment\" field, are shown below. ".format(len(subdf))
        t += " This likely means that the filter was run without the --conservative flag.\n"
        # Print each of these columns in markdown format.
        for index, row in subdf.iterrows():
            t += "  - {}\n".format(row["Assembly Accession"])
            for keycol in target_cols:
                t += "    - {}: {}\n".format(keycol, row[keycol])

    subdf = df[df["Embargo"] == "Embargo Ambiguous"]
    if len(subdf) > 0:
        t += "The {} genomes have the string \"embargo\" in the \"Assembly BioSample Description Comment\" field, are shown below.".format(len(subdf))
        t += " This likely means that the filter was run with the --conservative flag.\n"
        # Print each of these columns in markdown format.
        for index, row in subdf.iterrows():
            t += "  - {}\n".format(row["Assembly Accession"])
            for keycol in target_cols:
                t += "    - {}: {}\n".format(keycol, row[keycol])


    t += "\n\n"
    t += "The number of policies of the embargoed genomes:\n"
    for policy in policy_counts_embargoed.index:
        t += "  - {}: {}\n".format(policy, policy_counts_embargoed[policy])
    t += "\n"
    t += "The number of policies of the non-embargoed genomes:\n"
    for policy in policy_counts_not_embargoed.index:
        t += "  - {}: {}\n".format(policy, policy_counts_not_embargoed[policy])
    t += "\n"
    t += "The number of genomes each submitter has in the spreadsheet for the embargoed genomes:\n"
    for submitter in submitter_counts_embargoed.index:
        t += "  - {}: {}\n".format(submitter, submitter_counts_embargoed[submitter])
    t += "\n"
    t += "The number of genomes each submitter has in the spreadsheet for the non-embargoed genomes:\n"
    for submitter in submitter_counts_not_embargoed.index:
        t += "  - {}: {}\n".format(submitter, submitter_counts_not_embargoed[submitter])

    # Write the report to the file.
    with open(output_filepath, "w") as f:
        f.write(t)

def parse_args():
    """
    The args we need are:
      - tsvs of annotated and unannotated genomes
      - directory of rbh files
      - an output directory to put the results in
        - genomes_embargoed_rbh_files_YYYYMMDD/
        - genomes_notembargoed_rbh_files_YYYYMMDD/
        - genomes_not_in_spreadsheet_rbh_files_YYYYMMDD/
        - spreadsheet_genomes_all_YYYYMMDD.tsv
        - spreadsheet_genomes_embargoed_YYYYMMDD.tsv
        - spreadsheet_genomes_notembargoed_YYYYMMDD.tsv
      - A flag for conservative mode for VGP genomes
        - in this mode, the only VGP genomes allowed are those in which
          the assembly was submitted the max amount of time ago, allowing
          for the spreadsheed to be a bit outdated and lacking annotations.
      - A flag to not transfer the rbhfiles
    """
    parser = argparse.ArgumentParser(description="Filter assemblies based on their embargo status.")
    parser.add_argument("-t", "--tsvs",
                        nargs    = "+",
                        help     = "List of csvs that contain the annotated and unannotated genomes.")
    parser.add_argument("-c", "--conservative",
                        action   = "store_true",
                        required = False,
                        default  = False,
                        help     = "Conservative mode for VGP genomes. Allows for the possibility that the annotation was released after the spreadsheet date.")
    parser.add_argument("-p", "--prefix",
                        required = False,
                        default  = "spreadsheet_genomes",
                        help     = "Prefix for the output files.")
    # everything after this is related to saving the output files when the user has some input rbh files already downloaded.
    parser.add_argument("-r", "--rbh_directory",
                        required = False,
                        default  = None,
                        help     = "Directory of the rbh files.")
    # default is the present working directory
    pwd = os.getcwd()
    parser.add_argument("-d", "--output_directory",
                        default  = pwd,
                        required = False,
                        help     = "Directory to put the output files in.")
    parser.add_argument("-n", "--no_transfer",
                        action   = "store_true",
                        required = False,
                        default  = False,
                        help     = "Do not transfer the rbh files.")
    args = parser.parse_args()
    print(args)

    # check that the tsvs exist
    for tsv in args.tsvs:
        if not os.path.exists(tsv):
            raise IOError("The file {} does not exist.".format(tsv))
    if args.rbh_directory is not None:
        # check that the directory exists
        if not os.path.exists(args.rbh_directory):
            raise IOError("The directory {} does not exist.".format(args.rbh_directory))
    return args

def main():
    args = parse_args()
    list_of_ncbi_tsvs = args.tsvs
    directory_of_rbh_files = args.rbh_directory

    # If the user has provided a directory of rbh files, load information about
    # the files into ``accession_dict``; otherwise keep it empty so downstream
    # code can still run.
    accession_dict = {}
    if args.rbh_directory is not None:
        rbhlist = [x for x in os.listdir(directory_of_rbh_files) if x.endswith(".rbh")]
        accession_dict = {x.split("_")[1].split("-")[2]:
                          {"filepath" : os.path.join(directory_of_rbh_files, x),
                           "filename" : x,
                           "ALGname"  : x.split("_")[0],
                           "binomial" : x.split("_")[1].split("-")[0],
                           "ncbitaxid": x.split("_")[1].split("-")[1],
                           "accession": x.split("_")[1].split("-")[2]}
                          for x in rbhlist}

    # (2) Load a csv of annotated and unannotated genomes.
    list_of_dfs = [pd.read_csv(x, sep = "\t")
                   for x in list_of_ncbi_tsvs]
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

    ## this code prints out the unique genome submitters
    #for entry in sorted([str(x) for x in df["Assembly Submitter"].unique().tolist()]):
    #    print(entry)

    # Determine which genomes are missing from the spreadsheet when a directory
    # of rbh files is supplied.
    files_missing_in_tsv = set()
    if args.rbh_directory is not None:
        accession_list = [x.replace("_", "") for x in df["Assembly Accession"].tolist()]
        for key in accession_dict:
            thisacc = accession_dict[key]["accession"].strip("_")
            if thisacc.strip("_") not in accession_list:
                files_missing_in_tsv.add(key)

        if len(files_missing_in_tsv) > 0:
            print("There are {} files that are missing in the TSV.".format(len(files_missing_in_tsv)))
            print("  - They are:")
            for key in files_missing_in_tsv:
                print("    -", key, accession_dict[key]["filename"])

    # (4) Identify accessions that are possibly under embargo still
    #   This calls many helper functions that annotate the genomes based on the submitter.
    df = annotate_embargo_status(df, conservative = args.conservative)
    print(df)

    # (5) Add publication information for each assembly,
    #      update the embargo information if they were released through publication.
    # TODO

    # (6) Write the files:
    #  - genomes_embargoed_rbh_files_YYYYMMDD/
    #  - genomes_notembargoed_rbh_files_YYYYMMDD/
    #  - genomes_not_in_spreadsheet_rbh_files_YYYYMMDD/
    #  - spreadsheet_genomes_all_YYYYMMDD.tsv
    #  - spreadsheet_genomes_embargoed_YYYYMMDD.tsv
    #  - spreadsheet_genomes_notembargoed_YYYYMMDD.tsv
    #  - report_genomes_YYYYMMDD.txt

    datetoday     = pd.Timestamp.today().strftime("%Y%m%d")

    # First, check that the output directory exists
    if not os.path.exists(args.output_directory):
        os.makedirs(args.output_directory)
    if args.rbh_directory is not None:

        # Don't transfer files if the flag is set.
        if not args.no_transfer:
            # Next, make the subdirectories
            # - genomes_embargoed_rbh_files_YYYYMMDD/
            # - genomes_notembargoed_rbh_files_YYYYMMDD/
            # - genomes_not_in_spreadsheet_rbh_files_YYYYMMDD/
            embargodir    = os.path.join(args.output_directory, "genomes_embargoed_rbh_files_{}".format(datetoday))
            notembargodir = os.path.join(args.output_directory, "genomes_notembargoed_rbh_files_{}".format(datetoday))
            notintsvdir   = os.path.join(args.output_directory, "genomes_not_in_spreadsheet_rbh_files_{}".format(datetoday))
            for dirname in [embargodir, notembargodir, notintsvdir]:
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
            # Next, copy the rbh files to their respective directories
            counter = 0
            for key in accession_dict:
                # print a single-line progress message
                counter += 1
                # format the last field as 2 decimal places
                print("\r    Copying file {} of {} - {:.2f}%".format(
                    counter, len(accession_dict), 100*counter/len(accession_dict)), end = "")
                correct_accession = key
                # This is hacky and should be fixed later.
                if (key[0:3] == "GCA") or (key[0:3] == "GCF"):
                    if key[3] != "_":
                        correct_accession = key[:3] + "_" + key[3:]

                if key in files_missing_in_tsv:
                    shutil.copy(accession_dict[key]["filepath"], notintsvdir)
                else:
                    if correct_accession not in df["Assembly Accession"].tolist():
                        raise IOError("The accession {} is not in the dataframe, but we should have found it.".format(correct_accession))
                    else:
                        if df[df["Assembly Accession"] == correct_accession]["Embargo"].tolist()[0] == "Not Embargoed":
                            # Here we are just getting the things specifically not embargoed.
                            shutil.copy(accession_dict[key]["filepath"], notembargodir)
                        else:
                            # The things that will end up here are things specifically "Embargoed" or "Embargo Ambiguous"
                            #  There may be other categories that we add in the future.
                            shutil.copy(accession_dict[key]["filepath"], embargodir)

            print()
            print()

    # sort the df by lineage and embargo status, then reset the index
    df = df.sort_values(by = ["Lineage", "Embargo"], ascending = [True, True])
    df = df.reset_index(drop = True)

    # Write the three spreadsheets
    allspreadsheet        = os.path.join(args.output_directory, f"{args.prefix}_all_{datetoday}.tsv")
    embargospreadsheet    = os.path.join(args.output_directory, f"{args.prefix}_embargoed_{datetoday}.tsv")
    notembargospreadsheet = os.path.join(args.output_directory, f"{args.prefix}_notembargoed_{datetoday}.tsv")
    df.to_csv(allspreadsheet, sep = "\t", index = False)
    df[df["Embargo"] == "Not Embargoed"].to_csv(notembargospreadsheet, sep = "\t", index = False)
    # For the embargoed genomes, we include "Embargoed" and "Embargo Ambiguous".=
    # It is just easier to take the inverse of the "Not Embargoed" genomes.
    df[~df["Embargo"].isin(["Not Embargoed"])].to_csv(embargospreadsheet, sep = "\t", index = False)

    # Write three spreadsheets with a limited set of columns.
    keep_columns = ["Assembly Accession", "Current Accession", "Organism Name", "Organism Common Name",
                    "Assembly Submitter", "Organism Taxonomic ID",
                    "Embargo", "EmbargoPolicy", "EmbargoPolicyLink", "EmbargoReason", "EmbargoLiftPublication",
                    "EmbargoLiftPublicationPMID", "EmbargoLiftPublicationDOI", "EmbargoLiftDate", "EmbargoDaysUntil",
                    "Lineage", "Annotation Name",
                    "Annotation Pipeline", "Annotation Provider",
                    "Annotation Release Date", "Assembly BioSample Accession", "Assembly BioSample BioProject Accession",
                    "Assembly BioSample Description Comment", "Assembly BioSample Description Organism Name",
                    "Assembly BioSample Description Title", "Assembly BioSample Sample Identifiers Database",
                    "Assembly BioSample Last updated", "Assembly BioSample Owner Name", "Assembly BioSample Publication date",
                    "Assembly Description", "Assembly Level", "Assembly Name", "Assembly Notes", "Assembly Paired Assembly Accession",
                    "Assembly Refseq Category", "Assembly Release Date"]
    subdf = df[keep_columns]
    #                                             default is:     spreadsheet_genomes_all_{datetoday}...
    allspreadsheet        = os.path.join(args.output_directory, f"{args.prefix}_all_{datetoday}_fewerColumns.tsv")
    embargospreadsheet    = os.path.join(args.output_directory, f"{args.prefix}_embargoed_{datetoday}_fewerColumns.tsv")
    notembargospreadsheet = os.path.join(args.output_directory, f"{args.prefix}_notembargoed_{datetoday}_fewerColumns.tsv")
    subdf.to_csv(allspreadsheet, sep = "\t", index = False)
    subdf[subdf["Embargo"] == "Not Embargoed"].to_csv(notembargospreadsheet, sep = "\t", index = False)
    # For the embargoed genomes, we include "Embargoed" and "Embargo Ambiguous".=
    # It is just easier to take the inverse of the "Not Embargoed" genomes.
    subdf[~subdf["Embargo"].isin(["Not Embargoed"])].to_csv(embargospreadsheet, sep = "\t", index = False)

    # Write a report of the number of genomes in each category.
    reportfile = os.path.join(args.output_directory, f"{args.prefix}_report.txt")
    generate_report(reportfile, df, files_missing_in_tsv, accession_dict)

if __name__ == "__main__":
    main()

