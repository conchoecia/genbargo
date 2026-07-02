# Handoff: publication curation for genbargo

## Who this is for

You are an autonomous research agent (e.g. Codex). Your job is **manuscript
research**: for each embargoed genome assembly, determine whether that genome has
been **published**, find the specific paper that published it, and record it in
`assembly_specifications/publications_manual.tsv`.

This is deliberately manual, per-assembly work. The payoff is permanent: once a
genome's publishing paper is recorded, genbargo lifts its embargo and never looks
it up again.

## Why it matters

Most embargoed assemblies fall under the Vertebrate Genomes Project (VGP) /
G10K data-use policy. That policy
([`../embargo_policies/VGP_20180109.txt`](../embargo_policies/VGP_20180109.txt))
says a genome is *"considered released from this embargo when [it is] expressly
published by members of the VGP or if released by a G10K announcement."* So a
genome can leave embargo two ways: (a) the time-based embargo lapses (genbargo
already computes this), or (b) **it gets published** — which is what you find.

## What counts as "published" (decision rules)

Record a paper only if it is **the paper that published/announced that specific
assembly** by the data producers. Use these rules:

- **YES** — a genome note, assembly announcement, or consortium paper that
  presents that assembly (its accession appears in the paper, its data-
  availability section, or its supplement). Examples: a VGP flagship paper
  listing many `GCA_` accessions; a Wellcome Open Research genome note.
- **YES** — a **pre-print** (bioRxiv, etc.). The VGP policy explicitly treats
  pre-prints, conference talks, and press releases as "first presentation", so
  a bioRxiv paper by the producers that presents the genome counts.
- **NO** — a paper that merely **uses** the genome as a mapping reference, or
  analyses a single locus / gene family (the policy carves these out as
  allowed non-embargoed uses). These do **not** publish the genome.
- **NO** — a paper about a *different* assembly of the same species. Match the
  assembly, not just the species.
- **If unsure, do not record it.** A wrong entry silently un-embargoes a genome.
  Leave it out and note the uncertainty (see "When you can't decide").

Pick the **earliest** qualifying paper (that is the one that released the
embargo). One paper often publishes **many** assemblies (consortium papers) —
add one row per assembly it covers.

## Inputs: the worklist

Work from the list of currently-embargoed assemblies. Generate it with:

```bash
# produces output/spreadsheet_genomes_embargoed_<date>_fewerColumns.tsv
genbargo scrape --taxon 7742 --outdir input        # 7742 = Vertebrata (VGP focus)
genbargo filter -t input/7742_<date>.tsv -c -d output
```

Useful columns in that spreadsheet for your research:
`Assembly Accession`, `Organism Name`, `Organism Common Name`,
`Assembly Submitter`, `Assembly BioSample BioProject Accession`,
`Assembly Release Date`, `EmbargoLiftDate`.

Before researching an accession, **skip it if it already appears** in either
`assembly_specifications/publications_manual.tsv` or
`assembly_specifications/publications_cache.tsv` — it has already been handled.

## Research procedure (per assembly)

Try these sources, in roughly this order, and stop when you have a confident
match. Always confirm the paper actually references the assembly accession.

1. **Europe PMC accession cross-reference** (best signal, no key needed):
   ```
   https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<ACCESSION>&format=json&resultType=core
   ```
   Also try the base accession without the version (`GCA_012345678`, not
   `.1`). Europe PMC indexes which articles cite a GCA/GCF accession.
2. **NCBI Entrez** — assembly → BioProject → PubMed:
   - `esearch db=assembly term=<ACCESSION>` → assembly UID
   - `esummary db=assembly id=<uid>` → `PubMedIds`, `GB_BioProjects`
   - `esummary db=pubmed id=<pmids>` → title, DOI, date
   - You can also `elink` from the BioProject to PubMed.
   (This is what `genbargo pubs` automates to seed candidates into the cache —
   run it first, then verify each candidate by hand.)
3. **BioProject page** — check the NCBI/ENA BioProject for a linked publication.
4. **Targeted literature search** — organism name + "genome" / "chromosome-level
   assembly" / "genome note"; check bioRxiv, Wellcome Open Research, GigaScience,
   Scientific Data, and the submitter's project site.

**Confirmation step (required):** open the candidate paper and verify the
assembly accession (or its BioProject) is named in the text, figures, tables,
data-availability, or supplement. Species match alone is not enough.

## Output: how to record a hit

Append one row per assembly to
`assembly_specifications/publications_manual.tsv` (tab-separated). Columns:

| Column | What to put |
| --- | --- |
| `Assembly Accession` | the exact accession, with version, e.g. `GCA_012345678.1` |
| `PMID` | PubMed ID if any (blank for pre-prints without one) |
| `DOI` | DOI, e.g. `10.1101/2026.01.02.123456` (bare DOI, no URL) |
| `Publication` | short citation: first author, year, title/journal |
| `PublicationDate` | ISO date `YYYY-MM-DD` (used as the embargo-lift date) |
| `Source` | `manual` |
| `LastChecked` | the date you researched it, `YYYY-MM-DD` |

Rules:
- At least one of `PMID` / `DOI` must be present (that is what triggers the
  lift). `Publication` and `PublicationDate` are strongly recommended —
  `PublicationDate` sets the recorded embargo-lift date, so use ISO format.
- Do **not** add a row for "no paper found." Negative results are handled by the
  automatic cache; the manual table is for confirmed publications only.
- For a consortium paper covering many accessions, add one row per accession with
  the same PMID/DOI/Publication/PublicationDate.

### Example rows

```
Assembly Accession	PMID	DOI	Publication	PublicationDate	Source	LastChecked
GCA_012345678.1	38123456	10.1038/s41586-025-00000-0	Rhie et al. 2025, "..." Nature	2025-03-14	manual	2026-07-02
GCA_023456789.2		10.1101/2026.01.02.123456	Smith et al. 2026 bioRxiv genome note	2026-01-02	manual	2026-07-02
```

## Known high-value target

The **2026 VGP bioRxiv paper** is expected to publish a large batch of VGP
assemblies at once. Find it, extract its accession list (main text +
supplement), and bulk-add one row per accession. This likely lifts many
embargoes in a single pass — do it first.

## When you can't decide

- If a candidate is plausible but unconfirmed, **do not** put it in the manual
  table. Instead note it (accession, candidate DOI, why you're unsure) in a
  separate `docs/publication_curation_notes.md` for a human to adjudicate.
- Never guess a PMID/DOI. An incorrect entry un-embargoes a genome that may still
  be embargoed.

## Validate your work

After editing the table, confirm the pipeline still runs and picks up your
entries:

```bash
python -m pytest tests/ -q            # logic still passes
genbargo filter -t input/7742_<date>.tsv -c -d output   # re-run
# then check output/spreadsheet_genomes_notembargoed_*.tsv:
#   assemblies you curated should now show Embargo = "Not Embargoed"
#   with your Publication / EmbargoLiftPublicationDOI filled in.
```

Keep `assembly_specifications/publications_manual.tsv` sorted/clean and commit in
reasonably sized batches with plain messages (no AI attribution).

## Notes

- Entrez needs a contact email; the pipeline reads it from the `ENTREZ_EMAIL`
  environment variable (a repo secret in CI). Set it in your shell before running
  `genbargo pubs`. An `NCBI_API_KEY` env var is optional and raises the rate
  limit from 3 to 10 requests/second.
- Match assemblies on the accession including version when possible, but a paper
  that names the base accession (no `.N`) still counts.
