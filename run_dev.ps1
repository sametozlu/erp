# Development için çalıştırma scripti
# Bu script cache'i temizler ve uygulamayı debug modunda çalıştırır

Write-Host "Python cache temizleniyor..." -ForegroundColor Yellow
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\tests\__pycache__ -ErrorAction SilentlyContinue

Write-Host "Uygulama başlatılıyor (DEBUG modu açık)..." -ForegroundColor Green
$env:DEBUG = "1"
& "C:\Users\burak\AppData\Local\Programs\Python\Python312\python.exe" app.py

