# Code Audit

Tarih: 2025-12-29

## Kapsam / Yontem
- Statik tarama: `rg` ile route/decorator, `print/TODO`, upload, mail, CSRF, exception bloklari.
- Runtime kontrol: `python -m py_compile app.py`, `from app import app` ile URL map ve template render smoke-test.
- Odak: runtime 500 riskleri, guvenlik (CSRF/secret/log/upload), performans (SQLite lock / network).

## Uygulanan duzeltmeler (ozet)
- `app.py:1997` `api_cell_clear` endpoint'i icin eksik route dekoratoru eklendi: `/api/cell/clear` (JS bu endpoint'i cagiriyordu).
- `app.py:3273` `api_send_weekly_emails` ve `app.py:3418` `api_send_team_emails` icin:
  - SQL query sonuc unpack hatalari duzeltildi (Team.name + PlanCell.team_name).
  - Gonderim basari/hatada `MailLog` kaydi ve dogru meta/subject eklendi.
  - Mail HTML'i `templates/email_base.html` ile standart hale getirildi.
- `app.py:705` upload silme fonksiyonunda path traversal kontrolu (dosya adi icinde `..`, `/`, `\\` varsa silmiyor).
- `app.py:47` rotating file logging eklendi: `instance/logs/app.log` (hata detaylari burada).
- `app.py:1002` admin POST formlarinda basic CSRF dogrulamasi eklendi; ilgili admin formlarina token konuldu:
  - `templates/mail_settings.html:8`
  - `templates/admin_user_add.html:8`
  - `templates/admin_user_edit.html:7`
- `app.py:2733` harita marker endpoint'i secilen haftaya gore filtrelenecek sekilde duzeltildi.
- `app.py:2362` `api_person_week` icinde olmayan alan erisimi `getattr` ile guvenli hale getirildi (runtime 500 riski).
- Debug `print()` kalintilari kaldirildi / logger'a tasindi.

## Bulgular (dosya/satir/seviye/oneri)

| ID | Dosya:Satir | Seviye | Bulgu | Oneri | Durum |
|---|---|---|---|---|---|
| R-01 | `app.py:1997` | High | Frontend `/api/cell/clear` cagiriyor ama route dekoratoru yoktu, 404/func calismiyordu. | Route dekoratoru ekle ve smoke-test ile URL map dogrula. | Fixed |
| R-02 | `app.py:3273` | High | Haftalik mail gonderiminde query tuple unpack uyusmazligi ve yanlis hata log/meta nedeniyle 500 riski. | Query select/unpack esit olsun; success/fail log/meta dogru olsun; template tek tip olsun. | Fixed |
| R-03 | `app.py:3418` | High | Ekip mail gonderiminde query Team.name + PlanCell.team_name uyusmazligi ve yanlis fail log/meta (weekly yaziyordu). | Select/unpack duzelt; subject/meta/type dogru olsun. | Fixed |
| S-01 | `app.py:1002` | Medium | CSRF sadece admin HTML POST formlarinda var; diger HTML POST formlari (projects/people/tools vb.) CSRF'siz. | Tum HTML form POST'lari icin CSRF ekle (tercihen Flask-WTF). | Open |
| S-02 | `app.py:720` | Medium | SMTP sifresi `instance/mail_settings.json` icinde duz metin (izinler sikilastirilsa da risk). | OS secret store / env-only model / encryption anahtar yonetimi dusun. | Mitigated (perm + mask), still Open |
| S-03 | `app.py:665` | Low | Upload uzanti allowlist var ama dosya boyutu limiti/icerik sniffing yok. | `MAX_CONTENT_LENGTH` ayarla, buyuk ekler icin uyar/limit koy. | Open |
| P-01 | `app.py:93` | Medium | SQLite migrasyon/seed islemleri coklu process ortaminda lock/yaris kosulu riski tasir (process-basi guard var). | Uretimde tek process/worker ya da dis DB (Postgres) + migration tool (Alembic). | Open |
| P-02 | `app.py:640` | Low | Nominatim dis istek (timeout=8) plan/harita acilisini yavaslatabilir. | Cache TTL, arka planda preload veya offline koordinat tablosu. | Open |
| Q-01 | `app.py` geneli | Low | Kodlama/encoding bozulmalari (TR karakter) okunabilirligi dusuruyor. | Tum dosyalari UTF-8 (no BOM) standardize et; console encoding ayarla. | Open |

Notlar:
- `...` ile belirtilen satirlar: repo degiskenligine gore yaklasik bolgeyi ifade eder (ilgili fonksiyon isimleri ile bulunabilir).

## Guvenlik kontrol checklist (mevcut durum)
- SMTP secrets loga dusmesin: exception loglari `err=%s` ile sinirli; ayarlari dump etmiyor (OK).
- Upload path traversal: `secure_filename` + allowlist + `delete_upload()` guard (OK).
- CSRF: admin HTML POST path'lerinde aktif; JSON `/api/*` istekleri kapsam disi (kabul edilebilir ama raporlandi).
- Hata yakalama/log: kritik noktalar `log.exception(...)` ile loglaniyor; kullaniciya sade mesaj (OK).
