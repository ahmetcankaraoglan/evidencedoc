# Contest and model review — September 10, 2026

The official entry window is August 18–September 10, 2026. The entry page and official rules do not specify a cutoff hour or timezone. September 10 is therefore the stated last date, but an exact number of remaining hours cannot be established from those sources.

Entry requires an open-source application, the applicable judge's entry requirements, a social post on LinkedIn/X/Instagram with #NVIDIAGTC and the relevant judge/channel tag. The user heard about the challenge from Merve Noyan. NVIDIA's four equally weighted criteria are technical innovation, effective NVIDIA/partner technology use, usefulness/impact and documentation/presentation. Partner judges may use their own criteria. There is no model-count scoring requirement or exclusive model whitelist in the general rules reviewed.

Sources:
- https://developer.nvidia.com/gtc-golden-ticket-contest
- https://developer.download.nvidia.com/licenses/gtc-berlin-golden-ticket-official-rules-for-2026.pdf

## Candidate additions — recommendations, not implemented capabilities

1. Nemotron OCR v2: text detection, recognition and layout relations, with bounding boxes and confidence. Useful for real scanned documents and more precise OCR geometry. The model card's multilingual variant lists English, Chinese, Japanese, Korean and Russian; Turkish support must not be assumed.
   https://build.nvidia.com/nvidia/nemotron-ocr-v2/modelcard
2. NVIDIA Nemotron Parse 2.0: document layout classes, reading order, text and bounding boxes, plus improved table/chart parsing. This is the strongest candidate for extracting structured evidence from charts and tables. The NVIDIA model card lists an August 3, 2026 release. Do not assume the existing hosted `nemotron-parse` endpoint is Parse 2.0; runtime/API availability must be checked before integration.
   https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-2.0
3. Llama Nemotron Embed VL 1B v2 and a Nemotron reranker: useful if the application expands to retrieval across many documents and visual pages. They add less value to the current small-document reader than OCR/Parse improvements.
   https://build.nvidia.com/nvidia/llama-nemotron-embed-vl-1b-v2/modelcard
   https://build.nvidia.com/nvidia/llama-nemotron-rerank-1b-v2/modelcard

Our recommendation is to validate one extraction improvement on public documents rather than expand the stack purely to list more model names. These model uses appear consistent with the general open-model challenge, subject to their licenses and the judge's requirements; this is not a promise of contest acceptance.
