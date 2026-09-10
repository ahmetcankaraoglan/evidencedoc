"""Download original public PDFs and verify the frozen evaluation hashes."""
import argparse,hashlib,json
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'evaluation/real-manifest.json').read_text())
    with httpx.Client(follow_redirects=True,timeout=90,headers={'User-Agent':'EvidenceDoc evaluation / public-source verification'}) as client:
        for document in manifest['documents']:
            target=args.output/document['file']
            raw=target.read_bytes() if target.exists() else client.get(document['source_url']).raise_for_status().content
            if hashlib.sha256(raw).hexdigest()!=document['sha256']:
                raise SystemExit('Source changed or download failed: '+document['id']+'. The frozen expected answers were not changed.')
            target.write_bytes(raw);print('VERIFIED',document['id'],flush=True)
if __name__=='__main__':main()
