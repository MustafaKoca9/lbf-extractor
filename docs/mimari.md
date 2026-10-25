# Mimari

Bu proje komut satırı aracı değil, Python kütüphanesidir.

| Modül | Sorumluluk |
| --- | --- |
| `common.py` | Ortak sabitler, istisnalar, sonuç modelleri, terminal çıktısı ve sürüm bilgisi. |
| `archive.py` | Mantıksal arşivin tamamını belleğe alır ve doğrudan bayt aralığı okur. |
| `metadata.py` | Başlık üstverisini çözer ve XML'i ayrıştırır. |
| `paths.py` | Çıktı dosya adlarını belirler; tam bayt/metin içeriklerini doğrudan yazar. |
| `extraction.py` | Katalogdaki payload aralıklarını tek seferde çıkarır ve isteğe bağlı eşlenmemiş aralıkları kurtarır. |
| `diagnostics.py` | Ham XML'i ve bilinmeyen alanları koruyan JSON/Markdown raporları üretir. |
| `reporting.py` | Sonuç özetini biçimlendirir. |
| `core.py` | Bileşenleri herkese açık `LBFExtractor` API'si üzerinden koordine eder. |

## Veri akışı

1. `ArchiveReader`, ana arşivi ve numaralı ek segmentleri tek bir `bytes` nesnesine yükler.
2. `MetadataParser` başlık aralıklarını okur, şifreyi çözer ve XML ağacını döndürür.
3. `diagnostics.py` ham XML'i, öznitelikleri ve yorumlanan ofset/boyut alanlarını kaydeder.
4. `PayloadExtractor`, her payload aralığını tek işlemde okur ve dosyanın tamamını yazar.
5. Etkinleştirilirse katalogda referans verilmeyen aralıklar kurtarılır.

## Tercihin bedeli

Bu tasarım, akışla işleme yerine doğrudan ve anlaşılır tam-aralık işlemesini tercih eder. Bellek kullanımı arşivin tamamının boyutuna ve yazılmakta olan en büyük payload'a yaklaşabilir. Yedeği işlerken yeterli RAM bulunduğundan emin olun.
