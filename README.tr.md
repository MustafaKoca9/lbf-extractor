# lbf-extractor

[English](README.md) | [Türkçe](README.tr.md)

LG Mobile Switch `.lbf` yedeklerini incelemek ve çıkarmak için Python kütüphanesi. API, mantıksal arşivin tamamını belleğe alır ve katalogdaki her payload aralığını tek seferde okuyup dosyaya yazar. Numaralı ek segmentler varsa aynı mantıksal arşivin parçaları olarak birleştirilir.

Başlık başarıyla ayrıştırıldığında ham XML'i, özgün alan değerlerini ve çözülemeyen alanları içeren `metadata_report.json` ve `metadata_report.md` dosyaları oluşturulur.

## Kullanım

```python
from lbf_extractor import extract_archive

extractor = extract_archive("yedek.lbf", "./kurtarilan")
print(extractor.stats)
```

Payload dosyalarını çıkarmadan yalnızca üstveri raporu üretmek için:

```python
from lbf_extractor import extract_archive

extractor = extract_archive("yedek.lbf", "./rapor", extract_files=False)
```

Kurulum: `python -m pip install .`. Mimari: `docs/mimari.md`. MIT lisansı.
