"""Build a transparent report from saved runs; never modify expected answers."""
import argparse,html,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='normalized-v6');a=parser.parse_args()
    manifest=json.loads((ROOT/'evaluation/real-manifest.json').read_text())
    records=[json.loads((ROOT/'evaluation'/a.tag/(d['id']+'-nvidia.json')).read_text()) for d in manifest['documents']]
    completed=[r for r in records if r['job_status']['status']=='complete']
    decisions=[d for r in completed for d in r['decisions']]
    correct=sum(d['correct'] for d in decisions);nonnull=[d for d in decisions if d['actual'] is not None]
    present=[d for d in decisions if d['expected'] is not None];absent=[d for d in decisions if d['expected'] is None]
    calls=[c for r in completed for c in r['result']['model_calls']]
    summary={'tag':a.tag,'documents':len(records),'completed':len(completed),'pages':sum(d['pages'] for d in manifest['documents']),
        'requested_fields':sum(len(d['fields']) for d in manifest['documents']),'scored_fields':len(decisions),'strict_correct':correct,
        'present_correct':sum(d['correct'] for d in present),'present_total':len(present),
        'absent_correct':sum(d['correct'] for d in absent),'absent_total':len(absent),
        'nonnull':len(nonnull),'nonnull_strict_correct':sum(d['correct'] for d in nonnull),
        'nonnull_with_evidence':sum(d['has_evidence'] for d in nonnull),'successful_model_calls':len(calls),
        'total_reported_tokens':sum(c.get('usage',{}).get('total_tokens',0) for c in calls),
        'median_document_seconds':statistics.median([r['wall_seconds'] for r in records]),
        'models':sorted(set(c['model'] for c in calls)),
        'interpretation':'Small public-document development set. Reused during fixes, not held out. Exact match is not a source-grounding quality score. API errors are counted separately, not silently dropped.'}
    (ROOT/'evaluation'/a.tag/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    lines=['# Real-document evaluation — EvidenceDoc','',f'9 Eylül 2026 · sürüm testi: `{a.tag}`','',
        f'**{len(completed)}/{len(records)} belge tamamlandı. {correct}/{len(decisions)} alan kararı sabit cevap anahtarıyla birebir eşleşti.**',
        '','Altı özgün, kamuya açık PDF; 36 pages; 49 alan. Sentetik belge veya yapay hata enjeksiyonu kullanılmadı. Kaynaklar değiştirilmeden işlendi. Beklenen cevaplar ilk model çalışmasından önce kaydedildi; sonraki düzeltmeler sırasında değiştirilmedi.',
        '',f'- Belgede bulunan alanlar: **{summary["present_correct"]}/{len(present)}** doğru çıkarım.',
        f'- Boş/olmayan alanlar: **{summary["absent_correct"]}/{len(absent)}** doğru boş bırakma.',
        f'- Boş olmayan sonuçlar: **{summary["nonnull_strict_correct"]}/{len(nonnull)}** birebir doğru; **{summary["nonnull_with_evidence"]}/{len(nonnull)}** kaynak metni taşıyor. Kaynak taşıması tek başına doğru alan anlamına gelmez.',
        f'- Kaydedilen başarılı model çağrısı: **{len(calls)}**; bildirilen toplam token: **{summary["total_reported_tokens"]:,}**.',
        f'- Medyan belge süresi: **{summary["median_document_seconds"]:.1f} seconds**. Ağ/servis etkileri dahildir; donanım performans ölçümü değildir.',
        '', '| Belge | Sayfa | Doğru alan / toplam | Durum |', '|---|---:|---:|---|']
    detail=[]
    for r in records:
        ds=r.get('decisions',[])
        lines.append(f'| [{r["title"]}]({r["source_url"]}) | {r["pages"]} | {sum(d["correct"] for d in ds)}/{len(ds)} | {r["job_status"]["status"]} |')
        detail.append(f'<details><summary>{html.escape(r["title"])} · {sum(d["correct"] for d in ds)}/{len(ds)}</summary><p><a href="{html.escape(r["source_url"],quote=True)}">Original PDF</a> · {r["pages"]} pages · {r["wall_seconds"]:.1f} seconds</p><table><tr><th>Field</th><th>Expected</th><th>Actual result</th><th>Check</th></tr>')
        for d in ds:
            detail.append('<tr><td>'+html.escape(d['field'])+'</td><td>'+html.escape(' / '.join(d['expected']) if d['expected'] else 'null')+'</td><td>'+html.escape(str(d['actual']) if d['actual'] is not None else 'null')+'</td><td>'+('✓ Matched' if d['correct'] else '✕ Review')+'</td></tr>')
        detail.append('</table></details>')
    lines+=['','## Kalan birebir eşleşme hataları','']
    for r in completed:
        for d in r['decisions']:
            if not d['correct']:lines.append(f'- **{r["document_id"]} / {d["field"]}** — beklenen: `{d["expected"]}`; sonuç: `{d["actual"]}`; durum: `{d["status"]}`.')
    if a.tag == 'normalized-v6':
        lines+=['', 'Bu son turdaki beş tam eşleşme farkının dördünde doğru bilgiye ek sözler eşlik ediyor: aylık tutardaki “per month”, yazıyla da verilen hibe tutarı, katalog numarasının “Cat. No.” öneki ve kurum adına eklenen üst kurum. Bunları cevap anahtarını sonradan genişleterek doğru saymadık. Beşinci fark el yazısı imza tarihinin boş bırakılmasıdır. Bu yorum, ayrı bir bağımsız doğruluk puanı değildir.']
    lines+=['','## Önceki denemeler de korunuyor','',
        '| Deneme | Tamamlanan belge | Doğru / değerlendirilebilen alan | Servis/çıktı hatası |','|---|---:|---:|---:|']
    history=[]
    for tag,mode in [('baseline','local'),('baseline','nvidia'),('omni-v1','nvidia'),('omni-v2','nvidia'),('super-v3','nvidia'),('final-v4','nvidia'),('release-v5','nvidia'),(a.tag,'nvidia')]:
        rr=[json.loads(p.read_text()) for p in (ROOT/'evaluation'/tag).glob('*-'+mode+'.json')]
        dd=[d for r in rr for d in r.get('decisions',[])]
        ok=sum(r['job_status']['status']=='complete' for r in rr)
        line=f'{tag} / {mode} | {ok}/{len(rr)} | {sum(d["correct"] for d in dd)}/{len(dd)} | {len(rr)-ok}'
        lines.append('| '+line+' |');history.append(line)
    lines+=['','İlk varsayılan model HTTP 410 döndürdü. Nano Omni ile bazı yanıtlarda biçim hataları ve HTTP 503 görüldü. Metin çıkarımı/denetim Super’e, görsel tekrar okuma Omni’ye ayrıldı. Noktalama sınırları, çok satırlı değerler, komşu kaynak bağlantısı, eksik tarih parçaları ve yanlış yerel çatışma tespiti için düzeltmeler eklendi.',
        '', '## Ölçümün sınırları','',
        '- Bu küçük küme geliştirme sırasında tekrar kullanıldı; bağımsız veya temsili bir başarı testi değildir. Kamuya açık belgeler model eğitim verisinde bulunmuş olabilir.',
        '- Tam eşleşme yalnızca önceden yazılmış alternatifler, Unicode, harf büyüklüğü ve boşluk normalizasyonu kullanır. Sonradan uygun görünen cevaplar doğru sayılacak şekilde anahtar genişletilmedi.',
        '- Kaynak eşleştirme metin satırı düzeyindedir. Kutu varlığı, piksel hassasiyetinde alan segmentasyonu veya semantik doğruluk kanıtı değildir. Bazı özgün pageslar görsel olarak incelendi; tüm kutular bağımsız bir değerlendirici tarafından puanlanmadı.',
        '- Bozuk OCR katmanı ve el yazısı tarihleri hâlâ zorlayıcıdır. Metin katmanı bulunan taramalarda yeni OCR yapılmaz; görsel tekrar okuma bu katmanı otomatik değiştirmez.',
        '- Türkçe TCMB sonucu keşif amaçlıdır. Kullanılan modellerin resmî dil listelerinde Türkçe yoktur.',
        '- Aynı metin modeli çıkarım ve denetim yapar. Bunlar bağımsız hata olasılıkları değildir. Güven puanı kalibre edilmedi; null kalır.',
        '- Tek geçişli LLM ile kontrollü kıyas yapılmadı. Bu sonuçlardan “halüsinasyonları yüzde X azalttı” sonucu çıkarılamaz.',
        '', '## Yeniden üretim','',
        '```sh','.venv/bin/python scripts/fetch_real_documents.py --output data/real-source',
        '# Yerel uygulamada NVIDIA anahtarını bağla.',
        '.venv/bin/python scripts/evaluate_real.py --documents data/real-source --tag yeni-deneme --modes local nvidia',
        '.venv/bin/python scripts/report_real.py --tag yeni-deneme','```','',
        'Kaynak adresleri ve SHA-256 değerleri: [manifest](../evaluation/real-manifest.json). Alan bazındaki gerçek sonuçlar, model yanıtları, token kullanımı ve kod karmaları `evaluation/` altındadır. Anahtar kodda veya teslim paketinde bulunmaz.',
        '', 'Model belgeleri: [Nemotron Super](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard) · [Nano Omni](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning/modelcard).']
    (ROOT/'docs/real-evaluation.md').write_text('\n'.join(lines)+'\n')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EvidenceDoc · Real-document evaluation</title><style>body{font:16px/1.65 system-ui,sans-serif;background:#f2f3ee;color:#182719;margin:0}main{max-width:1160px;margin:auto;padding:48px 24px}h1{font-size:clamp(32px,6vw,62px);line-height:1.07;letter-spacing:-2px}small{letter-spacing:2px;text-transform:uppercase}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:#183d2b;color:white;border-radius:16px;padding:24px;flex:1;min-width:180px}.big{display:block;font-size:44px;line-height:1.2}details{border:1px solid #c7d0c3;background:white;border-radius:12px;margin:14px 0;padding:18px;overflow:auto}summary{cursor:pointer;font-weight:650}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd;vertical-align:top;max-width:360px;overflow-wrap:anywhere}a{color:#276944}.note{border-left:4px solid #a8bf82;padding:12px 20px;background:#e5eadc}.history{white-space:pre-wrap;font:13px/1.8 ui-monospace,monospace}footer{margin-top:30px;color:#546050}</style><main><small>EvidenceDoc / Live NVIDIA evaluation</small><h1>Real documents.<br>Visible failures.</h1><p>6 original public documents · 36 pages · 49 fields · September 9, 2026</p>'''
    page+=f'<div class="cards"><div class="card"><span class="big">{correct}/{len(decisions)}</span>Exact field decisions</div><div class="card"><span class="big">{len(completed)}/6</span>Completed public documents</div><div class="card"><span class="big">{summary["absent_correct"]}/{len(absent)}</span>Correct abstentions</div></div>'
    page+='<p class="note">This is a development evaluation. The same documents were reused during fixes; this is not an independent benchmark or a general accuracy claim. Expected answers were fixed before the first model run. Earlier failed attempts are retained.</p><h2>Field-level results</h2>'+''.join(detail)
    page+='<h2>All attempts</h2><div class="history">'+html.escape('\n'.join(history))+'</div><p>A source citation does not guarantee that a value answers the requested field. Handwriting, OCR errors, table context and model variability remain limitations. Broad language coverage has not been established.</p><footer><a href="real-evaluation.md">Method and reproduction</a> · '+html.escape(a.tag)+' · API keys and original PDF files are not embedded in this report.</footer></main></html>'
    (ROOT/'docs/real-evaluation.html').write_text(page)
    (ROOT/'evidencedoc/static/real-evaluation.html').write_text(page)
    (ROOT/'evidencedoc/static/real-evaluation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
