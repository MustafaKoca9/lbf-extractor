# lbf-extractor

[English](README.md) | [Türkçe](README.tr.md)

LG Mobile Switch LBF yedeklerini incelemek ve kurtarmak için modüler, akış tabanlı kütüphane. Çekirdek API isteğe bağlı CLI arayüzüne bağlı değildir. Başlık çözüldüğünde ham XML yapısını, özgün alanları ve çözülemeyen alanları içeren metadata_report.json ve metadata_report.md üretilir.

Kurulum: python -m pip install .
Dosya çıkarma: lbf-extractor backup.lbf --output ./kurtarilan
Yalnızca üstveri: lbf-extractor backup.lbf --output ./rapor --metadata-only
Akış parça boyutu: lbf-extractor backup.lbf --chunk-size-mib 4

Python API: from lbf_extractor import extract_archive; extract_archive("backup.lbf", "./kurtarilan"). Dosyaları çıkarmadan rapor için extract_archive("backup.lbf", "./rapor", extract_files=False) kullanın. API içindeki chunk_size bayt cinsindendir.

Raporlar kişisel veri içerebilir; paylaşmadan önce temizleyin. Mimari: docs/mimari.md. Geliştirme: python -m pip install -e ".[dev]", ardından pytest -q. MIT lisansı.
