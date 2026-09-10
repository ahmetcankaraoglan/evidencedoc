# Real-document evaluation

Six public documents, 36 pages and 49 predefined field decisions were evaluated on September 9, 2026. The final development run matched 44 of 49 expected decisions, including all nine expected abstentions. The same documents were reused during fixes; this is not an independent benchmark or a general accuracy claim.

Source text matching does not establish semantic correctness. Handwriting, table context, OCR errors and model variability remain limitations. Source values retain the document's original language.

The interactive report lists expected and actual values, source PDF links and all run summaries: [Open evaluation report](real-evaluation.html).

Reproduction from the repository: run `scripts/fetch_real_documents.py`, followed by `scripts/evaluate_real.py --help` for options. Public-source manifests and model responses are stored in `evaluation/`. Credentials are not included.
