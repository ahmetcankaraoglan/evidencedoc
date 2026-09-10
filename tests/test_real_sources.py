"""Regression checks using original public documents and their recorded source data."""
import hashlib,json,shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import evidencedoc.app as api
from evidencedoc.document import ingest
from evidencedoc.discovery import precise_evidence
from evidencedoc.stress import mask_document
ROOT=Path(__file__).parents[1]
PUBLIC=ROOT/'evidencedoc/public_documents'
MANIFEST=json.loads((PUBLIC/'manifest.json').read_text())

@pytest.mark.parametrize('entry',MANIFEST,ids=lambda d:d['id'])
def test_public_source_has_published_url_and_matches_checksum(entry):
    assert entry['source_url'].startswith('https://')
    assert hashlib.sha256((PUBLIC/entry['filename']).read_bytes()).hexdigest()==entry['sha256']

@pytest.fixture
def tcmb(tmp_path):
    content=(PUBLIC/'tcmb-2025-24.pdf').read_bytes();(tmp_path/'source').write_bytes(content)
    return ingest(content,tmp_path)

def test_real_tcmb_date_has_precise_boxes(tcmb,tmp_path):
    cited=[s for s in tcmb['spans'] if '17 Nisan 2025' in s['text']]
    assert cited
    boxes=precise_evidence('17 Nisan 2025',cited,tmp_path/'source')
    assert boxes and all(s['precision']=='text-match' for s in boxes)
    assert all(0<=v<=1 for s in boxes for v in s['bbox'])

def test_real_source_mask_preserves_original_and_removes_date(tcmb,tmp_path):
    before=(tmp_path/'page-1.png').read_bytes()
    date=next(s for s in tcmb['spans'] if '17 Nisan 2025' in s['text'])
    masked,removed=mask_document(tcmb,[date['id']],tmp_path,tmp_path/'masked')
    assert date['id'] not in {s['id'] for s in masked['spans']}
    assert date['id'] in {s['id'] for s in removed}
    assert (tmp_path/'page-1.png').read_bytes()==before
    assert (tmp_path/'masked/page-1.png').read_bytes()!=before

def test_preview_of_real_document_precedes_final_result(tcmb,tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    did='a'*32;folder=tmp_path/did;folder.mkdir()
    doc={**tcmb,'id':did,'filename':'tcmb-2025-24.pdf','sha256':hashlib.sha256((PUBLIC/'tcmb-2025-24.pdf').read_bytes()).hexdigest()}
    api.jobs[did]={'status':'discovering','message':'Reading source'}
    client=TestClient(api.app)
    assert client.get('/api/jobs/'+did+'/preview').status_code==409
    (folder/'document.json').write_text(json.dumps(doc))
    assert client.get('/api/jobs/'+did).json()['preview_ready']
    assert 'spans' not in client.get('/api/jobs/'+did+'/preview').json()
    assert client.get('/api/documents/'+did).status_code==409
    api.jobs.pop(did)

def test_only_real_examples_are_available(monkeypatch):
    client=TestClient(api.app)
    config=client.get('/api/config').json()
    assert not config['samples']
    assert len(config['public_documents'])==4
    assert client.post('/api/samples/authority').status_code==404
    assert client.post('/api/lab-example').status_code==404
    monkeypatch.delenv('NVIDIA_API_KEY',raising=False)
    assert client.post('/api/public-documents/nvidia-fy2026').status_code==422
    assert client.post('/api/public-documents/unknown').status_code==404

def test_real_document_submission_passes_original_bytes(monkeypatch):
    observed={}
    def capture(content,filename,fields,mode,**kwargs):
        observed.update(content=content,filename=filename,mode=mode,fields=fields,**kwargs)
        return {'id':'test-request'}
    monkeypatch.setattr(api,'submit',capture)
    response=TestClient(api.app).post('/api/public-documents/nvidia-fy2026?discover=true')
    assert response.status_code==200
    assert observed['content']==(PUBLIC/'nvidia-fy2026.pdf').read_bytes()
    assert observed['mode']=='nvidia' and observed['discover']

def test_cross_origin_write_blocked():
    assert TestClient(api.app).post('/api/public-documents/tcmb-2025-24',headers={'Origin':'https://example.org'}).status_code==403
