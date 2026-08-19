# genbargo

This collection of scripts calculates the embargo status of a genome assembly based on known embargos.

Currently, this script annotates the following:

Embargo Policies:

- Vertebrate Genomes Project/G10K Embargo Policy:
  - Old Policy Website: https://genome10k.ucsc.edu/data-use-policies/
  - New Policy Website: https://vertebrategenomesproject.org/data-use-policies
  - Embargo: 2 years from the assembly release date for things prior to May 1st, 2024. 1 year for things after May 1st, 2024.
  - Projects that fall under the VGP/G10K policy:
    - Vertebrate Genomes Project (VGP)
      - Website: https://vertebrategenomesproject.org
      - Submitting genomes to NCBI/ENA as: "Vertebrate Genomes Project"
    - Bat1K
      - Website: https://bat1k.com/
      - Embargo: Same as the VGP embargo, specified in the 2018 VGP embargo page.
      - Submitting genomes to NCBI/ENA as: "Bat1k"
    - Bird10K
      - Website: https://b10k.genomics.cn/
      - Embargo: Same as the VGP embargo, specified in the 2018 VPG embargo page.
      - Submitting genomes to NCBI/ENA as: "Bird10K"
    - Kakapo projects
      - Website: Unknown, December 3rd, 2024
      - Embargo: Same as the VGP embargo, specified in the 2018 VPG embargo page.
      - "Assembly Submitter" values: None found, but the 2018 page specifies that there are Kakapo projects under the VGP umbrella
    - G10K project - https://genome10k.ucsc.edu/data-use-policies/
      - Website: https://genome10k.ucsc.edu/data-use-policies/
      - Embargo: Same as the VGP embargo, specified in the 2018 VPG embargo page.
      - Submitting genomes to NCBI/ENA as: "G10K", "Genome 10K"
    - Global Invertebrate Genomics Alliance (GIGA)
      - Website: http://www.gigacos.org/
      - Embargo: GIGA is listed on the 2024 VGP/G10K website under the section of "contributing, affiliated projects." No embargo is specified on the GIGA website on access date of Tuesday, December 3rd, 2024.
      - Submitting genomes to NCBI/ENA as: We did not find GIGA as a ENA/NCBI genome submitter in the "Assembly Submitter" field in our list of chromosome-scale genomes as of December 3rd, 2024.
    - Earth BioGenome Project (EBP)
      - Website: https://www.earthbiogenome.org/
      - Embargo: The EBP is listed on the 2024 VGP/G10K website under the section of "contributing, affiliated projects." No embargo specified on the EBP website on access date of Tuesday, December 3rd, 2024.
      - Submitting genomes to NCBI/ENA as: We did not find EBP, Earth BioGenome Project, or similar searches as a ENA/NCBI genome submitter in the "Assembly Submitter" field in our list of chromosome-scale genomes as of December 3rd, 2024.

    # To Determine
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

## Citing genbargo

If you use `genbargo` in your work, please cite the following paper:

> Schultz, D.T., Blümel, A., Destanović, D., Sarigol, F., & Simakov, O. (2026).
> Topological mixing and irreversibility in animal chromosome evolution.
> *Science Advances*, **12**(34), eadz5561.
> [https://doi.org/10.1126/sciadv.adz5561](https://doi.org/10.1126/sciadv.adz5561)

See also [`CITATION.cff`](CITATION.cff).
