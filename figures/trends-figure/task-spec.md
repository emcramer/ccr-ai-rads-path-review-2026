# Task Specification for Trends Analysis

## Goal

To create a figure for the CCR review manuscript that displays the recent trends in AI for pathology and radiology research. The figure will show how different _themes_ in the research literature have leveraged different _modalities_ of data, and how they have evolved over time. This is focused on topics and semantics - how has the literature evolved in terms of number of papers that are exploring each theme (topic), and what methods (modalities) they are using to explore those themes. The goal is to see how these are evolving over time, and which themes are most closely tied to each topic.  

**Themes:**

1. Foundation Models
2. Multimodal Integration
3. Digital Twins
4. Clinical Applications/FDA Approval

**Modalities:**

| Modality Name | Modality Type |
|---|---|
| Hematoxylin and Eosin (H&E) or Histology | Imaging| 
| Pathology Report | Text |
| Radiology Report | Text |
| Spatial Proteomics | Imaging |
| Spatial Transcriptomics | Imaging |
| Magnetic Resonance Imaging (MRI) | Imaging |
| Computed Tomography (CT) | Imaging |
| Ultrasound | Imaging |
| Immunohistochemistry (IHC) | Imaging |
| Other | All other modalities |  

_Table 1_. Modalities covered in this review and the type of data they produce.

The analysis will focus on using the published literature accessible through the PubMed API using structured and reproducible queries.


**To Do:**

1. Generate structured queries to pull the paper titles and their abstracts that match the terms of the themes and modalities in table 1.
2. Query PubMed API to get paper titles and abstracts.
3. Categorize papers according to the themes they discuss and which modalities they use.
4. Generate figure based on results.

## Figure Layout

![](figure_mockup.jpg)

## Rules

1. Make everything reproducible and follow all best practices for coding style, software engineering project organization, data provenance, keeping track of decision-making, etc.  
2. Answers must always be concise, clear, and direct. Avoid aphorisms. Follow writing conventions and rules set forth by Strunk and White in their book on writing, the Elements of Style.
3. Avoid jargon and define key terms as necessary when communicating. Keep communication professional and academic.  
4. Keep workspace tidy. Don't clutter with unnecessary files and use proper directory structure for easy organization.  
5. Document all code appropriately and keep a code book and data dictionary that describes the purpose and use of every file.  