#!/usr/bin/env python

"""
Embargo annotation for genome assemblies.

This is the core of genbargo. It takes one or more NCBI-Datasets-style TSVs of
genome assemblies and annotates each with its embargo status, based on the
data-use policy of the submitting project. See ``docs/embargo_policies.md`` for
the full text and provenance of every policy encoded here.

The public entry point is ``main`` (exposed on the command line as
``filter_assemblies.py`` and as ``genbargo filter``). ``annotate_embargo_status``
is the reusable library function.

Behaviour is unchanged from the original ``filter_assemblies.py`` except that:
  * ``pd.Timestamp.today()`` is routed through ``now()`` so tests can pin a date;
  * after annotation, publications are merged in (an assembly that has been
    published is released from the VGP embargo); and
  * a Markdown dashboard is written alongside the TSV report.
"""

import argparse
import os
import shutil

import pandas as pd

from genbargo import publications as _publications
from genbargo import report as _report

# --------------------------------------------------------------------------- #
# Date injection (so the embargo-date logic is testable with a pinned "today")
# --------------------------------------------------------------------------- #
_NOW = None


def now():
    """Return the reference "today". Pinned via ``set_now`` in tests."""
    return _NOW if _NOW is not None else pd.Timestamp.today()


def set_now(timestamp):
    """Pin (or, with ``None``, unpin) the reference date used by the annotator."""
    global _NOW
    _NOW = None if timestamp is None else pd.Timestamp(timestamp)


# --------------------------------------------------------------------------- #
# Data-file resolution (assembly_specifications/ lives at the repo root)
# --------------------------------------------------------------------------- #
_PACKAGE_DIR = os.path.dirname(os.path.realpath(__file__))
_REPO_ROOT = os.path.dirname(_PACKAGE_DIR)


def data_path(relpath):
    """Resolve a data file (e.g. ``assembly_specifications/x.tsv``).

    Checks the repo root, then the package directory, then the CWD.
    """
    for base in (_REPO_ROOT, _PACKAGE_DIR, os.getcwd()):
        candidate = os.path.join(base, relpath)
        if os.path.exists(candidate):
            return candidate
    # Fall back to the repo-root path so callers get a sensible error message.
    return os.path.join(_REPO_ROOT, relpath)


DEFAULT_SANGER_TSV = data_path("assembly_specifications/Sanger_25_genomes.tsv")
DEFAULT_MANUAL_PUBS = os.path.join(
    _REPO_ROOT, "assembly_specifications", "publications_manual.tsv"
)
DEFAULT_CACHE_PUBS = os.path.join(
    _REPO_ROOT, "assembly_specifications", "publications_cache.tsv"
)
DEFAULT_DASHBOARD_DIR = os.path.join(_REPO_ROOT, "dashboard")

REQUIRED_EMBARGO_COLUMNS = [
    "Embargo",
    "EmbargoPolicy",
    "EmbargoPolicyLink",
    "EmbargoReason",
    "EmbargoLiftPublication",
    "EmbargoLiftPublicationPMID",
    "EmbargoLiftPublicationDOI",
    "EmbargoLiftDate",
    "EmbargoDaysUntil",
]


def _required_column_check(df):
    """Check that the required embargo columns are present in the dataframe."""
    for column in REQUIRED_EMBARGO_COLUMNS:
        if column not in df.columns:
            raise IOError("The column '{}' is not in the dataframe.".format(column))


