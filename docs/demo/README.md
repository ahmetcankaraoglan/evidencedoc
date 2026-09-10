# EvidenceDoc: real-source GTC demo kit

Two English demo videos are available in [Releases](https://github.com/ahmetcankaraoglan/evidencedoc/releases/latest): **EvidenceDoc-GTC-full-demo.mp4** (about 3:03) and **EvidenceDoc-GTC-social-cut.mp4** (about 2:01). Both have English neural narration, burned-in English captions, and separate `.en.srt` subtitle files. The shorter cut emphasizes discovery, source navigation, graph, comparison and the source-removal experiment. The full cut also shows unsupported fields, scanned documents and export.

## Original English documents

| Document | Pages | Why it is in the demo |
|---|---:|---|
| [NVIDIA Q3 FY2026 results](https://nvidianews.nvidia.com/_gallery/download_pdf/691e34d93d633290a88deeef/) | 10 | Baseline for revenue, margins, earnings and dividend dates. |
| [NVIDIA Q4 and FY2026 results](https://nvidianews.nvidia.com/_gallery/download_pdf/699f6ab43d6332ccaa689907/) | 11 | Entity discovery, bounding boxes, source navigation, graph, comparison, unsupported-field behavior and Evidence Lab. |
| [World Bank / IDA grant agreement TF051711](https://documents1.worldbank.org/curated/en/549511516120883931/pdf/Grant-Agreement-TF051711.pdf) | 10 | Original scanned English agreement, financial amounts and cross-page evidence; a saved run includes Nemotron Super and Nemotron Omni calls. |

The three PDFs in `data/` are unchanged source downloads. `data/manifest.json` contains original URLs, SHA-256 hashes, language, page counts and local result IDs. All source hashes match the documents attached to their recorded model results. These documents remain subject to their publishers' rights; project code licensing does not relicense third-party PDFs.

## Recorded outcomes

- Q3 quarterly revenue: **$57.0 billion**. Q4: **$68.1 billion**. Both are anchored to the original text.
- Dividend per share: **$0.01** in both reports.
- Q4 dividend payment date: **April 1, 2026**.
- `external_auditor_name`: no supported value in the recorded reviews. This is a requested field, not an invented document value.
- Automatic Q4 understanding discovered **256 entities** and proposed 12 fields in this run. The model-assigned categories and roles are interpretations; this is not a claim of complete entity recall.
- Comparison of the consistent 10-field reviews reports **7 changed**, **2 same-text** and **1 needing context**.
- The recorded source-removal experiment withheld two overlapping source regions. A fresh NVIDIA call returned **no supported answer** for the dividend payment date. The original PDF is unchanged. The masked page in `evidence/` is labeled as an experimental copy.
- The scanned World Bank run uses `nvidia/nemotron-3-super-120b-a12b` and `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`. Omni was called for a crop retry on `loan_interest_rate`; the video does not establish that the grant amount was extracted by Omni.

Actual result JSON, discovery output, comparison fields and the source-removal outcome are in `evidence/`. They contain public-document data only. No credentials, private uploaded documents, fabricated invoice samples or manually substituted model answers are included.

## Reproduce in the local app

1. Open the app and upload `data/nvidia-q4-fy2026.pdf` with automatic understanding enabled to repeat discovery. A rerun may return a different number of entities and different suggested fields.
2. For a like-for-like comparison, analyze Q3 and Q4 using the names in `fields.json` with NVIDIA mode. The recorded comparison uses these explicit fields, while the discovery scene shows the separate automatically proposed schema.
3. Open the Q4 review, select **Evidence lab → Dividend payment date → Withhold & re-evaluate**. Inspect the observed result and masked page. Future runs may differ.
4. Use the scanned agreement to explore image-region retries and multi-page source navigation.

The video is edited from actual UI screen captures. Pauses are shortened or held for narration, cuts join separate recorded interactions, and headings/captions are added in post-production. It is not a real-time speed benchmark. Narration is AI-generated with the standard Andrew multilingual English voice. No voice cloning, generated document data, stock footage or background music is used.

## Entry preparation

The [official contest page](https://developer.nvidia.com/gtc-golden-ticket-contest) asks for a short video or project link, the judge who introduced the challenge, and `#NVIDIAGTC`. Its listed entry period ends September 10, 2026. Merve's official linked X account is [@mervenoyann](https://x.com/mervenoyann). `social-posts.md` contains drafts; nothing has been posted. The public project is https://github.com/ahmetcankaraoglan/evidencedoc.
