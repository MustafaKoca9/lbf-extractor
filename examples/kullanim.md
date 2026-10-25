# Kullanım örnekleri

Bu rehber ana [README](../README.tr.md) dosyasını tamamlar. Komut satırı aracına verdiğiniz gibi birincil `.lbf` dosyasının yolunu kullanın.

## 1. Yedeği dışa aktarma

```bash
lbf-extractor telefon_yedegi.lbf --output ./kurtarilan
```

Çıktı dizininde çözümlenmiş başlık, uygulama paketleri, yeniden oluşturulmuş medya yolları, kategorilere ayrılmış kayıtlar ve (özelliği kapatmadıysanız) başvurulmayan bayt aralıkları bulunabilir. Dosya adları yedek üstverisine göre değişir.

## 2. Çok parçalı yedeği inceleme

LG Mobile Switch yedekleri `.lbf0`, `.lbf1` ve `.lbf` gibi parçalara ayrılabilir. Varsayılan sıralama önce numaralı parçalar, sonra `.lbf` dosyasıdır. Birincil `.lbf` dosyasını belirtin:

```bash
lbf-extractor telefon_yedegi.lbf --output ./kurtarilan --debug
```

Yedeğin `.lbf` parçası ilk sıradaysa:

```bash
lbf-extractor telefon_yedegi.lbf --split-lbf-first
```

Kurtarılan verilere güvenmeden önce hata ayıklama çıktısını inceleyerek parça sırasını doğrulayın.

## 3. Adli inceleme günlüğünü saklama

```bash
lbf-extractor telefon_yedegi.lbf --output ./inceleme --debug --log calistirma.log
```

Üstveride işaret edilmeyen ham aralıkları atlamak için `--no-unmapped` kullanın. Aksi durumda bu aralıklar, dosya adlarında bayt ofsetleri yer alacak şekilde `unmapped/` dizinine yazılır. Ayrı dosya-kurtarma araçları gerekebilir; bu aralıkların eksiksiz dosyaları temsil ettiği garanti edilmez.

Terminal çıktısını renksiz almak için `NO_COLOR=1` ayarlayın:

```bash
NO_COLOR=1 lbf-extractor telefon_yedegi.lbf --output ./inceleme --debug --log calistirma.log
```

Günlükleri paylaşmadan önce kişisel dosya yollarını ve üstverileri temizleyin.

## 4. Python API'sini kullanma

```python
from lbf_extractor import LBFExtractor

with LBFExtractor(
    "telefon_yedegi.lbf",
    output_dir="./kurtarilan",
    try_path_reconstruct=True,
    overwrite=False,
    extract_unmapped=True,
    debug=False,
    log_file="calistirma.log",
) as extractor:
    extractor.execute()

print("Aktarılan:", extractor.stats.extracted)
print("Başarısız:", extractor.stats.failed)

for record in extractor.audit_failed:
    print(record)
```

## 5. Hata bildirimine hazırlanma

Sürüm ve ortam bilgilerini toplayın:

```bash
lbf-extractor --version
python --version
python -c "import platform; print(platform.platform())"
```

Kullanılan tam komutu ve kişisel bilgilerden arındırılmış `--debug` çıktısını ekleyin. Gerçek yedek veya kurtarılan kişisel içerik paylaşmayın. Mümkünse sentetik bir örnek hazırlayın.
