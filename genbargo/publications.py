#!/usr/bin/env python
"""
Link genome assemblies to the publications that released them.

Under the VGP data-use policy an assembly is "released from this embargo when
[it is] expressly published". This module finds those publications so the
embargo annotator can lift the embargo on published assemblies.

Two sources are combined (manual entries win over automatic ones):

1. A hand-curated table (``publications_manual.tsv``) for project papers and
   pre-prints that the NCBI cross-references miss (e.g. large consortium
   papers such as a VGP bioRxiv release).
2. Automatic lookups against NCBI Entrez (assembly -> BioProject -> PubMed),
   cached in ``publications_cache.tsv`` so weekly CI only queries new
   accessions.

The public entry point used by the embargo pipeline is ``merge_publications``.
The automatic lookup helpers only import Biopython when actually querying, so
this module can be imported (and the manual/cache paths used) in a minimal
environment without Biopython installed.
"""

import os
import time

import pandas as pd

# Columns used for both the manual and cache tables.
PUB_COLUMNS = [
    "Assembly Accession",
    "PMID",
    "DOI",
    "Publication",
    "PublicationDate",
    "Source",
    "LastChecked",
]

_EMBARGOED_STATES = ["Embargoed", "Embargo Ambiguous"]


# --------------------------------------------------------------------------- #
# Table I/O
# --------------------------------------------------------------------------- #
def _empty_pub_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=PUB_COLUMNS)


def load_pub_table(path) -> pd.DataFrame:
    """Load a manual or cache publication table, or return an empty frame."""
    if path is None or not os.path.exists(path):
        return _empty_pub_frame()
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    for col in PUB_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[PUB_COLUMNS]


