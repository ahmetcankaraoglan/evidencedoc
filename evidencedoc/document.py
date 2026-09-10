"""Immutable source spans. All boxes use top-left normalized page coordinates."""
import io
import os
from collections import defaultdict

import pymupdf as fitz
from PIL import Image, ImageOps, UnidentifiedImageError
import pytesseract

MAX_PAGES = 12
MAX_PIXELS = 20_000_000


def ocr_lines(image, page_number):
    data = pytesseract.image_to_data(image, lang=os.getenv("OCR_LANGUAGE", "eng"),
                                     output_type=pytesseract.Output.DICT, timeout=45)
    groups = defaultdict(list)
    for i, text in enumerate(data["text"]):
        if text.strip() and float(data["conf"][i]) >= 0:
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            groups[key].append(i)
    lines = []
    for indices in groups.values():
        x0 = min(data["left"][i] for i in indices)
        y0 = min(data["top"][i] for i in indices)
        x1 = max(data["left"][i] + data["width"][i] for i in indices)
        y1 = max(data["top"][i] + data["height"][i] for i in indices)
        lines.append({"text": " ".join(data["text"][i] for i in indices),
                      "bbox": [x0/image.width, y0/image.height, x1/image.width, y1/image.height],
                      "page": page_number, "source": "tesseract",
                      "ocr_confidence": round(min(float(data["conf"][i]) for i in indices)/100, 3)})
    return lines


def ingest(content: bytes, directory):
    pages, spans = [], []
    try:
        if content.startswith(b"%PDF-"):
            doc = fitz.open(stream=content, filetype="pdf")
            if doc.needs_pass:
                raise ValueError("Password-protected PDFs are not supported. Export an unlocked copy.")
            if not 1 <= len(doc) <= MAX_PAGES:
                raise ValueError(f"Upload 1–{MAX_PAGES} pages.")
            for n, page in enumerate(doc, 1):
                if page.rotation:
                    page.remove_rotation()
                scale = min(2, 1800 / max(page.rect.width, page.rect.height))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                lines = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(s["text"] for s in line["spans"]).strip()
                        if text:
                            x0, y0, x1, y1 = line["bbox"]
                            lines.append({"text": text, "bbox": [x0/page.rect.width, y0/page.rect.height,
                                          x1/page.rect.width, y1/page.rect.height], "page": n,
                                          "source": "pdf-text", "ocr_confidence": None})
                if not lines:
                    lines = ocr_lines(image, n)
                save_page(image, lines, n, directory, pages, spans)
            doc.close()
        else:
            image = Image.open(io.BytesIO(content))
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image exceeds 20 megapixels.")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1800, 2400))
            save_page(image, ocr_lines(image, 1), 1, directory, pages, spans)
    except (fitz.FileDataError, UnidentifiedImageError) as exc:
        raise ValueError("Upload a readable PDF, PNG or JPEG.") from exc
    if len(spans) > 1800 or sum(len(s["text"]) for s in spans) > 100_000:
        raise ValueError("Document text exceeds the demo limit. Upload a shorter document.")
    return {"pages": pages, "spans": spans}


def save_page(image, lines, n, directory, pages, spans):
    image.save(directory / f"page-{n}.png")
    pages.append({"number": n, "width": image.width, "height": image.height,
                  "source": "tesseract" if any(l["source"] == "tesseract" for l in lines) else "pdf-text"})
    for line in lines:
        line["id"] = f"p{n}-s{len(spans)+1}"
        line["bbox"] = [round(max(0, min(1, x)), 6) for x in line["bbox"]]
        spans.append(line)
