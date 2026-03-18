@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

python -c "import yt_dlp" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    python -m pip install -r requirements.txt
)

rem Sempre atualiza o yt-dlp — YouTube muda a API com frequencia
echo Atualizando yt-dlp...
python -m pip install -q --upgrade yt-dlp

python -m downloader.app
