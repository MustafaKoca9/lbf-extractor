# Mimari özeti

## Mevcut yapı

Dışa aktarıcı şimdilik üst düzeydeki `lbf_extractor.py` modülünde tutuluyor. Böylece `from lbf_extractor import LBFExtractor` gibi mevcut kullanımlar ve kaynak dosyadan çalıştırma biçimi korunuyor; paketleme ve otomatik testler ise değişiklikleri doğrulamayı kolaylaştırıyor.

| Yol | Sorumluluk |
| --- | --- |
| `lbf_extractor.py` | Komut satırı, arşiv parçaları, başlık ayrıştırma, şifre çözme, güvenli yol çözümleme, akış tabanlı dışa aktarma ve denetim özeti. |
| `tests/test_helpers.py` | Dolgu işleme için deterministik testler. |
| `tests/test_cli.py` | Komut satırı varsayılanları, seçenekler ve kurucu doğrulamaları. |
| `examples/kullanim.md` | Komut satırı ve Python API'si için gerçekçi örnekler. |
| `pyproject.toml` | Paket metaverisi, bağımlılıklar, komut satırı girişi ve geliştirme araçları. |
| `.github/workflows/tests.yml` | Desteklenen Python sürümlerinde otomatik testler. |

## Dışa aktarma akışı

1. Komut satırı argümanları doğrulanır ve bir `LBFExtractor` oluşturulur.
2. Çok parçalı yedek bölümleri bulunur ve mantıksal bir bayt akışı olarak açılır.
3. Veriler yorumlanmadan önce arşiv sınırları ve başlık üstverisi denetlenir.
4. Başlık şifresi çözülür, dolgu kaldırılır, metne dönüştürülür ve XML olarak ayrıştırılır.
5. Katalog girdileri, izin verilen çıktı yollarına akış hâlinde yazılır; hatalar kaydedilir.
6. İsteğe bağlı olarak katalogda kullanılmayan aralıklar `unmapped/` dizinine aktarılır.
7. İnceleme için özet ve denetim kayıtları yazdırılır.

## Korunması gereken temel kurallar

- Yedeğin tamamını belleğe yüklemeyin; akış tabanlı tasarımı koruyun.
- Güvenilmeyen her ofset ve uzunluğu okumadan önce doğrulayın.
- Çıktı yollarını seçilen hedef dizinin içinde tutun.
- Çok parçalı yedeklerin sıralanmasında tutarlı davranışı koruyun.
- Gerçek kişilere ait yedekleri herkese açık test verisi olarak kullanmayın.
- Değişiklik bozucu olarak belgelenmediği sürece `LBFExtractor` içe aktarmasını ve `lbf-extractor` komutunu uyumlu tutun.

## Güvenli yeniden düzenleme yönü

Uygulama büyürse sorumlulukları küçük adımlarla ayrı modüllere taşıyın: komut satırı ve argüman doğrulama, parça/akış okuyucusu, başlık ve XML ayrıştırıcısı, yol politikası, denetim ve raporlama. Davranışı taşımadan önce test ekleyin ve üst düzey içe aktarma yolunu uyumluluk katmanı olarak koruyun. Her iki başlık biçimini ve çok parçalı okumayı kapsayan örnekler olmadan büyük çaplı dosya bölme işlemi yapmayın.
