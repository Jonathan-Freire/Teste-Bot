@echo off
echo ========================================
echo      INICIANDO BOT WHATSAPP
echo ========================================

echo.
echo [1/4] Iniciando Ngrok...
start "Ngrok" cmd /k "ngrok http 8000"

echo.
echo [2/4] Aguardando Ngrok inicializar...
timeout /t 5 /nobreak > nul

echo.
echo [3/4] Iniciando API...
start "API Bot" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [4/4] Aguardando API inicializar...
timeout /t 5 /nobreak > nul

echo.
echo ========================================
echo   BOT INICIADO COM SUCESSO!
echo ========================================
echo.
echo Acesse:
echo - API: http://localhost:8000/docs
echo - Ngrok: http://localhost:4040
echo.
echo IMPORTANTE: 
echo 1. Copie a URL HTTPS do ngrok
echo 2. Cole no arquivo .env (NGROK_URL=...)
echo 3. Configure o WhatsApp no WAHA
echo.
pause