# lbf-extractor

[English](README.md) · [Türkçe](README.tr.md)

> LG Mobile Switch `.lbf` yedeklerini akış tabanlı inceleme ve dışa aktarma aracı.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![MIT Lisansı](https://img.shields.io/badge/lisans-MIT-green.svg)](LICENSE)
[![Platformlar](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

`lbf-extractor`, LG Mobile Switch yedek arşivlerini okur, üstverilerini çözer, işaret edilen dosyaları çıktı dizinine aktarır ve adli inceleme amacıyla başvurulmayan bayt aralıklarını da koruyabilir. Tüm arşivi belleğe yüklemek yerine veriyi parça parça işler.

**Yalnızca size ait olan veya incelemek için açıkça yetkilendirildiğiniz yedekleri kullanın.** Ayrıntılar için [güvenlik politikasına](SECURITY.tr.md) ve [sorumlu kullanım](#sorumlu-kullanim) bölümüne bakın.

## Özellikler

- 1 MiB'lık parçalarla akış tabanlı okuma ve çok parçalı yedek desteği.
- Yeni başlık yerleşimi ile eski treyler yerleşiminin tespiti.
- AES-128-ECB ile üstveri çözme ve geçerli PKCS#7 dolgusunu kaldırma.
- Üstveri yeterli bilgi sağladığında medya yollarını yeniden oluşturma.
- Başvurulmayan bayt aralıklarını adli inceleme için `unmapped/` dizinine yazabilme.
- Dizin dışına dosya yazma riskini azaltmak için çıktı yollarını denetleme ve başarısız işlemleri kaydetme.
- Komut satırı arayüzü ve Python API'si.

Çalışma zamanı bağımlılığı: [PyCryptodome](https://pypi.org/project/pycryptodome/). Python 3.9 veya daha yeni bir sürüm gerekir.

## Kurulum

### Komut satırı aracı olarak kurulum

```bash
git clone https://github.com/MustafaKoca9/lbf-extractor.git
cd lbf-extractor
python -m pip install .
lbf-extractor --help
```

### Kaynak kod üzerinden çalıştırma

```bash
python -m pip install -r requirements.txt
python lbf_extractor.py telefon_yedegi.lbf --output ./kurtarilan
```

## Hızlı başlangıç

```bash
# Tek dosyalı bir yedeği dışa aktar
lbf-extractor telefon_yedegi.lbf --output ./kurtarilan

# Ayrıntılı günlükleri göster ve dosyaya kaydet
lbf-extractor telefon_yedegi.lbf --output ./kurtarilan --debug --log calistirma.log

# Başvurulmayan bayt aralıklarını yazma
lbf-extractor telefon_yedegi.lbf --output ./kurtarilan --no-unmapped

# .lbf dosyası çok parçalı yedeğin ilk parçasıysa
lbf-extractor telefon_yedegi.lbf --split-lbf-first
```

Çok parçalı yedeklerde programı `.lbf` dosyasını göstererek başlatın. Varsayılan olarak aynı dizindeki `.lbf0`, `.lbf1` ve benzeri parçaları bulur; önce numaralı parçaları, sonra `.lbf` dosyasını birleştirir. Yedeğiniz farklı sıradaysa `--split-lbf-first` kullanın.

## Python kütüphanesi olarak kullanma

```python
from lbf_extractor import LBFExtractor

with LBFExtractor("telefon_yedegi.lbf", output_dir="./kurtarilan") as extractor:
    extractor.execute()

print("Aktarılan:", extractor.stats.extracted)
print("Başarısız:", extractor.stats.failed)
```

Bağlam yöneticisi açık parça dosyalarını ve günlük işleyicilerini kapatır. Sonuçlara ve hata kayıtlarına `extractor.stats`, `extractor.audit_failed` ve `extractor.audit_missed` üzerinden erişilebilir.

## Çıktı dizini

Dosya adları yedek üstverisine göre değişir. Örnek bir çıktı yapısı:

```text
kurtarilan/
├── header-new.xml
├── app/
├── media/
├── records/
└── unmapped/
```

`unmapped/` dizini, çözümlenen üstveride işaret edilmeyen ham bayt aralıklarını içerir. Bu aralıkların geçerli veya eksiksiz dosyalar olması garanti değildir.

## Komut satırı seçenekleri

| Seçenek | Açıklama |
| --- | --- |
| `file` | Gerekli birincil `.lbf` dosyası yolu. |
| `-o, --output DİZİN` | Çıktı dizini; varsayılan: `./export`. |
| `--no-path-reconstruct` | Medya yolunu yeniden oluşturmayı kapatır. |
| `--force-new` | Yeni başlık biçimini zorlar. |
| `--force-old` | Eski başlık biçimini zorlar. |
| `--split-lbf-first` | `.lbf` parçasını numaralı parçalardan önce işler. |
| `--no-unmapped` | Başvurulmayan aralıkların kurtarılmasını atlar. |
| `--overwrite` | Çakışan dosyaları yeni ad vermek yerine değiştirir. |
| `--debug` | Ayrıntılı günlüklemeyi açar. |
| `--log DOSYA` | Ayrıntılı günlükleri belirtilen dosyaya da yazar. |
| `-v, --version` | Kurulu sürümü gösterir. |

`--force-new` ve `--force-old` aynı anda kullanılamaz. Güncel seçenekler için `lbf-extractor --help` komutunu çalıştırın.

## Geliştirme

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
python -m py_compile lbf_extractor.py
```

- [Mimari özeti](docs/mimari.md)
- [Kullanım örnekleri](examples/kullanim.md)
- [Katkıda bulunma rehberi](CONTRIBUTING.tr.md)
- [Güvenlik politikası](SECURITY.tr.md)
- [Değişiklik günlüğü](CHANGELOG.tr.md)

Mevcut dışa aktarıcı; herkese açık Python içe aktarma yolunu ve komut satırı kullanımını korumak amacıyla tek modülde tutuluyor. Daha büyük değişikliklerde gözetilecek sorumluluk sınırları mimari belgede açıklanmıştır.

## Sorumlu kullanım

- Yalnızca size ait veya incelemek için izin aldığınız yedekleri işleyin.
- Çıkarılan mesajları, medyayı, veritabanlarını, XML dosyalarını ve günlükleri hassas kişisel veri olarak değerlendirin.
- Gerçek yedekleri, anahtarları, kişisel dosya yollarını veya çıkarılmış kayıtları sorun bildirimlerinde ya da pull request'lerde yayımlamayın.
- İşlem eksik sonuç verebilir veya bozuk dosyalar üretebilir. Özgün yedeğin değiştirilmemiş bir kopyasını daima koruyun.

## Lisans

MIT. Ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.
