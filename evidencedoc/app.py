"""Local desktop service. Bind to loopback; public hosting requires authentication."""
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, SecretStr

from .document import ingest
from .pipeline import DEFAULT_FIELDS, run_pipeline
from .provider import ProviderError
from .stress import run_stress
from .discovery import discover_entities

ROOT = Path(os.getenv("EVIDENCEDOC_PROJECT_DIR", str(Path.cwd()))).resolve()
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("EVIDENCEDOC_DATA_DIR", str(ROOT / "data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
STATIC = Path(__file__).parent / "static"
app = FastAPI(title="EvidenceDoc", version="0.5.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
pool = ThreadPoolExecutor(max_workers=2)
jobs = {}
lock = threading.Lock()
slots = threading.BoundedSemaphore(4)
stress_jobs = {}
entity_jobs = {}
MAX_UPLOAD = 20 * 1024 * 1024


@app.middleware("http")
async def same_origin(request: Request, call_next):
    host = request.url.hostname
    if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        return JSONResponse({"detail": "This demo only accepts loopback hosts."}, status_code=403)
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        if urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


def folder(identifier):
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise HTTPException(404, "Document not found.")
    path = DATA / identifier
    if not path.is_dir():
        raise HTTPException(404, "Document not found.")
    return path


def load_document(identifier):
    path = folder(identifier)
    if not (path / "document.json").exists():
        raise HTTPException(404, "Document not found.")
    return json.loads((path / "document.json").read_text())


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def config():
    return {"nvidia_configured": bool(os.getenv("NVIDIA_API_KEY")),
            "model": os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            "default_fields": DEFAULT_FIELDS, "max_pages": 12,
            "samples": [], "public_documents": public_documents()}


class KeySettings(BaseModel):
    api_key: SecretStr


@app.post("/api/settings/nvidia")
def configure_nvidia(settings: KeySettings):
    key = settings.api_key.get_secret_value().strip()
    if not key.startswith("nvapi-") or not 20 <= len(key) <= 512:
        raise HTTPException(422, "Enter a valid NVIDIA API key beginning with nvapi-.")
    # Session-only; never return, persist, or log the key.
    os.environ["NVIDIA_API_KEY"] = key
    return {"configured": True, "message": "Key stored in server memory until restart. Select NVIDIA mode to use it."}


def process(identifier, content, filename, fields, mode, fault, discover=False):
    path = DATA / identifier
    started = time.monotonic()
    try:
        with lock:
            jobs[identifier] = {"status": "reading", "message": "Reading pages and locating source text…"}
        document = ingest(content, path)
        document.update({"id": identifier, "filename": filename, "sha256": hashlib.sha256(content).hexdigest()})
        (path / "document.pending").write_text(json.dumps(document, ensure_ascii=False))
        (path / "document.pending").replace(path / "document.json")
        atlas = None
        if discover:
            def discovery_progress(done, total):
                with lock:
                    jobs[identifier] = {'status':'discovering','message':f'Nemotron analyzed {done}/{total} pages. Anchoring discovered entities…', 'pages_done':done,'pages_total':total}
            with lock:
                jobs[identifier] = {'status':'discovering','message':'Nemotron is identifying the document type, entities and useful extraction fields…'}
            atlas = discover_entities(document, path, progress=discovery_progress)
            (path / 'entities.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=2))
            fields = atlas['suggested_fields'] or ['document_title']
        with lock:
            jobs[identifier] = {"status": "verifying", "message": "Extracting fields and checking evidence…"}
        result = run_pipeline(document, fields, mode, path, fault)
        result["pipeline_elapsed_seconds"] = result["elapsed_seconds"]
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        result.update({"document": document, "schema_version": "1.0"})
        if atlas:
            result['discovery'] = {k:v for k,v in atlas.items() if k not in {'entities','model_calls'}}
            result['entity_count'] = len(atlas['entities'])
        (path / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        with lock:
            jobs[identifier] = {"status": "complete", "message": "Evidence review complete."}
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ValueError, ProviderError)) else "Document processing failed. Check the local server log."
        if not isinstance(exc, (ValueError, ProviderError)):
            import traceback
            traceback.print_exc()
        with lock:
            jobs[identifier] = {"status": "failed", "message": message}
    finally:
        slots.release()


def submit(content, filename, fields, mode, fault=False, discover=False):
    if mode not in {"local", "nvidia"}:
        raise HTTPException(422, "Unknown extraction mode.")
    if mode == "nvidia" and not os.getenv("NVIDIA_API_KEY"):
        raise HTTPException(422, "NVIDIA_API_KEY is missing. Configure .env and restart.")
    if discover and mode != 'nvidia':
        raise HTTPException(422, 'Automatic entity discovery requires NVIDIA mode.')
    if (not fields and not discover) or len(fields) > 16 or len(set(fields)) != len(fields) or any(
        not isinstance(f, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", f) for f in fields):
        raise HTTPException(422, "Use 1–16 unique snake_case field names.")
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, "Upload a non-empty file under 20 MB.")
    if not slots.acquire(blocking=False):
        raise HTTPException(429, "The local queue is full. Wait for a current run to finish.")
    identifier = uuid.uuid4().hex
    path = DATA / identifier
    path.mkdir()
    (path / "source").write_bytes(content)
    with lock:
        jobs[identifier] = {"status": "queued", "message": "Waiting for a processing slot…"}
    pool.submit(process, identifier, content, Path(filename).name[:150], fields, mode, fault, discover)
    return {"id": identifier}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), fields: str = Form(...), mode: str = Form("local"), discover: bool = Form(False)):
    try:
        names = json.loads(fields)
    except ValueError:
        raise HTTPException(422, "Fields must be a JSON array.")
    if not isinstance(names, list):
        raise HTTPException(422, "Fields must be a JSON array.")
    content = await file.read(MAX_UPLOAD + 1)
    return submit(content, file.filename or "document", names, mode, discover=discover)


def public_documents():
    return json.loads((Path(__file__).parent / 'public_documents/manifest.json').read_text())


@app.post('/api/public-documents/{name}')
def review_public_document(name: str, discover: bool = False):
    item = next((d for d in public_documents() if d['id'] == name), None)
    if item is None:
        raise HTTPException(404, 'Public document not found.')
    content = (Path(__file__).parent / 'public_documents' / item['filename']).read_bytes()
    if hashlib.sha256(content).hexdigest() != item['sha256']:
        raise HTTPException(409, 'Public document checksum mismatch.')
    return submit(content, item['filename'], item['fields'], 'nvidia', discover=discover)


@app.get("/api/jobs/{identifier}")
def job(identifier: str):
    folder(identifier)
    with lock:
        status = jobs.get(identifier)
    if status:
        return {**status, "preview_ready": (folder(identifier) / "document.json").exists()}
    if (folder(identifier) / "result.json").exists():
        return {"status": "complete", "message": "Saved result."}
    return {"status": "failed", "message": "This run was interrupted by a server restart. Start again."}


@app.get("/api/documents")
def list_documents():
    """Recent completed documents, with the latest review per filename."""
    paths = sorted(DATA.glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    documents, seen = [], set()
    for path in paths[:200]:
        if not re.fullmatch(r"[0-9a-f]{32}", path.parent.name):
            continue
        try:
            result = json.loads(path.read_text())
            document = result["document"]
            name = document["filename"]
            if name in seen:
                continue
            seen.add(name)
            documents.append({"id": path.parent.name, "filename": name, "pages": len(document["pages"]),
                              "mode": result["mode"], "requested": result["requested"],
                              "counts": result["counts"], "updated_at": path.stat().st_mtime})
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if len(documents) >= 20:
            break
    return {"documents": documents}


@app.get("/api/jobs/{identifier}/preview")
def job_preview(identifier: str):
    path = folder(identifier) / "document.json"
    if not path.exists():
        raise HTTPException(409, "Document preview is being prepared.")
    document = json.loads(path.read_text())
    return {key: document[key] for key in ('id', 'filename', 'pages', 'sha256')}


@app.get("/api/documents/{identifier}")
def result(identifier: str):
    path = folder(identifier) / "result.json"
    if not path.exists():
        raise HTTPException(409, "Result is not ready.")
    return FileResponse(path, media_type="application/json")


@app.get("/api/documents/{identifier}/export")
def export(identifier: str):
    path = folder(identifier) / "result.json"
    if not path.exists():
        raise HTTPException(409, "Result is not ready.")
    return FileResponse(path, filename="evidencedoc-evidence.json", media_type="application/json")


@app.get("/api/documents/{identifier}/pages/{number}")
def page(identifier: str, number: int):
    document = load_document(identifier)
    if number < 1 or number > len(document["pages"]):
        raise HTTPException(404, "Page not found.")
    return FileResponse(folder(identifier) / f"page-{number}.png", media_type="image/png")


@app.delete("/api/documents/{identifier}")
def delete(identifier: str):
    path = folder(identifier)
    with lock:
        if any(j.get('document_id') == identifier and j['status'] not in {'complete', 'failed'} for j in stress_jobs.values()):
            raise HTTPException(409, "Wait for the evidence experiment to finish before deleting.")
        if entity_jobs.get(identifier, {}).get('status') in {'queued','discovering'}:
            raise HTTPException(409, 'Wait for entity discovery to finish before deleting.')
        if jobs.get(identifier, {}).get("status") not in {None, "complete", "failed"}:
            raise HTTPException(409, "Wait for processing to finish before deleting.")
        jobs.pop(identifier, None)
    shutil.rmtree(path)
    return {"deleted": True}


class StressRequest(BaseModel):
    field: str
    span_ids: list[str]


def experiment_folder(identifier, test_id):
    if not re.fullmatch(r'[0-9a-f]{32}', test_id):
        raise HTTPException(404, 'Experiment not found.')
    path = folder(identifier) / 'experiments' / test_id
    if not path.is_dir():
        raise HTTPException(404, 'Experiment not found.')
    return path


def process_stress(identifier, test_id, original, field, span_ids):
    path = experiment_folder(identifier, test_id)
    try:
        with lock:
            stress_jobs[test_id] = {'status': 'verifying', 'document_id': identifier,
                                   'message': 'Withholding text and pixels. Running a fresh extraction…'}
        payload = run_stress(original, field, span_ids, folder(identifier), path)
        payload['id'] = test_id
        (path / 'result.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        status = {'status': 'complete', 'document_id': identifier, 'message': 'Source-removal experiment complete.'}
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ValueError, ProviderError)) else 'Experiment failed. Your original document is unchanged.'
        status = {'status': 'failed', 'document_id': identifier, 'message': message}
    finally:
        slots.release()
    (path / 'status.json').write_text(json.dumps(status))
    with lock:
        stress_jobs[test_id] = status


@app.post('/api/documents/{identifier}/stress-tests')
def start_stress(identifier: str, body: StressRequest):
    path = folder(identifier)
    if not (path / 'result.json').exists():
        raise HTTPException(409, 'Finish the original review first.')
    original = json.loads((path / 'result.json').read_text())
    field = next((f for f in original['fields'] if f['field'] == body.field), None)
    if not field or not field.get('value') or not field.get('evidence'):
        raise HTTPException(422, 'Choose a field with an answer and evidence.')
    if not body.span_ids or len(body.span_ids) > 32 or len(set(body.span_ids)) != len(body.span_ids) or not set(body.span_ids) <= {s['id'] for s in field['evidence']}:
        raise HTTPException(422, 'Select 1–32 unique cited evidence spans for this field.')
    if original['mode'] == 'nvidia' and not os.getenv('NVIDIA_API_KEY'):
        raise HTTPException(422, 'Connect NVIDIA in settings to run a fresh experiment.')
    if not slots.acquire(blocking=False):
        raise HTTPException(429, 'The processing queue is full. Try again shortly.')
    test_id = uuid.uuid4().hex
    experiment = path / 'experiments' / test_id
    experiment.mkdir(parents=True)
    with lock:
        stress_jobs[test_id] = {'status': 'queued', 'document_id': identifier, 'message': 'Preparing a separate masked copy…'}
    pool.submit(process_stress, identifier, test_id, original, body.field, body.span_ids)
    return {'id': test_id}


@app.get('/api/documents/{identifier}/stress-tests/{test_id}')
def stress_result(identifier: str, test_id: str):
    path = experiment_folder(identifier, test_id)
    if (path / 'result.json').exists():
        return {'status': 'complete', 'result': json.loads((path / 'result.json').read_text())}
    with lock:
        status = stress_jobs.get(test_id)
    if status:
        return {**status, "preview_ready": (folder(identifier) / "document.json").exists()}
    if (path / 'status.json').exists():
        return json.loads((path / 'status.json').read_text())
    return {'status': 'failed', 'message': 'The server restarted during this experiment. Start a new one.'}


@app.get('/api/documents/{identifier}/stress-tests/{test_id}/pages/{number}')
def stress_page(identifier: str, test_id: str, number: int):
    path = experiment_folder(identifier, test_id)
    if number < 1 or number > 12 or not (path / f'page-{number}.png').exists():
        raise HTTPException(404, 'Experiment page not found.')
    return FileResponse(path / f'page-{number}.png', media_type='image/png')


def process_entities(identifier, document):
    path = folder(identifier)
    try:
        def progress(done,total):
            with lock:
                entity_jobs[identifier] = {'status':'discovering', 'message':f'Analyzed {done}/{total} pages. Linking entities to source regions…', 'pages_done':done, 'pages_total':total}
        atlas = discover_entities(document, path, progress=progress)
        # Atomic replacement avoids partial reads by polling clients.
        tmp = path / 'entities.pending.json'
        tmp.write_text(json.dumps(atlas, ensure_ascii=False, indent=2))
        tmp.replace(path / 'entities.json')
        status = {'status':'complete'}
    except Exception as exc:
        status = {'status':'failed','message':str(exc) if isinstance(exc,(ValueError,ProviderError)) else 'Entity discovery failed. The original review is unchanged.'}
    finally:
        slots.release()
    with lock:
        entity_jobs[identifier] = status


@app.post('/api/documents/{identifier}/entities')
def start_entities(identifier: str):
    document = load_document(identifier)
    with lock:
        if entity_jobs.get(identifier,{}).get('status') in {'queued','discovering'}:
            return entity_jobs[identifier]
        if (folder(identifier)/'entities.json').exists():
            return {'status':'complete'}
        if not os.getenv('NVIDIA_API_KEY'):
            raise HTTPException(422,'Connect NVIDIA in settings for automatic entity discovery.')
        if not slots.acquire(blocking=False):
            raise HTTPException(429,'The processing queue is full. Try again shortly.')
        entity_jobs[identifier] = {'status':'queued','message':'Nemotron is discovering document entities…'}
    pool.submit(process_entities, identifier, document)
    return {'status':'queued'}


@app.get('/api/documents/{identifier}/entities')
def get_entities(identifier: str):
    path = folder(identifier)/'entities.json'
    if path.exists():
        return {'status':'complete','result':json.loads(path.read_text())}
    with lock:
        status = entity_jobs.get(identifier)
    return status or {'status':'not_started'}
