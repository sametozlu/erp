@echo off
REM Development için çalıştırma scripti
echo Python cache temizleniyor...
if exist __pycache__ rmdir /s /q __pycache__
if exist tests\__pycache__ rmdir /s /q tests\__pycache__

echo Uygulama başlatılıyor (DEBUG modu açık)...
set DEBUG=1
"C:\Users\burak\AppData\Local\Programs\Python\Python312\python.exe" app.py

