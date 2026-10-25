# Güvenlik politikası

## Kapsam

`lbf-extractor`, güvenilmeyen ikili `.lbf` verilerini ayrıştırır ve kurtarılan içeriği diske yazar. Şu konulardaki bildirimler özellikle değerlidir:

- Dizin geçişi veya seçilen çıktı dizininin dışına yazma.
- Hatalı ofsetlerin, uzunlukların, başlıkların ya da XML verisinin güvenli olmayan davranışa yol açması.
- Beklenmeyen dosya üzerine yazma veya diğer dosya sistemi yan etkileri.
- Özel hazırlanmış arşivleri incelemeyi güvensiz hâle getiren çökmeler veya güvenlik sınırı ihlalleri.

Dışa aktarıcı çıktı yollarını denetler, okuma sınırlarını kontrol eder, başlık boyutunu sınırlar ve başarısız işlemleri kaydeder. Bu önlemler riski azaltır ancak her bozuk arşivin güvenli olduğunu garanti etmez.

## Güvenlik açığını özel olarak bildirme

**Güvenlikle ilgili hassas ayrıntıları herkese açık bir issue içinde yayımlamayın.**

Varsa deponun özel güvenlik bildirimi özelliğini kullanın: deponun **Security** sekmesini açıp **Report a vulnerability** seçeneğini seçin. Bu seçenek yoksa GitHub profilindeki iletişim bilgileri üzerinden bakım sorumlusuna ulaşın.

Asgari bir sentetik örnek, kullanılan tam komut, beklenen ve gözlenen davranış ile kişisel bilgilerden arındırılmış hata günlüğünü ekleyin. Gerçek yedek veya kişisel veri eklemeyin.

## Sınırlamalar

- LG biçimindeki sabit AES anahtarı biçimin kendi özelliğidir; tek başına bu programda güvenlik açığı olduğu anlamına gelmez.
- Yol denetimleri, önceden hazırlanmış her sembolik bağlantı veya güvenilmeyen çıktı dizini düzenine karşı mutlak koruma sağlamaz.
- Büyük arşivler ciddi disk alanı tüketebilir. Akış tabanlı işleme bellek kullanımını sınırlar; yazılabilecek veri miktarını değil.
- Sonuçlar eksik veya bozuk olabilir. Özgün yedeği değiştirmeden saklayın.
