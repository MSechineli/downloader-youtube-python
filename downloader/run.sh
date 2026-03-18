#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Install dependencies if needed
if ! python3 -c "import yt_dlp" 2>/dev/null; then
    echo "Instalando dependencias..."
    python3 -m pip install -r requirements.txt
fi

# Always update yt-dlp — YouTube muda a API com frequencia
echo "Atualizando yt-dlp..."
python3 -m pip install -q --upgrade yt-dlp

python3 -m downloader.app
