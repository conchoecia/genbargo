# Embargo policies encoded in genbargo

genbargo assigns an embargo status to each genome assembly based on the
data-use policy of the submitting project, keyed on the NCBI/ENA
`Assembly Submitter` field (and, for the Wellcome Sanger Institute, on
membership in the Sanger 25 Genomes Project). This document records the
policies, their provenance, and how each is applied. Copies of the source
policy documents are in [`../embargo_policies/`](../embargo_policies/).

The logic lives in [`../genbargo/embargo.py`](../genbargo/embargo.py).

## Summary of policy application

| Policy | Applies to (submitter) | Embargo |
| --- | --- | --- |
| VGP / G10K | Vertebrate Genomes Project, Bat1K, Bird10K, G10K, Genome 10K, Human Pangenome Reference Consortium, Telomere-to-Telomere Consortium, Leibniz Institute for Zoo and Wildlife Research | 2 yr (pre 2024-05-01) / 1 yr (on-or-after 2024-05-01) from release; lifted early on publication |
| Darwin Tree of Life | Wellcome (Trust) Sanger Institute assemblies **not** in the Sanger 25 project | None (open on deposition) |
| Sanger 25 Genomes | Wellcome Sanger assemblies listed in `assembly_specifications/Sanger_25_genomes.tsv` | VGP embargo (see above) |
| DNA Zoo | DNA Zoo | None; requests citation of Dudchenko et al. 2017 |
| Unknown | anything else | Not embargoed, unless the BioSample comment contains "embargo" |

## VGP / G10K embargo

- Old policy: <https://genome10k.ucsc.edu/data-use-policies/>
- New policy: <https://vertebrategenomesproject.org/data-use-policies>
- Embargo length: **2 years** from the assembly release date for assemblies
  released before **2024-05-01**; **1 year** for assemblies released on or after
  that date.
- If the assembly is annotated and the annotation was released **within** the
  embargo window, the clock runs from the annotation release date instead of the
  assembly release date.
- **Publication lifts the embargo.** The 2018 policy
  ([`../embargo_policies/VGP_20180109.txt`](../embargo_policies/VGP_20180109.txt))
  states that assemblies "will be considered released from this embargo when they
  are expressly published by members of the VGP or if released by a G10K
  announcement." genbargo therefore lifts the embargo on any VGP assembly for
  which it finds a publication (see [publications](#publication-linking)).
- The `--conservative` flag doubles the window for **unannotated** assemblies
  (4 yr / 2 yr) to guard against a spreadsheet generated before an annotation
  was released within the lapse window, and flags any assembly whose BioSample
  comment mentions "embargo" as `Embargo Ambiguous`.

### Projects under the VGP/G10K umbrella

The VGP 2024 page lists many affiliated projects. Those observed as NCBI/ENA
`Assembly Submitter` values and mapped to the VGP embargo are: Vertebrate
Genomes Project, Bat1K, Bird10K, G10K, Genome 10K, Human Pangenome Reference
Consortium, Telomere-to-Telomere Consortium, and the Leibniz Institute for Zoo
and Wildlife Research (elephant genome, submitted 2025-08-11). Affiliated
projects for which no distinct submitter string has been observed (EBP, ERGA,
GIGA, Paratus, Cetacean Genomes, CBP, AfricaBP, Minderoo, AmaZOOmics, California
Conservation Genomes, EBP-Colombia, Canadian Biogenome, Revive & Restore,
Colossal, Allen Institute, CZI, Tabula Madagascar, HHMI) are not yet mapped;
add them to `VGP_POLICY_SUBMITTERS` in `embargo.py` if/when they appear.

## Darwin Tree of Life (DToL)

- Policy: <https://www.darwintreeoflife.org/> (open data release policy v1.04).
- DToL data are released freely for reuse on deposition in ENA; there is no
  embargo. Most Wellcome (Trust) Sanger Institute assemblies fall here.

## Sanger 25 Genomes Project

- Website: <https://www.sanger.ac.uk/collaboration/25-genomes-for-25-years/>
- NCBI BioProject: PRJEB33226. This is a **separate** project from DToL and
  falls under the VGP embargo. Because both use the "Wellcome Sanger Institute"
  submitter string, the Sanger 25 assemblies are identified explicitly by
  accession in
  [`../assembly_specifications/Sanger_25_genomes.tsv`](../assembly_specifications/Sanger_25_genomes.tsv).

## DNA Zoo

- Policy: <https://www.dnazoo.org/usage>
  ([`../embargo_policies/DNAzoo_20241210.pdf`](../embargo_policies/DNAzoo_20241210.pdf)).
- "All DNA Zoo data ... are shared freely without any restriction." No embargo.
  The authors request citation of Dudchenko et al. 2017
  (doi:10.1126/science.aal3327, PMID 28336562) for unannotated assemblies.

## Publication linking

An assembly under the VGP embargo is released early once it has been published.
genbargo finds these publications from two sources (manual wins over automatic):

1. **Manual** — `assembly_specifications/publications_manual.tsv`, a curated
   table of `Assembly Accession -> PMID/DOI/Publication/PublicationDate` for
   consortium papers and pre-prints (e.g. large VGP releases) that the NCBI
   cross-references do not yet capture.
2. **Automatic** — NCBI Entrez lookups (assembly → BioProject → PubMed →
   DOI/title/date), cached in `assembly_specifications/publications_cache.tsv`
   so weekly runs only query newly-embargoed accessions.

See [`../genbargo/publications.py`](../genbargo/publications.py).
