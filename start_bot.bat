@echo off
chcp 65001 >nul
:: ========================================
:: SCRIPT COMPLETO DE INICIALIZAÇÃO
:: Bot WhatsApp com WAHA + Ngrok + API
:: ========================================

setlocal enabledelayedexpansion
title Bot WhatsApp - Inicializador Completo

:: Cores para o terminal
color 0A

echo.
echo ========================================
echo     INICIANDO BOT WHATSAPP 
echo ========================================
echo.

:: Verificar se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  ERRO: Python não encontrado!
    echo    Instale Python 3.10+ e tente novamente.
    pause
    exit /b 1
)

:: Verificar se Docker está instalado e rodando
echo [1/6] Verificando Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo   AVISO: Docker não encontrado!
    echo    Você precisará iniciar o WAHA manualmente.
    set SKIP_WAHA=true
) else (
    echo  Docker encontrado
    set SKIP_WAHA=false
)

:: Verificar se ngrok está instalado
echo [2/6] Verificando Ngrok...
ngrok version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  ERRO: Ngrok não encontrado!
    echo    Baixe em: https://ngrok.com/download
    echo    Ou instale com: winget install ngrok
    pause
    exit /b 1
)
echo  Ngrok encontrado

:: Verificar se Ollama está rodando
echo [3/6] Verificando Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo   AVISO: Ollama não está rodando!
    echo    Inicie o Ollama com: ollama serve
    echo    Continuando em 5 segundos...
    timeout /t 5 /nobreak >nul
)

:: Criar diretórios necessários
if not exist "logs" mkdir logs
if not exist "temp" mkdir temp

:: Verificar arquivo .env
if not exist ".env" (
    echo   Arquivo .env não encontrado, criando...
    call :criar_env_padrao
)

:: Ler variáveis do .env (implementação simplificada)
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    if "%%a"=="WAHA_API_KEY" set WAHA_API_KEY=%%b
    if "%%a"=="PORT" set API_PORT=%%b
)

:: Definir porta padrão se não especificada
if "%API_PORT%"=="" set API_PORT=8000

echo.
echo ========================================
echo    INICIANDO SERVIÇOS
echo ========================================

:: [4/6] Iniciar WAHA via Docker
if "%SKIP_WAHA%"=="false" (
    echo [4/6] Iniciando WAHA...
    
    :: Verificar se container já está rodando
    docker ps --filter "name=^waha-bot$" | findstr "waha-bot" >nul 2>&1
    if %errorlevel% equ 0 (
        echo  Container WAHA já está rodando.
    ) else (
        echo    Parando containers antigos do WAHA...
        docker stop waha-bot 2>nul
        docker rm waha-bot 2>nul
        
        echo    Iniciando novo container WAHA...
        if "%WAHA_API_KEY%"=="" (
            :: Sem API Key
            start /min cmd /c "docker run --name waha-bot -p 3000:3000 devlikeapro/waha"
        ) else (
            :: Com API Key
            start /min cmd /c "docker run --name waha-bot -p 3000:3000 -e WHATSAPP_DEFAULT_ENGINE=WEBJS -e WAHA_SECURITY=sha512:%WAHA_API_KEY% devlikeapro/waha"
        )
        
        echo    Aguardando WAHA inicializar...
        :wait_waha
        timeout /t 2 /nobreak >nul
        curl -s http://localhost:3000 >nul 2>&1
        if %errorlevel% neq 0 goto wait_waha
        echo  WAHA iniciado com sucesso
    )
) else (
    echo [4/6] Pulando WAHA (Docker não disponível)
)

:: [5/6] Iniciar Ngrok
echo [5/6] Iniciando Ngrok...

:: Verificar se ngrok já está rodando
curl -s http://localhost:4040/api/tunnels >nul 2>&1
if %errorlevel% equ 0 (
    echo  Ngrok já está rodando
) else (
    echo    Iniciando túnel ngrok na porta %API_PORT%...
    start "Ngrok Tunnel" /min cmd /c "ngrok http %API_PORT%"
    
    echo    Aguardando ngrok inicializar...
    :wait_ngrok
    timeout /t 2 /nobreak >nul
    curl -s http://localhost:4040/api/tunnels >nul 2>&1
    if %errorlevel% neq 0 goto wait_ngrok
    echo  Ngrok iniciado com sucesso
)

:: Obter URL do ngrok e atualizar .env
echo    Obtendo URL pública do ngrok...
for /f "tokens=*" %%i in ('curl -s http://localhost:4040/api/tunnels ^| python -c "import sys,json; data=json.load(sys.stdin); print(next((t['public_url'] for t in data['tunnels'] if t['proto']=='https'), 'Not found'))"') do set NGROK_URL=%%i

