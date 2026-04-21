@echo off
REM SSL Sertifikası Oluşturma Scripti (Windows)
REM Bu script self-signed SSL sertifikası oluşturur

echo ============================================
echo SSL Sertifikası Oluşturma
echo ============================================
echo.

REM SSL klasörünü oluştur
if not exist ssl mkdir ssl

REM OpenSSL yüklü mü kontrol et
where openssl >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] OpenSSL bulunamadi!
    echo.
    echo OpenSSL kurulumu icin:
    echo 1. https://slproweb.com/products/Win32OpenSSL.html adresinden indirin
    echo 2. Veya: choco install openssl (Chocolatey ile)
    echo 3. Veya: winget install ShiningLight.OpenSSL
    echo.
    pause
    exit /b 1
)

echo OpenSSL bulundu, sertifika olusturuluyor...
echo.

REM Self-signed sertifika oluştur
openssl req -x509 -nodes -days 365 -newkey rsa:2048 ^
    -keyout ssl/server.key ^
    -out ssl/server.crt ^
    -subj "/CN=localhost/O=StaffPlanner/C=TR"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [BASARILI] SSL sertifikasi olusturuldu!
    echo.
    echo Dosyalar:
    echo   - ssl/server.crt (Sertifika)
    echo   - ssl/server.key (Ozel anahtar)
    echo.
    echo HTTPS ile calistirmak icin:
    echo   docker-compose -f docker-compose.https.yml up -d
    echo.
    echo Uyari: Self-signed sertifika tarayicida guvenlik uyarisi verir.
    echo        Uretim ortaminda Let's Encrypt veya gercek sertifika kullanin.
) else (
    echo.
    echo [HATA] Sertifika olusturulamadi!
)

pause
