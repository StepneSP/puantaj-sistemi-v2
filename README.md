# 💳 Puantaj Sistemi — Streamlit

Klavye tipi USB kart okuyucu kullanan kurumlar için başlangıç/üretim adayı puantaj uygulaması.

## Temel kurallar

- Mola takibi yoktur.
- Bir takvim gününde en az bir kart hareketi = çalışma günü.
- Hafta Pazartesi–Pazar kabul edilir.
- Bir personel aynı hafta içinde 7 farklı gün çalıştıysa 7. çalışma günü için **9 saat ek mesai** hesaplanır.
- Aylık puantaj, ay içindeki farklı çalışma günlerinin toplamıdır.
- Kart hareketleri ham veri olarak SQLite'ta saklanır.
- Manuel giriş/çıkış düzeltmesi yapılabilir.
- İzin ve resmî tatil kayıtları tutulabilir.
- Personel pasifleştirilirse eski kart hareketleri korunur.

> Bu yazılım kurum içi operasyonel puantaj için hazırlanmıştır. Bordro ve iş hukuku uygulaması olarak kullanılmadan önce kurumunuzun İK/muhasebe kurallarıyla doğrulanmalıdır.

## 1. Lokal kurulum

Python 3.11+ önerilir.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Ardından:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 2. İlk personel/kart kaydı

1. Sol menü → **Personeller**
2. **Yeni personel / kart tanımla**
3. Kart okuyucuyu USB ile bağlayın.
4. `Kart No` alanına tıklayın.
5. Kartı okutun.
6. Ad soyad ve diğer bilgileri girin.
7. Personeli kaydedin.

Klavye tipi okuyucu kartı bir metin/numara gibi gönderir. Bu nedenle özel SDK gerekmez.

## 3. Günlük kullanım

**Kart Okutma** ekranını bilgisayarda açık bırakın.

İlk okutma:

```text
07:58 → giriş
```

Son okutma:

```text
17:04 → çıkış
```

Aradaki kart hareketleri ham kayıt olarak tutulabilir; mola hesabı yapılmaz.

## 4. 7. gün hesabı

Örnek:

| Pzt | Sal | Çar | Per | Cum | Cmt | Paz |
|---|---|---|---|---|---|---|
| ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Bu hafta için:

**6 normal çalışma günü + 9 saat ek mesai**

oluşur.

Eğer personel haftada yalnızca 6 farklı günde çalıştıysa ek mesai oluşmaz.

## 5. Manuel düzeltme

Kart okutmayı unutan personel için:

**Düzeltmeler / İzin → Kart hareketi düzeltmesi**

ile manuel giriş/çıkış eklenebilir.

Bu işlem `MANUEL` kaynak etiketiyle tutulur.

## 6. İzin ve resmî tatil

İzin kayıtları ayrı tabloda tutulur. Resmî tatil altyapısı veritabanında hazırdır.

Üretimde kullanmadan önce kurumunuzun:

- yıllık izin,
- rapor,
- ücretsiz izin,
- resmî tatil,
- eksik gün

kurallarının kesinleştirilmesi önerilir.

## 7. GitHub

Yeni bir GitHub repository oluşturun: `puantaj-sistemi`

Proje klasöründe:

```bash
git init
git add .
git commit -m "Puantaj sistemi v2"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/puantaj-sistemi.git
git push -u origin main
```

## 8. Streamlit Community Cloud

Streamlit Community Cloud'da:

1. GitHub hesabını bağlayın.
2. `puantaj-sistemi` repository'sini seçin.
3. Branch: `main`
4. Main file: `app.py`
5. Deploy.

### Önemli: gerçek kullanım ve veritabanı

SQLite dosyası bu repository'ye gönderilmez (`data/*.db` `.gitignore` içindedir).

Streamlit Cloud üzerinde uygulama yeniden deploy/restart olduğunda lokal SQLite dosyasına güvenmek doğru değildir. Gerçek firma kullanımına geçmeden önce veritabanını kalıcı bir PostgreSQL/Supabase benzeri servise taşımak önerilir.

Kart okuyucu ise fiziksel olarak puantaj bilgisayarına bağlı olduğundan, **Streamlit Cloud'daki uzak uygulamaya doğrudan USB kart okuyucu bağlanamaz**.

Bu nedenle gerçek kullanım için iki mimariden biri tercih edilmelidir:

### A) Yerel Streamlit
Puantaj bilgisayarında çalışır. USB okuyucu doğrudan çalışır. SQLite kullanılabilir.

### B) Yerel kart terminali + uzak veritabanı
Puantaj bilgisayarında kart okuyucuyu dinleyen küçük bir istemci çalışır; veriyi uzak PostgreSQL/Supabase veritabanına gönderir. Yönetim paneli Streamlit Cloud'da olabilir.

Firma içinde gerçek kullanım için **B mimarisi** daha ölçeklenebilirdir.

## 9. Güvenlik

Gerçek kullanım sürümünde mutlaka:

- yönetici giriş sistemi,
- rol/yetki,
- HTTPS,
- veritabanı yedekleme,
- işlem/audit logu,
- manuel değişikliklerin kim tarafından yapıldığının kaydı

eklenmelidir.

## 10. Sonraki geliştirmeler

- Personel bazlı detay sayfası
- Yönetici onayı
- Excel şablonuna doğrudan aktarım
- PDF puantaj
- PostgreSQL/Supabase bağlantısı
- Kullanıcı giriş sistemi
- Audit log
- Çoklu şube/departman
- Vardiya tanımları
- Gece vardiyası desteği
