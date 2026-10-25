# Mimari

Paket, mixin yerine bileşim (composition) kullanır. CLI isteğe bağlı bir adaptördür; temel Python API'si CLI'yi içe aktarmaya ihtiyaç duymaz.

| Modül | Sorumluluk |
| --- | --- |
| `common.py` | Ortak sabitler, genel istisnalar, sonuç modelleri, terminal biçimlendirme ve sürüm bilgisi. |
| `archive.py` | `ArchiveReader`: segment dosyalarını yönetir, parça sırasını doğrular ve sınır kontrollü `iter_range()` / `read_bytes()` sunar. |
| `metadata.py` | `MetadataParser`: kendisine verilen arşiv okuyucusu ve çıktı yöneticisiyle başlığı çözer ve XML'i ayrıştırır. |
| `paths.py` | `OutputManager`: çıktı yollarını sınırlar ve tamamlanan dosyaları atomik yayımlar. |
| `extraction.py` | `PayloadExtractor`: katalog aralıklarını yorumlar, payload'ları akışla çıkarır, hataları kaydeder ve eşlenmemiş aralıkları kurtarır. |
| `diagnostics.py` | Ham XML ve bilinmeyen alanları koruyarak JSON/Markdown üstveri raporu üretir. |
| `reporting.py` | Durumdan bağımsız terminal özeti biçimlendiricisi. |
| `core.py` | Herkese açık `LBFExtractor` koordinatörü ve geriye dönük uyumluluk katmanı. |
| `cli.py` | İsteğe bağlı komut satırı argümanları ve çıkış kodları. |

## Veri akışı

1. `LBFExtractor`, tüm segment dosyalarını yöneten bir `ArchiveReader` açar.
2. `MetadataParser` sınırları belli aralıkları okur, başlığı çözer ve XML ağacını döndürür.
3. `diagnostics.py`, payload çıkarma başlamadan önce özgün XML'i ve ham/yorumlanmış ofset-boyut alanlarını rapora kaydeder.
4. `PayloadExtractor`, kataloğu işler; veriyi yapılandırılabilir boyuttaki parçalarla `ArchiveReader.iter_range()` üzerinden okur.
5. `OutputManager`, aynı dizindeki geçici dosyalara yazar ve tamamlanmış çıktıları atomik yayımlar.
6. Özellik etkinse eşlenmemiş aralık taraması bilinen aralıkları birleştirir ve yalnızca arşiv treylerinden önceki boşlukları kurtarır.

## Temel kurallar

- Payload çıkarmak için arşivin tamamını belleğe yüklemeyin.
- Okumadan/yazmadan önce ofset ve uzunlukları doğrulayın.
- Numaralı çok parçalı arşivlerdeki boş segment numaralarını sessizce atlamayın.
- Üretilen raporları ve çıkarılan kişisel verileri gizli tutun; raporlar kişisel bilgi içerebilir.
- Arşiv sınırları içinde kalan aralık yalnızca sayısal açıdan geçerlidir; belli bir yedek biçiminde yine de yanlış yorumlanmış olabilir.
- CLI ayrıntılarını çekirdek ayrıştırıcıdan ve arşiv okuyucusundan ayrı tutun.

API içindeki `chunk_size` bayt, CLI içindeki `--chunk-size-mib` MiB cinsindendir. Payload dosyalarını yazmadan tanılama toplamak için `--metadata-only` kullanın.
