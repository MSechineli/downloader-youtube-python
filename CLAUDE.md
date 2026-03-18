# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Ignored Paths

The `.devcontainer/` folder must be ignored — do not read, modify, or suggest changes to files inside it.

---

## Project: YouTube to MP3 Downloader

A desktop GUI application built with Python (TDD approach) that downloads YouTube videos and converts them to MP3 audio files. Located at `/workspace/downloader/`.

## Tech Stack

- **Language:** Python 3.10+
- **GUI:** tkinter (built-in)
- **Downloader:** yt-dlp (≥2024.1.0)
- **Audio conversion:** ffmpeg (external system dependency)
- **Tests:** pytest (≥8.0.0) + pytest-cov (≥5.0.0)
- **Concurrency:** Python threading

## File Structure

```
downloader/
├── requirements.txt             # Runtime dependencies (yt-dlp)
├── requirements-dev.txt         # Dev dependencies (pytest, pytest-cov)
├── run.sh / run.bat             # Launcher scripts
├── downloader/
│   ├── models.py                # DownloadStatus enum + DownloadItem dataclass
│   ├── url_parser.py            # URL validation and parsing
│   ├── downloader.py            # DownloadService (core download engine)
│   └── app.py                   # MainWindow (tkinter GUI)
└── tests/
    ├── conftest.py              # FakeYDL mock + pytest fixtures
    ├── test_models.py
    ├── test_url_parser.py
    ├── test_downloader.py
    └── test_app_integration.py  # Skipped if no display available
```

## How to Run

```bash
cd /workspace/downloader
./run.sh           # Linux/macOS
# or
python -m downloader.app
```

## How to Test

```bash
pip install -r requirements-dev.txt

# All tests (GUI tests auto-skipped in headless env)
python -m pytest tests/ -v

# Unit tests only (no display needed)
python -m pytest tests/test_models.py tests/test_url_parser.py tests/test_downloader.py -v

# With coverage
python -m pytest tests/ --cov=downloader --cov-report=term-missing
```

## Architecture

- **models.py** — `DownloadStatus` (PENDING, IN_PROGRESS, DONE, FAILED) and `DownloadItem` dataclass
- **url_parser.py** — Validates youtube.com/watch, youtu.be, youtube.com/shorts URLs
- **downloader.py** — Spawns background thread; yt-dlp extracts best audio → FFmpegExtractAudio MP3 192kbps; accepts `ydl_factory` for dependency injection
- **app.py** — Dark-themed tkinter GUI; thread-safe updates via `root.after(0, ...)`; status icons: ○ → ↓ → ✓/✗

## Development Approach

- **TDD:** All tests written before implementation
- **Dependency injection:** `DownloadService` accepts `ydl_factory` for testing
- **Error isolation:** One download failure does not stop others
- **Language:** UI and README are in Brazilian Portuguese (pt-BR); code comments in English