if "%NGROK_URL%"=="Not found" (
    echo   Não foi possível obter URL do ngrok automaticamente
    set NGROK_URL=https://your-ngrok-url.ngrok-free.app
) else (
    echo  URL obtida: %NGROK_URL%
    :: Atualizar .env com a nova URL
    call :atualizar_env_ngrok "%NGROK_URL%"
)

:: [6/6] Iniciar API
echo [6/6] Iniciando API FastAPI...

:: Verificar se API já está rodando
curl -s http://localhost:%API_PORT% >nul 2>&1
if %errorlevel% equ 0 (
    echo  API já está rodando na porta %API_PORT%
) else (
    
    echo    Iniciando servidor FastAPI...
    start "Bot API" /min cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port %API_PORT% --reload"
    
    echo    Aguardando API inicializar...
    :wait_api
    timeout /t 2 /nobreak >nul
    curl -s http://localhost:%API_PORT% >nul 2>&1
    if %errorlevel% neq 0 goto wait_api
    echo  API iniciada com sucesso
)

:: Verificações finais
echo.
echo ========================================
echo    VERIFICAÇÕES FINAIS
echo ========================================

echo Testando conectividade dos serviços...

:: Testar API
curl -s http://localhost:%API_PORT% >nul 2>&1
if %errorlevel% equ 0 (
    echo  API: Funcionando
) else (
    echo  API: Não responde
)

:: Testar WAHA
if "%SKIP_WAHA%"=="false" (
    curl -s http://localhost:3000 >nul 2>&1
    if %errorlevel% equ 0 (
        echo  WAHA: Funcionando
    ) else (
        echo  WAHA: Não responde
    )
) else (
    echo   WAHA: Não testado
)

:: Testar Ngrok
curl -s http://localhost:4040 >nul 2>&1
if %errorlevel% equ 0 (
    echo  Ngrok: Funcionando
) else (
    echo  Ngrok: Não responde
)

color 0A
echo.
echo ========================================
echo     SISTEMA INICIADO COM SUCESSO! 
echo ========================================
echo.
echo  INFORMAÇÕES IMPORTANTES:
echo ├─ API Local:      http://localhost:%API_PORT%
echo ├─ API Docs:       http://localhost:%API_PORT%/docs
echo ├─ WAHA:           http://localhost:3000
echo ├─ Ngrok Admin:    http://localhost:4040
echo └─ URL Pública:    %NGROK_URL%
echo.
echo  WEBHOOK URL PARA WAHA:
echo    %NGROK_URL%/webhook/whatsapp
echo.
echo  PRÓXIMOS PASSOS:
echo 1. Configure o WhatsApp no WAHA (acesse http://localhost:3000)
echo 2. Use a URL webhook: %NGROK_URL%/webhook/whatsapp
echo 3. Escaneie o QR Code para conectar seu WhatsApp
echo 4. Teste enviando mensagens!
echo.
echo  EXEMPLOS DE MENSAGENS PARA TESTAR:
echo    "Quais os 5 produtos mais vendidos este mês?"
echo    "Qual o limite de crédito do cliente João?"
echo    "Mostre os pedidos do cliente 123"
echo.
echo   IMPORTANTE: Mantenha esta janela aberta!
echo    Para parar todos os serviços, pressione Ctrl+C
echo.

:: Abrir URLs importantes no navegador
echo Abrindo páginas importantes no navegador...
start http://localhost:%API_PORT%/docs
start http://localhost:3000
start http://localhost:4040

echo.
echo Pressione qualquer tecla para abrir o monitor do sistema...
pause >nul

:: Iniciar monitor
python monitor.py

goto :eof

:criar_env_padrao
echo # Configurações do Bot WhatsApp > .env
echo OLLAMA_BASE_URL=http://localhost:11434 >> .env
echo LLM_MODEL=llama3.1 >> .env
echo WAHA_BASE_URL=http://localhost:3000 >> .env
echo WAHA_API_KEY=sha512:c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec >> .env
echo WHATSAPP_SESSION_NAME=default >> .env
echo BOT_TIMEOUT_MINUTES=30 >> .env
echo MAX_CONTEXT_MESSAGES=10 >> .env
echo DEBUG_MODE=True >> .env
echo PORT=8000 >> .env
echo HOST=0.0.0.0 >> .env
echo LOG_LEVEL=INFO >> .env
echo LOG_DIR=logs >> .env
goto :eof

:atualizar_env_ngrok
set NOVA_URL=%~1
:: Criar arquivo temporário
> .env.tmp (
    for /f "usebackq delims=" %%a in (".env") do (
        set "linha=%%a"
        if "!linha:~0,9!"=="NGROK_URL" (
            echo NGROK_URL=%NOVA_URL%
        ) else (
            echo %%a
        )
    )
)
move .env.tmp .env >nul
goto :eof