def save_pub_table(df, path):
    """Write a publication table to ``path`` (creating parent dirs)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df[PUB_COLUMNS].to_csv(path, sep="\t", index=False)


# --------------------------------------------------------------------------- #
# Automatic lookup via NCBI Entrez
# --------------------------------------------------------------------------- #
def _entrez(email, api_key):
    """Configure and return the Bio.Entrez module (imported lazily)."""
    from Bio import Entrez  # noqa: PLC0415  (optional dependency)

    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key
    return Entrez


def fetch_pmids_for_accession(accession, email, api_key, max_retries=5, delay=1):
    """Return the list of PubMed IDs linked to an assembly accession."""
    Entrez = _entrez(email, api_key)
    for attempt in range(max_retries):
        try:
            with Entrez.esearch(db="assembly", term=accession) as handle:
                record = Entrez.read(handle)
            ids = record.get("IdList", [])
            if not ids:
                return []
            pmids = []
            for assembly_id in ids:
                with Entrez.esummary(
                    db="assembly", id=assembly_id, report="full"
                ) as handle:
                    summary = Entrez.read(handle, validate=False)
                docs = summary["DocumentSummarySet"]["DocumentSummary"]
                for doc in docs:
                    pmids.extend([str(p) for p in doc.get("PubMedIds", [])])
            return sorted(set(pmids))
        except Exception as e:  # noqa: BLE001 - retry on any transient error
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                print("  ! Entrez lookup failed for {}: {}".format(accession, e))
                return []
    return []


def fetch_pubmed_details(pmids, email, api_key, max_retries=5, delay=1):
    """Return (doi, title, date) for the first PubMed record with a DOI."""
    if not pmids:
        return "", "", ""
    Entrez = _entrez(email, api_key)
    for attempt in range(max_retries):
        try:
            with Entrez.esummary(db="pubmed", id=",".join(pmids)) as handle:
                records = Entrez.read(handle, validate=False)
            best = None
            for rec in records:
                doi = ""
                for aid in rec.get("ArticleIds", []):
                    if aid.get("IdType") == "doi":
                        doi = str(aid.get("Value", ""))
                title = str(rec.get("Title", ""))
                date = str(rec.get("PubDate", "") or rec.get("EPubDate", ""))
                if doi:
                    return doi, title, date
                if best is None:
                    best = ("", title, date)
            return best if best else ("", "", "")
        except Exception as e:  # noqa: BLE001
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                print("  ! PubMed lookup failed for {}: {}".format(pmids, e))
                return "", "", ""
    return "", "", ""


def query_accession(accession, email, api_key, today_string):
    """Look up one accession and return a PUB_COLUMNS-shaped dict (row)."""
    pmids = fetch_pmids_for_accession(accession, email, api_key)
    doi, title, date = fetch_pubmed_details(pmids, email, api_key)
    return {
        "Assembly Accession": accession,
        "PMID": ";".join(pmids),
        "DOI": doi,
        "Publication": title,
        "PublicationDate": date,
        "Source": "api",
        "LastChecked": today_string,
    }


# --------------------------------------------------------------------------- #
# Building the combined lookup
# --------------------------------------------------------------------------- #
def _has_publication(row) -> bool:
    return bool(str(row.get("PMID", "")).strip()) or bool(
        str(row.get("DOI", "")).strip()
    )


def build_lookup(candidate_accessions, manual_df, cache_df, email, api_key,
                 query_api=False, today_string=None, delay=0.34):
    """Return ({accession: pub_row}, updated_cache_df).

    Manual entries take precedence over cached/automatic ones. When
    ``query_api`` is True, candidate accessions absent from both manual and
    cache tables are looked up via Entrez and appended to the cache.
    """
    lookup = {}
    cache_map = {r["Assembly Accession"]: dict(r) for _, r in cache_df.iterrows()}

    # Cache first (may be overwritten by manual below).
    for acc, row in cache_map.items():
        lookup[acc] = row
    # Manual overrides.
    for _, row in manual_df.iterrows():
        acc = str(row["Assembly Accession"]).strip()
        if acc:
            entry = dict(row)
            entry.setdefault("Source", "manual")
            entry["Source"] = "manual"
            lookup[acc] = entry

    if query_api:
        if not email:
            raise ValueError("An email address is required for NCBI Entrez queries.")
        to_query = [
            acc for acc in candidate_accessions
            if acc not in lookup  # unknown = never checked (manual or cached)
        ]
        print("  Querying NCBI for {} uncached accession(s)...".format(len(to_query)))
        for i, acc in enumerate(to_query, 1):
            entry = query_accession(acc, email, api_key, today_string)
            lookup[acc] = entry
            cache_map[acc] = entry
            if i % 25 == 0:
                print("    ...{}/{}".format(i, len(to_query)))
            time.sleep(delay)

    updated_cache = (
        pd.DataFrame(list(cache_map.values()), columns=PUB_COLUMNS)
        if cache_map else _empty_pub_frame()
    )
    return lookup, updated_cache


# --------------------------------------------------------------------------- #
# Merge into the embargo dataframe (fills the step-5 TODO in the pipeline)
# --------------------------------------------------------------------------- #
def merge_publications(df, manual_path=None, cache_path=None, email=None,
                       api_key=None, query_api=False, today=None):
    """Lift the embargo on any embargoed assembly that has been published.

    For every currently-embargoed row with a known publication, set
    ``Embargo`` to "Not Embargoed", fill the ``EmbargoLift*`` columns, set the
    lift date to the publication date and recompute ``EmbargoDaysUntil``.
    When ``query_api`` is True the cache is refreshed and written back to
    ``cache_path``.
    """
    if today is None:
        today = pd.Timestamp.today()
    today_string = today.strftime("%Y-%m-%d")

    manual_df = load_pub_table(manual_path)
    cache_df = load_pub_table(cache_path)

    candidates = df[df["Embargo"].isin(_EMBARGOED_STATES)]["Assembly Accession"]
    candidate_accessions = sorted(set(candidates.astype(str)))

    lookup, updated_cache = build_lookup(
        candidate_accessions, manual_df, cache_df, email, api_key,
        query_api=query_api, today_string=today_string,
    )

    if query_api and cache_path is not None:
        save_pub_table(updated_cache, cache_path)

    n_lifted = 0
    for index, row in df.iterrows():
        if row["Embargo"] not in _EMBARGOED_STATES:
            continue
        acc = str(row["Assembly Accession"])
        pub = lookup.get(acc)
        if pub is None or not _has_publication(pub):
            continue

        pub_date = str(pub.get("PublicationDate", "")).strip()
        lift_date = today
        parsed = pd.to_datetime(pub_date, errors="coerce")
        if pd.notna(parsed):
            lift_date = parsed
        days_until = int((lift_date - today).days)

        df.at[index, "Embargo"] = "Not Embargoed"
        df.at[index, "EmbargoLiftPublication"] = pub.get("Publication", "")
        df.at[index, "EmbargoLiftPublicationPMID"] = pub.get("PMID", "")
        df.at[index, "EmbargoLiftPublicationDOI"] = pub.get("DOI", "")
        df.at[index, "EmbargoLiftDate"] = lift_date.strftime("%Y-%m-%d")
        df.at[index, "EmbargoDaysUntil"] = days_until

        reason = str(df.at[index, "EmbargoReason"])
        reason += (
            " However, this assembly has been expressly published"
            + (" on {}".format(pub_date) if pub_date else "")
            + (" ({})".format(pub["Publication"]) if pub.get("Publication") else "")
            + ". Under the VGP data-use policy an assembly is released from its"
            + " embargo when it is expressly published, so it is no longer"
            + " embargoed (source: {}).".format(pub.get("Source", "lookup"))
        )
        df.at[index, "EmbargoReason"] = reason
        n_lifted += 1

    print("Publication linking lifted the embargo on {} assemblies.".format(n_lifted))
    return df
