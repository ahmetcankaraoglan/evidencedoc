# Gerçek belge testi — EvidenceDoc

9 Eylül 2026 · sürüm testi: `normalized-v6`

**6/6 belge tamamlandı. 44/49 alan kararı sabit cevap anahtarıyla birebir eşleşti.**

Altı özgün, kamuya açık PDF; 36 sayfa; 49 alan. Sentetik belge veya yapay hata enjeksiyonu kullanılmadı. Kaynaklar değiştirilmeden işlendi. Beklenen cevaplar ilk model çalışmasından önce kaydedildi; sonraki düzeltmeler sırasında değiştirilmedi.

- Belgede bulunan alanlar: **35/40** doğru çıkarım.
- Boş/olmayan alanlar: **9/9** doğru boş bırakma.
- Boş olmayan sonuçlar: **35/39** birebir doğru; **39/39** kaynak metni taşıyor. Kaynak taşıması tek başına doğru alan anlamına gelmez.
- Kaydedilen başarılı model çağrısı: **12**; bildirilen toplam token: **81,922**.
- Medyan belge süresi: **31.3 saniye**. Ağ/servis etkileri dahildir; donanım performans ölçümü değildir.

| Belge | Sayfa | Doğru alan / toplam | Durum |
|---|---:|---:|---|
| [Federal Reserve FOMC statement and implementation decisions](https://www.federalreserve.gov/monetarypolicy/files/monetary20250129a1.pdf) | 4 | 7/8 | complete |
| [NVIDIA Q4 and Fiscal 2026 financial results](https://nvidianews.nvidia.com/_gallery/download_pdf/699f6ab43d6332ccaa689907/) | 11 | 8/8 | complete |
| [TCMB Para Politikası Kurulu Kararı 17 Nisan 2025](https://www.tcmb.gov.tr/wps/wcm/connect/3203675d-3553-4bf0-bfc2-a21a660e739c/DUY2025-24.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-3203675d-3553-4bf0-bfc2-a21a660e739c-pp3pZv2) | 1 | 8/8 | complete |
| [World Bank / IDA Afghanistan grant agreement TF051711](https://documents1.worldbank.org/curated/en/549511516120883931/pdf/Grant-Agreement-TF051711.pdf) | 10 | 8/8 | complete |
| [World Bank / IDA Somalia Statistical Capacity Building grant](https://documents1.worldbank.org/curated/en/126091487799296208/pdf/ITK171540-201701221631.pdf) | 4 | 7/9 | complete |
| [IRS Form W-9 revision March 2024 (official blank form)](https://www.irs.gov/pub/irs-pdf/fw9.pdf) | 6 | 6/8 | complete |

## Kalan birebir eşleşme hataları

- **fomc-2025-01-29 / treasury_monthly_redemption_cap** — beklenen: `['$25 billion']`; sonuç: `$25 billion per month`; durum: `recovered`.
- **worldbank-tf / total_grant_amount** — beklenen: `['$500,000', '500,000']`; sonuç: `five hundred thousand United States Dollars ($500,000)`; durum: `grounded`.
- **worldbank-tf / recipient_signature_date** — beklenen: `['16 FEBRUARY 2017', '16 February 2017', '16 FEBRUARY, 2017']`; sonuç: `None`; durum: `abstained`.
- **irs-w9 / catalog_number** — beklenen: `['10231X']`; sonuç: `Cat. No. 10231X`; durum: `grounded`.
- **irs-w9 / issuing_agency** — beklenen: `['Internal Revenue Service']`; sonuç: `Department of the Treasury Internal Revenue Service`; durum: `grounded`.

Bu son turdaki beş tam eşleşme farkının dördünde doğru bilgiye ek sözler eşlik ediyor: aylık tutardaki “per month”, yazıyla da verilen hibe tutarı, katalog numarasının “Cat. No.” öneki ve kurum adına eklenen üst kurum. Bunları cevap anahtarını sonradan genişleterek doğru saymadık. Beşinci fark el yazısı imza tarihinin boş bırakılmasıdır. Bu yorum, ayrı bir bağımsız doğruluk puanı değildir.

## Önceki denemeler de korunuyor

| Deneme | Tamamlanan belge | Doğru / değerlendirilebilen alan | Servis/çıktı hatası |
|---|---:|---:|---:|
| baseline / local | 6/6 | 9/49 | 0 |
| baseline / nvidia | 0/6 | 0/0 | 6 |
| omni-v1 / nvidia | 1/6 | 7/8 | 5 |
| omni-v2 / nvidia | 3/6 | 18/24 | 3 |
| super-v3 / nvidia | 5/6 | 30/40 | 1 |
| final-v4 / nvidia | 6/6 | 41/49 | 0 |
| release-v5 / nvidia | 5/6 | 28/41 | 1 |
| normalized-v6 / nvidia | 6/6 | 44/49 | 0 |

İlk varsayılan model HTTP 410 döndürdü. Nano Omni ile bazı yanıtlarda biçim hataları ve HTTP 503 görüldü. Metin çıkarımı/denetim Super’e, görsel tekrar okuma Omni’ye ayrıldı. Noktalama sınırları, çok satırlı değerler, komşu kaynak bağlantısı, eksik tarih parçaları ve yanlış yerel çatışma tespiti için düzeltmeler eklendi.

## Ölçümün sınırları

- Bu küçük küme geliştirme sırasında tekrar kullanıldı; bağımsız veya temsili bir başarı testi değildir. Kamuya açık belgeler model eğitim verisinde bulunmuş olabilir.
- Tam eşleşme yalnızca önceden yazılmış alternatifler, Unicode, harf büyüklüğü ve boşluk normalizasyonu kullanır. Sonradan uygun görünen cevaplar doğru sayılacak şekilde anahtar genişletilmedi.
- Kaynak eşleştirme metin satırı düzeyindedir. Kutu varlığı, piksel hassasiyetinde alan segmentasyonu veya semantik doğruluk kanıtı değildir. Bazı özgün sayfalar görsel olarak incelendi; tüm kutular bağımsız bir değerlendirici tarafından puanlanmadı.
- Bozuk OCR katmanı ve el yazısı tarihleri hâlâ zorlayıcıdır. Metin katmanı bulunan taramalarda yeni OCR yapılmaz; görsel tekrar okuma bu katmanı otomatik değiştirmez.
- Türkçe TCMB sonucu keşif amaçlıdır. Kullanılan modellerin resmî dil listelerinde Türkçe yoktur.
- Aynı metin modeli çıkarım ve denetim yapar. Bunlar bağımsız hata olasılıkları değildir. Güven puanı kalibre edilmedi; null kalır.
- Tek geçişli LLM ile kontrollü kıyas yapılmadı. Bu sonuçlardan “halüsinasyonları yüzde X azalttı” sonucu çıkarılamaz.

## Yeniden üretim

```sh
.venv/bin/python scripts/fetch_real_documents.py --output data/real-source
# Yerel uygulamada NVIDIA anahtarını bağla.
.venv/bin/python scripts/evaluate_real.py --documents data/real-source --tag yeni-deneme --modes local nvidia
.venv/bin/python scripts/report_real.py --tag yeni-deneme
```

Kaynak adresleri ve SHA-256 değerleri: [manifest](../evaluation/real-manifest.json). Alan bazındaki gerçek sonuçlar, model yanıtları, token kullanımı ve kod karmaları `evaluation/` altındadır. Anahtar kodda veya teslim paketinde bulunmaz.

Model belgeleri: [Nemotron Super](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard) · [Nano Omni](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning/modelcard).