def _row_helper_DToL(df, index, row):
    """Apply the Darwin Tree of Life open-data (no embargo) policy to one row."""
    _required_column_check(df)
    days_until = int((row["Assembly Release Date"] - now()).days)
    embargo_message = "This genome falls under the Darwin Tree of Life data use policy."
    embargo_message += " The policy text states, \"DToL data are released freely for reuse for any purpose upon deposition in ENA, and the DToL partners encourage such community reuse.\""
    embargo_message += " This assembly's 'Assembly Release Date' on NCBI/ENA is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))
    embargo_message += " Therefore, the genome has not been under an embargo since its publication date,"
    embargo_message += " {} years and {} days ago".format(-1 * days_until // 365, -1 * days_until % 365)
    embargo_message += " since this report was generated on {}.".format(now().strftime("%Y-%m-%d"))
    df.at[index, "Embargo"]           = "Not Embargoed"
    df.at[index, "EmbargoPolicy"]     = "Darwin Tree of Life Open Data Release Policy v1.04"
    df.at[index, "EmbargoPolicyLink"] = "https://www.darwintreeoflife.org/wp-content/uploads/2024/10/DToL-Open-Data-Release-Policy.docx_.pdf"
    df.at[index, "EmbargoReason"]     = embargo_message
    df.at[index, "EmbargoLiftDate"]   = row["Assembly Release Date"].strftime("%Y-%m-%d")
    df.at[index, "EmbargoDaysUntil"]  = days_until


def _row_helper_VPG(df, index, row, conservative=False):
    """Apply the VGP/G10K embargo policy to one row.

    Pre-May-1-2024 assemblies get a 2-year embargo; later ones get 1 year. The
    embargo runs from the assembly release date, unless an annotation was
    released within that window, in which case it runs from the annotation date.
    See ``docs/embargo_policies.md`` for the full policy and the list of
    submitters this applies to.
    """
    _required_column_check(df)

    embargo_reason_message = ""
    timestamp = ""
    embargo_reason_message += " This genome assembly was uploaded by {} on {} (MMDDYYYY).".format(row["Assembly Submitter"], row["Assembly Release Date"])

    offset_time = 0
    if row["Assembly Release Date"] < pd.Timestamp("2024-05-01"):
        embargo_reason_message = "This genome falls under the pre-May 1st, 2024 VGP embargo policy, originally published in 2018."
        df.at[index, "EmbargoPolicy"]     = "VGP, pre-May 1st, 2024 policy"
        df.at[index, "EmbargoPolicyLink"] = "https://genome10k.ucsc.edu/data-use-policies/ clarified here: https://vertebrategenomesproject.org/data-use-policies"
        offset_time = 2
    else:
        embargo_reason_message = "This genome falls under the new, post-May 1st, 2024 VGP embargo policy, last updated July 8th, 2024."
        df.at[index, "EmbargoPolicy"]     = "VGP, post-May 1st, 2024 policy"
        df.at[index, "EmbargoPolicyLink"] = "https://vertebrategenomesproject.org/data-use-policies"
        offset_time = 1
    embargo_reason_message += " This assembly 'Assembly Release Date' on NCBI is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))

    if not pd.isna(row["Annotation Release Date"]):
        if row["Annotation Release Date"] - row["Assembly Release Date"] < pd.Timedelta(days=365 * offset_time):
            timestamp = row["Annotation Release Date"] + pd.DateOffset(years=offset_time)
            embargo_reason_message += " The annotation was released on {}, less than {} year(s) after the assembly upload date.".format(
                row["Annotation Release Date"].strftime("%Y-%m-%d"), offset_time)
            embargo_reason_message += " Under this embargo policy and based on the assembly and annotation release dates, the Embargo Lift Date of this assembly is {} year(s) after the annotation upload date.".format(offset_time)
        else:
            timestamp = row["Assembly Release Date"] + pd.DateOffset(years=offset_time)
            df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
            embargo_reason_message += " The annotation was released on {}, more than {} year(s) after the assembly upload date.".format(
                row["Annotation Release Date"].strftime("%Y-%m-%d"), offset_time)
            embargo_reason_message += " Under this embargo policy and based on the assembly and annotation release dates, the Embargo Lift Date of this assembly is {} year(s) after the assembly upload date.".format(offset_time)
        df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
        embargo_reason_message += " The Embargo Lift Date is therefore {}.".format(df.at[index, "EmbargoLiftDate"])
        df.at[index, "EmbargoReason"] = embargo_reason_message
    else:
        if conservative is True:
            timestamp = row["Assembly Release Date"] + pd.DateOffset(years=offset_time * 2)
            embargo_reason_message += " This embargo date has been conservatively estimated to be {} year(s) after the assembly upload date, on the chance that this report was generated before the annotation was released within the embargo lapse window.".format(offset_time * 2)
        else:
            timestamp = row["Assembly Release Date"] + pd.DateOffset(years=offset_time)
        df.at[index, "EmbargoLiftDate"] = timestamp.strftime("%Y-%m-%d")
        embargo_reason_message += " There is no annotation released currently for this assembly. This may change at a later date."
        embargo_reason_message += " Therefore, the Embargo Lift Date is {} year(s) after the assembly upload date.".format(offset_time)
        embargo_reason_message += " The Embargo Lift Date is therefore {}.".format(df.at[index, "EmbargoLiftDate"])

    if timestamp == "":
        raise IOError("We should have reinitialized the timestamp before we got here.")
    daysuntil = timestamp - now()
    df.at[index, "EmbargoDaysUntil"] = int(daysuntil.days)

    if now() > timestamp:
        df.at[index, "Embargo"] = "Not Embargoed"
        embargo_reason_message += " This report was generated on {}, {} years and {} days after the Embargo Lift Date, and therefore the genome is no longer embargoed.".format(
            now().strftime("%Y-%m-%d"), -1 * int(daysuntil.days) // 365, -1 * int(daysuntil.days) % 365)
    else:
        df.at[index, "Embargo"] = "Embargoed"
        embargo_reason_message += " This report was generated on {}, {} days before the Embargo Lift Date, and therefore the genome is still embargoed.".format(
            now().strftime("%Y-%m-%d"), daysuntil.days)
    df.at[index, "EmbargoReason"] = embargo_reason_message


# Submitters whose assemblies fall directly under the VGP embargo policy.
# See docs/embargo_policies.md for provenance of each string.
VGP_POLICY_SUBMITTERS = [
    "Bat1K",
    "Bird10K",
    "Human Pangenome Reference Consortium",
    "G10K",
    "Genome 10K",
    "Leibniz Institute for Zoo and Wildlife Research",
    "Telomere-to-Telomere Consortium",
    "Vertebrate Genomes Project",
]

WELLCOME_SUBMITTERS = [
    "Wellcome Sanger Institute",
    "WELLCOME SANGER INSTITUTE",
    "Wellcome Trust Sanger Institute",
]

DNAZOO_SUBMITTERS = ["DNA Zoo"]


def _casefold_expand(names):
    """Return the names plus their lowercased variants (matches original logic)."""
    return names + [x.lower() for x in names]


def _annotate_embargo_status_VGP(df, conservative=False) -> pd.DataFrame:
    """Annotate rows whose 'Assembly Submitter' falls directly under the VGP policy."""
    submitters = _casefold_expand(VGP_POLICY_SUBMITTERS)
    for index, row in df.iterrows():
        if row["Assembly Submitter"] in submitters:
            _row_helper_VPG(df, index, row, conservative=conservative)
    return df


def _annotate_embargo_status_DNAZoo(df) -> pd.DataFrame:
    """Annotate DNA Zoo assemblies (open data; request citation of Dudchenko 2017)."""
    _required_column_check(df)
    submitters = _casefold_expand(DNAZOO_SUBMITTERS)
    for index, row in df.iterrows():
        if row["Assembly Submitter"] in submitters:
            days_until = int((row["Assembly Release Date"] - now()).days)
            df.at[index, "Embargo"]           = "Not Embargoed"
            df.at[index, "EmbargoPolicy"]     = "DNA Zoo Open Data Release Policy"
            df.at[index, "EmbargoPolicyLink"] = "https://www.dnazoo.org/usage"
            embargo_message = "This genome falls under the DNA Zoo data use policy."
            embargo_message += " The policy text states, \"All DNA Zoo data, including genome assemblies, genome annotations, DNA-Seq data, and Hi-C maps, are shared freely without any restriction.\""
            embargo_message += " This assembly's 'Assembly Release Date' on NCBI/ENA is {}.".format(row["Assembly Release Date"].strftime("%Y-%m-%d"))
            embargo_message += " Therefore, the genome has not been under an embargo since its publication date,"
            embargo_message += " {} years and {} days ago".format(-1 * days_until // 365, -1 * days_until % 365)
            embargo_message += " since this report was generated on {}.".format(now().strftime("%Y-%m-%d"))
            embargo_message += " The authors request that publications using these genomes at least cite the article, Dudchenko et al. (2017) https://doi.org/10.1126/science.aal3327 ."
            df.at[index, "EmbargoReason"]              = embargo_message
            df.at[index, "EmbargoLiftPublication"]     = "Dudchenko, Batra, Omer,  et al. 2017. De Novo Assembly of the Aedes Aegypti Genome Using Hi-C Yields Chromosome-Length Scaffolds. Science (New York, N.Y.) 356 (6333): 92-95."
            df.at[index, "EmbargoLiftPublicationPMID"] = "28336562"
            df.at[index, "EmbargoLiftPublicationDOI"]  = "https://doi.org/10.1126/science.aal3327"
            df.at[index, "EmbargoLiftDate"]            = row["Assembly Release Date"].strftime("%Y-%m-%d")
            df.at[index, "EmbargoDaysUntil"]           = days_until
    return df


def _annotate_embargo_status_WellcomeSangerInstitute(df, conservative=False) -> pd.DataFrame:
    """Annotate Wellcome Sanger Institute assemblies.

    Most Sanger assemblies are Darwin Tree of Life (open, no embargo), but those
    in the Sanger 25 Genomes Project fall under the VGP embargo. The Sanger 25
    assemblies are listed in ``assembly_specifications/Sanger_25_genomes.tsv``.
    See docs/embargo_policies.md for details.
    """
    submitters = _casefold_expand(WELLCOME_SUBMITTERS)

    sanger25df = pd.read_csv(DEFAULT_SANGER_TSV, sep="\t")
    sanger25df["assembly_stripped"] = sanger25df["Assembly Accession"].apply(lambda x: x.split(".")[0])
    sanger25df_unique = list(sorted(sanger25df["assembly_stripped"].unique()))

    for index, row in df.iterrows():
        if row["Assembly Submitter"] in submitters:
            thisassembly = row["Assembly Accession"].split(".")[0]
            if thisassembly in sanger25df_unique:
                _row_helper_VPG(df, index, row, conservative=conservative)
            else:
                _row_helper_DToL(df, index, row)
    return df


def _annotate_embargo_status_Unknown(df) -> pd.DataFrame:
    """Mark remaining unknown-policy assemblies not embargoed unless their
    BioSample comment contains the word 'embargo'."""
    for index, row in df.iterrows():
        if (row["Embargo"] == "Unknown") and (row["EmbargoPolicy"] == "Unknown"):
            comment_text = str(row["Assembly BioSample Description Comment"]).lower()
            if "embargo" not in comment_text:
                df.at[index, "Embargo"]           = "Not Embargoed"
                df.at[index, "EmbargoReason"]     = "We are not aware of an embargo policy for this genome, and there is no embargo policy specified in the \"Assembly BioSample Description Comment\" field."
                df.at[index, "EmbargoLiftDate"]   = row["Assembly Release Date"].strftime("%Y-%m-%d")
                days_until = row["Assembly Release Date"] - now()
                df.at[index, "EmbargoDaysUntil"]  = days_until.days
            else:
                e_msg = "We should have caught all of the genomes that are not embargoed by now, but there was message about an embargo "
                e_msg += "in the \"Assembly BioSample Description Comment\" field for assembly {}. ".format(row["Assembly Accession"])
                e_msg += "The submitter of this assembly is {}.".format(row["Assembly Submitter"])
                raise IOError(e_msg)
    return df


def _annotate_embargo_status_embargoString(df):
    """Flag rows whose BioSample comment mentions 'embargo' for manual review."""
    for index, row in df.iterrows():
        comment_text = str(row["Assembly BioSample Description Comment"]).lower()
        if "embargo" in comment_text:
            if row["Embargo"] == "Embargoed":
                t = row["EmbargoReason"]
                t += " The assembly has the string \"embargo\" in the \"Assembly BioSample Description Comment\" field."
                t += " This is consistent with the embargo status of the genome."
                df.at[index, "EmbargoReason"] = t
            elif row["Embargo"] == "Not Embargoed":
                df.at[index, "Embargo"] = "Embargo Ambiguous"
                t = row["EmbargoReason"]
                t += " On the other hand, there is a string \"embargo\" in the \"Assembly BioSample Description Comment\" field."
                t += " Please check that field to clarify why the word \"embargo\" is still present."
                t += " It is possible that this string should it have been removed,"
                t += " or that the intention is to extend the embargo past the policy data for this specific accession."
                df.at[index, "EmbargoReason"] = t
            else:
                raise IOError("The embargo status should not be unknown at this point.")
    return df


def annotate_embargo_status(df, conservative=False) -> pd.DataFrame:
    """Annotate the dataframe with the embargo status of each genome.

    Fills the ``Embargo``, ``EmbargoPolicy``, ``EmbargoReason``,
    ``EmbargoLift*`` and ``EmbargoDaysUntil`` columns. See the module docstring
    and docs/embargo_policies.md for the policies applied.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("The input must be a pandas dataframe.")
    if not df.index.is_unique:
        raise IOError("There are conflicts in the indices of the spreadsheet, try resetting the indices of the input DataFrame.")

    col_default_pair = {
        "Embargo": "Unknown",
        "EmbargoPolicy": "Unknown",
        "EmbargoPolicyLink": "Unknown",
        "EmbargoReason": "No explanation assigned.",
        "EmbargoLiftPublication": "No publication assigned.",
        "EmbargoLiftPublicationPMID": "No PMID assigned.",
        "EmbargoLiftPublicationDOI": "No DOI assigned.",
        "EmbargoLiftDate": "No Assigned Date",
        "EmbargoDaysUntil": 99999999,
    }
    for thiscol in col_default_pair:
        if thiscol not in df.columns:
            df[thiscol] = col_default_pair[thiscol]

    df = _annotate_embargo_status_VGP(df, conservative=conservative)
    print("We're done checking which VGP genomes are embargoed.")
    df = _annotate_embargo_status_WellcomeSangerInstitute(df, conservative=conservative)
    print("We're done checking the embargoes of the Wellcome Sanger Institute.")
    df = _annotate_embargo_status_DNAZoo(df)
    print("We're done checking the embargoes of the DNA Zoo.")
    df = _annotate_embargo_status_Unknown(df)
    print("We're done checking the embargoes of the remaining genomes.")

    if conservative is True:
        df = _annotate_embargo_status_embargoString(df)

    return df


def generate_report(output_filepath, df, files_not_in_spreadsheet=None, accession_dict=None):
    """Generate a text report summarising genome embargo information."""
    if files_not_in_spreadsheet is None:
        files_not_in_spreadsheet = set()
    if accession_dict is None:
        accession_dict = {}

    output_directory = os.path.dirname(output_filepath)
    if not os.path.exists(output_directory):
        raise IOError("The output directory {} does not exist.".format(output_directory))

    today_string = now().strftime("%Y-%m-%d")

    num_genomes_spreadsheet = len(df)
    num_genomes_directory = len(accession_dict)
    num_genomes_not_in_spreadsheet = len(files_not_in_spreadsheet)
    num_genomes_not_in_directory = (
        len([x for x in df["Assembly Accession"] if x not in accession_dict])
        if accession_dict else 0
    )
    num_genomes_embargoed = len(df[df["Embargo"] == "Embargoed"])
    num_genomes_embargoed_vertebrate = len(df[(df["Embargo"] == "Embargoed") & (df["Lineage"].str.contains(";7742;"))])
    num_genomes_not_embargoed = len(df[df["Embargo"] == "Not Embargoed"])
    num_genomes_not_embargoed_vertebrate = len(df[(df["Embargo"] == "Not Embargoed") & (df["Lineage"].str.contains(";7742;"))])
    num_genomes_not_embargoed_unknown = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"] == "Unknown")])
    num_genomes_not_embargoed_DToL = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"].str.contains("Darwin Tree of Life"))])
    num_genomes_not_embargoed_embargoed = len(df[(df["Embargo"] == "Not Embargoed") & (df["EmbargoPolicy"].str.contains("VGP"))])

    vdf = df[df["Lineage"].str.contains(";7742;")]
    counts = vdf.groupby(["Embargo", "EmbargoPolicy"]).size().reset_index(name='counts')
    counts["PercentOfVertebrates"] = 100 * counts["counts"] / len(vdf)
    vdf_embargoPolicy_counts_percent = counts

    vdf2 = df[df["Lineage"].str.contains(";7742;")]
    counts2 = vdf2.groupby(["Embargo", "Assembly Submitter"]).size().reset_index(name='counts')
    counts2 = counts2.sort_values(by=["Embargo", "counts"], ascending=[True, False])
    counts2 = counts2[counts2["counts"] > 4]
    counts2["PercentOfVertebrates"] = 100 * counts2["counts"] / len(vdf2)
    vdf_embargoPolicy_submitter_counts_percent = counts2

    counts_all = df.groupby(["Embargo", "Assembly Submitter"]).size().reset_index(name='counts')
    counts_all = counts_all.sort_values(by=["Embargo", "counts"], ascending=[True, False])
    counts_all = counts_all[counts_all["counts"] > 4]
    counts_all["PercentOfAllGenomes"] = 100 * counts_all["counts"] / len(df)

    num_vertebrates = len(df[df["Lineage"].str.contains(";7742;")])

    policy_counts_embargoed = df[df["Embargo"] == "Embargoed"]["EmbargoPolicy"].value_counts()
    policy_counts_not_embargoed = df[df["Embargo"] == "Not Embargoed"]["EmbargoPolicy"].value_counts()
    submitter_counts_embargoed = df[df["Embargo"] == "Embargoed"]["Assembly Submitter"].value_counts()
    submitter_counts_not_embargoed = df[df["Embargo"] == "Not Embargoed"]["Assembly Submitter"].value_counts()

    t = "# Genome Embargo Report\n"
    t += "\n"
    t += "Program     : genbargo (filter_assemblies.py)\n"
    t += "Language    : python\n"
    t += "Report Date : {}\n".format(today_string)
    t += "Contact     : darrin.schultz@univie.ac.at\n"
    t += "Github      : {}\n".format(_report.REPO_URL)
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
    t += vdf_embargoPolicy_counts_percent.to_string(index=False)
    t += "\n\n"
    t += vdf_embargoPolicy_submitter_counts_percent.to_string(index=False)
    t += "\n\n"

    target_cols = ["Assembly Accession", "Assembly BioSample Description Comment", "Embargo",
                   "EmbargoPolicy", "EmbargoReason", "EmbargoLiftPublication",
                   "EmbargoLiftPublicationPMID", "EmbargoLiftPublicationDOI", "EmbargoLiftDate"]
    subdf = df[(df["Embargo"] == "Not Embargoed") & (df["Assembly BioSample Description Comment"].str.contains("embargo"))]
    if len(subdf) > 0:
        t += "The {} genomes that are listed as not embargoed, but have the string \"embargo\" in the \"Assembly BioSample Description Comment\" field, are shown below. ".format(len(subdf))
        t += " This likely means that the filter was run without the --conservative flag.\n"
        for index, row in subdf.iterrows():
            t += "  - {}\n".format(row["Assembly Accession"])
            for keycol in target_cols:
                t += "    - {}: {}\n".format(keycol, row[keycol])

    subdf = df[df["Embargo"] == "Embargo Ambiguous"]
    if len(subdf) > 0:
        t += "The {} genomes have the string \"embargo\" in the \"Assembly BioSample Description Comment\" field, are shown below.".format(len(subdf))
        t += " This likely means that the filter was run with the --conservative flag.\n"
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

    with open(output_filepath, "w") as f:
        f.write(t)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Filter assemblies based on their embargo status.")
    parser.add_argument("-t", "--tsvs", nargs="+",
                        help="List of tsvs that contain the annotated and unannotated genomes.")
    parser.add_argument("-c", "--conservative", action="store_true", default=False,
                        help="Conservative mode for VGP genomes. Allows for the possibility that the annotation was released after the spreadsheet date.")
    parser.add_argument("-p", "--prefix", default="spreadsheet_genomes",
                        help="Prefix for the output files.")
    parser.add_argument("-r", "--rbh_directory", default=None,
                        help="Directory of the rbh files.")
    parser.add_argument("-d", "--output_directory", default=os.getcwd(),
                        help="Directory to put the output files in.")
    parser.add_argument("-n", "--no_transfer", action="store_true", default=False,
                        help="Do not transfer the rbh files.")
    # Publication linking (fills the former step-5 TODO).
    parser.add_argument("--publications-manual", default=DEFAULT_MANUAL_PUBS,
                        help="Curated TSV of assembly->publication mappings (manual overrides).")
    parser.add_argument("--publications-cache", default=DEFAULT_CACHE_PUBS,
                        help="Cache TSV of automatic assembly->publication lookups.")
    parser.add_argument("--query-publications", action="store_true", default=False,
                        help="Query NCBI Entrez for publications of embargoed assemblies (updates the cache).")
    parser.add_argument("--email", default=None,
                        help="Email address for NCBI Entrez (required with --query-publications).")
    parser.add_argument("--api-key", default=None,
                        help="NCBI Entrez API key (optional, raises the rate limit).")
    # Dashboard.
    parser.add_argument("--dashboard-dir", default=DEFAULT_DASHBOARD_DIR,
                        help="Directory to write the Markdown dashboard into.")
    parser.add_argument("--no-dashboard", action="store_true", default=False,
                        help="Do not write the Markdown dashboard.")
    args = parser.parse_args()
    print(args)

    for tsv in args.tsvs:
        if not os.path.exists(tsv):
            raise IOError("The file {} does not exist.".format(tsv))
    if args.rbh_directory is not None:
        if not os.path.exists(args.rbh_directory):
            raise IOError("The directory {} does not exist.".format(args.rbh_directory))
    return args


def main(args=None):
    if args is None:
        args = parse_args()
    list_of_ncbi_tsvs = args.tsvs
    directory_of_rbh_files = args.rbh_directory

    accession_dict = {}
    if args.rbh_directory is not None:
        rbhlist = [x for x in os.listdir(directory_of_rbh_files) if x.endswith(".rbh")]
        accession_dict = {x.split("_")[1].split("-")[2]:
                          {"filepath": os.path.join(directory_of_rbh_files, x),
                           "filename": x,
                           "ALGname": x.split("_")[0],
                           "binomial": x.split("_")[1].split("-")[0],
                           "ncbitaxid": x.split("_")[1].split("-")[1],
                           "accession": x.split("_")[1].split("-")[2]}
                          for x in rbhlist}

    list_of_dfs = [pd.read_csv(x, sep="\t") for x in list_of_ncbi_tsvs]
    df = pd.concat(list_of_dfs)
    df = df.reset_index(drop=True)
    df["Assembly Release Date"]   = pd.to_datetime(df["Assembly Release Date"], errors="coerce")
    df["Annotation Release Date"] = pd.to_datetime(df["Annotation Release Date"], errors="coerce")
    # Text columns used with the vectorized ``.str`` accessor must be strings;
    # empty cells otherwise parse as NaN (float) and break ``.str.contains``.
    for _col in ["Assembly BioSample Description Comment", "Lineage",
                 "Assembly Submitter", "Assembly Accession"]:
        if _col in df.columns:
            df[_col] = df[_col].fillna("").astype(str)
    df["Embargo"]                    = "Unknown"
    df["EmbargoPolicy"]              = "Unknown"
    df["EmbargoPolicyLink"]          = "Unknown"
    df["EmbargoReason"]              = "No explanation assigned."
    df["EmbargoLiftPublication"]     = "No publication assigned."
    df["EmbargoLiftPublicationPMID"] = "No PMID assigned."
    df["EmbargoLiftPublicationDOI"]  = "No DOI assigned."
    df["EmbargoLiftDate"]            = "No Assigned Date"
    df["EmbargoDaysUntil"]           = 99999999

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

    # (4) Annotate embargo status by submitter/policy.
    df = annotate_embargo_status(df, conservative=args.conservative)

    # (5) Add publication information; an assembly released through publication
    #     is no longer under the VGP embargo.
    df = _publications.merge_publications(
        df,
        manual_path=args.publications_manual,
        cache_path=args.publications_cache,
        email=args.email,
        api_key=args.api_key,
        query_api=args.query_publications,
        today=now(),
    )

    datetoday = now().strftime("%Y%m%d")

    if not os.path.exists(args.output_directory):
        os.makedirs(args.output_directory)
    if args.rbh_directory is not None:
        if not args.no_transfer:
            embargodir    = os.path.join(args.output_directory, "genomes_embargoed_rbh_files_{}".format(datetoday))
            notembargodir = os.path.join(args.output_directory, "genomes_notembargoed_rbh_files_{}".format(datetoday))
            notintsvdir   = os.path.join(args.output_directory, "genomes_not_in_spreadsheet_rbh_files_{}".format(datetoday))
            for dirname in [embargodir, notembargodir, notintsvdir]:
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
            counter = 0
            for key in accession_dict:
                counter += 1
                print("\r    Copying file {} of {} - {:.2f}%".format(
                    counter, len(accession_dict), 100 * counter / len(accession_dict)), end="")
                correct_accession = key
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
                            shutil.copy(accession_dict[key]["filepath"], notembargodir)
                        else:
                            shutil.copy(accession_dict[key]["filepath"], embargodir)
            print()
            print()

    df = df.sort_values(by=["Lineage", "Embargo"], ascending=[True, True])
    df = df.reset_index(drop=True)

    allspreadsheet        = os.path.join(args.output_directory, f"{args.prefix}_all_{datetoday}.tsv")
    embargospreadsheet    = os.path.join(args.output_directory, f"{args.prefix}_embargoed_{datetoday}.tsv")
    notembargospreadsheet = os.path.join(args.output_directory, f"{args.prefix}_notembargoed_{datetoday}.tsv")
    df.to_csv(allspreadsheet, sep="\t", index=False)
    df[df["Embargo"] == "Not Embargoed"].to_csv(notembargospreadsheet, sep="\t", index=False)
    df[~df["Embargo"].isin(["Not Embargoed"])].to_csv(embargospreadsheet, sep="\t", index=False)

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
    keep_columns = [c for c in keep_columns if c in df.columns]
    subdf = df[keep_columns]
    allspreadsheet        = os.path.join(args.output_directory, f"{args.prefix}_all_{datetoday}_fewerColumns.tsv")
    embargospreadsheet    = os.path.join(args.output_directory, f"{args.prefix}_embargoed_{datetoday}_fewerColumns.tsv")
    notembargospreadsheet = os.path.join(args.output_directory, f"{args.prefix}_notembargoed_{datetoday}_fewerColumns.tsv")
    subdf.to_csv(allspreadsheet, sep="\t", index=False)
    subdf[subdf["Embargo"] == "Not Embargoed"].to_csv(notembargospreadsheet, sep="\t", index=False)
    subdf[~subdf["Embargo"].isin(["Not Embargoed"])].to_csv(embargospreadsheet, sep="\t", index=False)

    reportfile = os.path.join(args.output_directory, f"{args.prefix}_report_{datetoday}.txt")
    generate_report(reportfile, df, files_missing_in_tsv, accession_dict)

    # (6b) Markdown dashboard for humans (renders on the GitHub repo page).
    if not args.no_dashboard:
        md_path = _report.write_markdown_dashboard(df, args.dashboard_dir, today=now())
        print("Wrote dashboard to {}".format(md_path))


if __name__ == "__main__":
    main()
