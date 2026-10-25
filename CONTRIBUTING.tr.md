# Katkıda bulunma

`lbf-extractor` projesini geliştirmeye katkı verdiğiniz için teşekkürler. Mevcut komut satırı arayüzünü ve Python API'sini değiştirmek bilinçli bir tercih değilse küçük, sınanabilir ve geriye dönük uyumlu değişiklikleri tercih edin. Arşiv okuma, üstveri ayrıştırma, çıktı politikası ve payload çıkarma bileşenlerini birbirinden bağımsız tutun.

## Başlamadan önce

- Yalnızca size ait veya incelemek için yetkilendirildiğiniz yedeklerle çalışın.
- Gerçek bir `.lbf` yedeğini ya da çıkarılmış kişisel verileri issue veya pull request ekine koymayın. Sentetik test verisi kullanın.
- Çalışma zamanı bağımlılıklarını az tutun. Tek çalışma zamanı bağımlılığı PyCryptodome'dur.
- Yeni seçenekler veya davranışlar için README dosyalarının her iki dil sürümünü ve kullanım örneklerini güncelleyin.

## Geliştirme ortamını hazırlama

```bash
git clone https://github.com/MustafaKoca9/lbf-extractor.git
cd lbf-extractor
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Pull request öncesi kontroller

```bash
pytest -q
python -m py_compile lbf_extractor/*.py
lbf-extractor --version
```

Komut satırı davranışı değişiyorsa ayrıştırıcı testlerini ekleyin veya güncelleyin. İkili veri ayrıştırması değişiyorsa gerçek kişisel yedekler yerine sentetik örneklerle test yazın.

## Proje kuralları

- Python 3.9 ve üzerini destekleyin.
- Yeni herkese açık fonksiyon ve metotlara tür açıklamaları ekleyin.
- Standart kütüphaneyi tercih edin; gereksiz çalışma zamanı bağımlılıkları eklemeyin.
- Akış tabanlı davranışı koruyun: büyük yedeğin tamamını belleğe okumayın.
- Arşiv verisini okumadan veya yazmadan önce ofset ve uzunlukları doğrulayın.
- Çıkarılan dosya yollarının seçilen çıktı dizini içinde kalmasını sağlayın.
- README, komut satırı yardımı, kullanım örnekleri ve değişiklik günlüğünü birbiriyle uyumlu tutun.
- Sürüm yayıma hazırlanırken `lbf_extractor/common.py` içindeki `__version__` ile `pyproject.toml` içindeki `version` değerini birlikte güncelleyin.

## Commit mesajları

Conventional Commits biçimini kullanın. Örnekler:

- `fix: çok parçalı segment sınırlarını doğrula`
- `docs: kurtarma çıktısını açıkla`
- `test: hatalı başlık uzunluklarını kapsa`
- `chore: geliştirme bağımlılıklarını güncelle`

## Hata bildirimi

Uygulama sürümünü, işletim sistemini, Python sürümünü, çalıştırılan komutu ve kişisel bilgilerden arındırılmış hata günlüğünü ekleyin. Gerçek yedekleri, çıkarılan dosyaları, kişisel yolları veya cihaz sahibini belirleyebilecek üstverileri yüklemeyin.

Güvenlik açıkları için [SECURITY.tr.md](SECURITY.tr.md) yönergelerini izleyin ve herkese açık issue yerine özel bildirim kanalını kullanın.
