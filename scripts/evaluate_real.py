"""Evaluate original public documents through the actual local app and configured NVIDIA session.

No API key is read or written by this script. Connect it through the local UI first.
The manifest contains references frozen before the first model run; never feed them to the model.
"""
import argparse, hashlib, json, time, unicodedata
from pathlib import Path
from datetime import datetime, timezone
import httpx

ROOT=Path(__file__).resolve().parents[1]
def normalized(s):
    return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--documents',type=Path,required=True)
    parser.add_argument('--server',default='http://127.0.0.1:8765')
    parser.add_argument('--tag',default='baseline')
    parser.add_argument('--only',nargs='*')
    parser.add_argument('--modes',nargs='+',choices=['local','nvidia'],default=['local','nvidia'])
    args=parser.parse_args()
    manifest_path=ROOT/'evaluation'/'real-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    folder=ROOT/'evaluation'/args.tag
    if folder.exists():raise SystemExit('Choose a new --tag; prior evaluation results must not be overwritten.')
    folder.mkdir(parents=True)
    code_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'evidencedoc').glob('*.py')}
    metadata={'started_at':datetime.now(timezone.utc).isoformat(),'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'code_sha256':code_hashes}
    (folder/'run-metadata.json').write_text(json.dumps(metadata,indent=2))
    with httpx.Client(base_url=args.server,timeout=45) as client:
        configuration=client.get('/api/config').json()
        if 'nvidia' in args.modes and not configuration['nvidia_configured']:
            raise SystemExit('Connect your NVIDIA API key in the local app before running this evaluation.')
        for doc in manifest['documents']:
            if args.only and doc['id'] not in args.only:continue
            raw=(args.documents/doc['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=doc['sha256']:
                raise ValueError('Source hash mismatch: '+doc['id'])
            for mode in args.modes:
                output=folder/(doc['id']+'-'+mode+'.json')
                started=time.monotonic()
                print('START',doc['id'],mode,flush=True)
                r=client.post('/api/analyze',files={'file':(doc['file'],raw,'application/pdf')},
                              data={'mode':mode,'fields':json.dumps([f['field'] for f in doc['fields']])})
                r.raise_for_status();identifier=r.json()['id']
                previous=None;heartbeat=0
                while time.monotonic()-started<1000:
                    job=client.get('/api/jobs/'+identifier).json()
                    elapsed=time.monotonic()-started
                    if job['status']!=previous or elapsed-heartbeat>30:
                        print(doc['id'],mode,job['status'],round(elapsed),'sec',flush=True)
                        previous=job['status'];heartbeat=elapsed
                    if job['status'] in {'complete','failed'}:break
                    time.sleep(2)
                record={'document_id':doc['id'],'title':doc['title'],'source_url':doc['source_url'],
                        'source_sha256':doc['sha256'],'source_type':doc['source_type'],'pages':doc['pages'],
                        'mode':mode,'job_id':identifier,'job_status':job,'wall_seconds':round(time.monotonic()-started,2)}
                if job['status']=='complete':
                    result=client.get('/api/documents/'+identifier).json()
                    record['result']={k:v for k,v in result.items() if k!='document'}
                    record['decisions']=[]
                    for reference in doc['fields']:
                        prediction=next(f for f in result['fields'] if f['field']==reference['field'])
                        accepted=reference['accepted_values'];value=prediction['value']
                        match=(value is None and prediction['status']=='abstained') if accepted is None else (isinstance(value,str) and any(normalized(value)==normalized(a) for a in accepted))
                        record['decisions'].append({'field':reference['field'],'expected':accepted,'reference_page':reference['reference_page'],
                            'actual':value,'status':prediction['status'],'correct':match,
                            'has_evidence':bool(prediction['evidence']),'reference_note':reference['reference_note']})
                    print('RESULT',doc['id'],mode,sum(d['correct'] for d in record['decisions']),'/',len(record['decisions']),flush=True)
                else:
                    print('FAILED',doc['id'],mode,job['message'],flush=True)
                output.write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print('SAVED',folder,flush=True)

if __name__=='__main__':main()
