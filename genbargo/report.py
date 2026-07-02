#!/usr/bin/env python
"""
Markdown dashboard writer for genbargo.

This module renders a human-readable dashboard of embargoed genome assemblies
that displays nicely on the GitHub repository page. It is intentionally
dependency-light (pandas only) so it can run in a minimal CI environment.

The main entry point is ``write_markdown_dashboard``.
"""

import os

import pandas as pd

REPO_URL = "https://github.com/conchoecia/genbargo"

# Columns shown in the embargoed-genomes table, in display order.
# Each tuple is (dataframe column, display header).
_DASHBOARD_COLUMNS = [
    ("Assembly Accession", "Accession"),
    ("Organism Name", "Organism"),
    ("Organism Common Name", "Common name"),
    ("Assembly Submitter", "Submitter"),
    ("EmbargoPolicy", "Policy"),
    ("EmbargoLiftDate", "Lift date"),
    ("EmbargoDaysUntil", "Days until lift"),
    ("EmbargoLiftPublication", "Publication"),
]


# Placeholder defaults set by the annotator when no value applies; shown blank.
_PLACEHOLDERS = {
    "No publication assigned.",
    "No PMID assigned.",
    "No DOI assigned.",
    "No Assigned Date",
    "Unknown",
}


def _md_escape(value) -> str:
    """Escape a value for safe display inside a Markdown table cell."""
    if pd.isna(value):
        return ""
    text = str(value)
    if text in _PLACEHOLDERS:
        return ""
    # Pipes break table columns; newlines break rows.
    text = text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return text.strip()


def _markdown_table(rows, headers) -> str:
    """Build a GitHub-flavored Markdown table from rows (list of lists)."""
    out = "| " + " | ".join(headers) + " |\n"
    out += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in rows:
        out += "| " + " | ".join(_md_escape(cell) for cell in row) + " |\n"
    return out


def _is_vertebrate(df) -> pd.Series:
    """Boolean mask for vertebrate rows (taxid 7742 in the Lineage path)."""
    if "Lineage" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df["Lineage"].astype(str).str.contains(";7742;")


def build_dashboard_markdown(df, today=None, repo_url=REPO_URL) -> str:
    """Return the Markdown text for the embargo dashboard."""
    if today is None:
        today = pd.Timestamp.today()
    today_string = today.strftime("%Y-%m-%d")

    is_embargoed = df["Embargo"].isin(["Embargoed", "Embargo Ambiguous"])
    embargoed = df[is_embargoed].copy()
    vert_mask = _is_vertebrate(df)

    n_total = len(df)
    n_embargoed = int(is_embargoed.sum())
    n_embargoed_vert = int((is_embargoed & vert_mask).sum())
    n_not_embargoed = int((df["Embargo"] == "Not Embargoed").sum())
    n_vert = int(vert_mask.sum())

    t = "# Embargoed Genome Assemblies Dashboard\n\n"
    t += "This page is generated automatically by "
    t += "[genbargo]({}). ".format(repo_url)
    t += "It summarises the embargo status of genome assemblies deposited at "
    t += "NCBI/ENA, based on the data-use policies of the submitting projects.\n\n"
    t += "**Last updated:** {}\n\n".format(today_string)

    t += "## Summary\n\n"
    t += "| Metric | Count |\n| --- | --- |\n"
    t += "| Assemblies analysed | {} |\n".format(n_total)
    t += "| Currently embargoed | {} |\n".format(n_embargoed)
    t += "| &nbsp;&nbsp;of which vertebrate (taxid 7742) | {} |\n".format(n_embargoed_vert)
    t += "| Not embargoed | {} |\n".format(n_not_embargoed)
    t += "| Vertebrate assemblies total | {} |\n".format(n_vert)
    t += "\n"

    # Counts of embargoed genomes by policy.
    if n_embargoed > 0:
        t += "## Embargoed assemblies by policy\n\n"
        policy_counts = embargoed["EmbargoPolicy"].value_counts()
        rows = [[policy, int(count)] for policy, count in policy_counts.items()]
        t += _markdown_table(rows, ["Policy", "Count"])
        t += "\n"

        # Counts of embargoed genomes by submitter.
        t += "## Embargoed assemblies by submitter\n\n"
        submitter_counts = embargoed["Assembly Submitter"].value_counts()
        rows = [[sub, int(count)] for sub, count in submitter_counts.items()]
        t += _markdown_table(rows, ["Submitter", "Count"])
        t += "\n"

    # Table of currently embargoed genomes, soonest lift first.
    t += "## Currently embargoed assemblies\n\n"
    if n_embargoed == 0:
        t += "_No assemblies are currently under embargo._\n"
        return t

    if "EmbargoDaysUntil" in embargoed.columns:
        embargoed = embargoed.sort_values(by="EmbargoDaysUntil", ascending=True)

    headers = [h for _, h in _DASHBOARD_COLUMNS]
    rows = []
    for _, row in embargoed.iterrows():
        rows.append([row.get(col, "") for col, _ in _DASHBOARD_COLUMNS])
    t += "Sorted by soonest embargo-lift date. "
    t += "A negative *Days until lift* means the embargo has already passed.\n\n"
    t += _markdown_table(rows, headers)
    return t


def write_markdown_dashboard(df, dashboard_dir, today=None, repo_url=REPO_URL):
    """Write ``README.md``, ``embargoed.tsv`` and ``all.tsv`` to ``dashboard_dir``.

    Returns the path to the written Markdown file.
    """
    os.makedirs(dashboard_dir, exist_ok=True)

    markdown = build_dashboard_markdown(df, today=today, repo_url=repo_url)
    md_path = os.path.join(dashboard_dir, "README.md")
    with open(md_path, "w") as f:
        f.write(markdown)

    # Machine-readable companions to the dashboard.
    is_embargoed = df["Embargo"].isin(["Embargoed", "Embargo Ambiguous"])
    df.to_csv(os.path.join(dashboard_dir, "all.tsv"), sep="\t", index=False)
    df[is_embargoed].to_csv(
        os.path.join(dashboard_dir, "embargoed.tsv"), sep="\t", index=False
    )
    return md_path
