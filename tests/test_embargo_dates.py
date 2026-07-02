"""
Tests for the embargo-date logic.

The annotator's notion of "today" is pinned via ``embargo.set_now`` so these
tests are deterministic regardless of when they run.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from genbargo import embargo, publications  # noqa: E402


def make_df(rows):
    """Build a minimal input dataframe from a list of row dicts."""
    base = {
        "Assembly Accession": "GCA_000000000.1",
        "Assembly Submitter": "Vertebrate Genomes Project",
        "Assembly Release Date": pd.Timestamp("2020-01-01"),
        "Annotation Release Date": pd.NaT,
        "Assembly BioSample Description Comment": "",
        "Lineage": ";7742;",
    }
    records = []
    for r in rows:
        rec = dict(base)
        rec.update(r)
        records.append(rec)
    return pd.DataFrame(records)


@pytest.fixture(autouse=True)
def _reset_now():
    yield
    embargo.set_now(None)


def annotate(df, today, conservative=False):
    embargo.set_now(today)
    return embargo.annotate_embargo_status(df.reset_index(drop=True),
                                           conservative=conservative)


def test_vgp_pre2024_unannotated_still_embargoed():
    df = make_df([{"Assembly Release Date": pd.Timestamp("2020-01-01")}])
    out = annotate(df, today="2021-01-01")
    assert out.loc[0, "Embargo"] == "Embargoed"
    # 2-year embargo from a pre-May-2024 release.
    assert out.loc[0, "EmbargoLiftDate"] == "2022-01-01"


def test_vgp_pre2024_unannotated_expired():
    df = make_df([{"Assembly Release Date": pd.Timestamp("2020-01-01")}])
    out = annotate(df, today="2023-01-01")
    assert out.loc[0, "Embargo"] == "Not Embargoed"
    assert out.loc[0, "EmbargoLiftDate"] == "2022-01-01"


def test_vgp_post2024_unannotated_one_year():
    df = make_df([{"Assembly Release Date": pd.Timestamp("2024-06-01")}])
    out = annotate(df, today="2024-09-01")
    assert out.loc[0, "Embargo"] == "Embargoed"
    # 1-year embargo for post-May-2024 releases.
    assert out.loc[0, "EmbargoLiftDate"] == "2025-06-01"


def test_vgp_annotation_within_window_runs_from_annotation():
    df = make_df([{
        "Assembly Release Date": pd.Timestamp("2020-01-01"),
        "Annotation Release Date": pd.Timestamp("2020-07-01"),
    }])
    out = annotate(df, today="2021-01-01")
    # Annotation within the 2-year window -> lift is 2 years after annotation.
    assert out.loc[0, "EmbargoLiftDate"] == "2022-07-01"


def test_dtol_never_embargoed():
    df = make_df([{
        "Assembly Submitter": "Wellcome Sanger Institute",
        "Assembly Accession": "GCA_999999999.1",  # not a Sanger-25 assembly
        "Assembly Release Date": pd.Timestamp("2023-01-01"),
    }])
    out = annotate(df, today="2023-06-01")
    assert out.loc[0, "Embargo"] == "Not Embargoed"
    assert "Darwin Tree of Life" in out.loc[0, "EmbargoPolicy"]


def test_dnazoo_open_with_citation():
    df = make_df([{
        "Assembly Submitter": "DNA Zoo",
        "Assembly Release Date": pd.Timestamp("2022-01-01"),
    }])
    out = annotate(df, today="2023-01-01")
    assert out.loc[0, "Embargo"] == "Not Embargoed"
    assert out.loc[0, "EmbargoLiftPublicationPMID"] == "28336562"


def test_publication_lifts_embargo(tmp_path):
    df = make_df([{
        "Assembly Accession": "GCA_123456789.1",
        "Assembly Release Date": pd.Timestamp("2020-01-01"),
    }])
    out = annotate(df, today="2021-01-01")
    assert out.loc[0, "Embargo"] == "Embargoed"

    manual = tmp_path / "manual.tsv"
    pd.DataFrame([{
        "Assembly Accession": "GCA_123456789.1",
        "PMID": "12345678",
        "DOI": "10.1101/2026.01.01.000000",
        "Publication": "A big VGP paper (2026)",
        "PublicationDate": "2026-01-01",
        "Source": "manual",
        "LastChecked": "2026-01-01",
    }])[publications.PUB_COLUMNS].to_csv(manual, sep="\t", index=False)

    embargo.set_now("2026-06-01")
    merged = publications.merge_publications(
        out, manual_path=str(manual), cache_path=None,
        query_api=False, today=pd.Timestamp("2026-06-01"),
    )
    assert merged.loc[0, "Embargo"] == "Not Embargoed"
    assert merged.loc[0, "EmbargoLiftPublicationPMID"] == "12345678"
    assert merged.loc[0, "EmbargoLiftDate"] == "2026-01-01"


def test_conservative_doubles_unannotated_window():
    df = make_df([{"Assembly Release Date": pd.Timestamp("2020-01-01")}])
    out = annotate(df, today="2021-01-01", conservative=True)
    # Conservative doubles the 2-year window -> 4 years.
    assert out.loc[0, "EmbargoLiftDate"] == "2024-01-01"
    assert out.loc[0, "Embargo"] == "Embargoed"
