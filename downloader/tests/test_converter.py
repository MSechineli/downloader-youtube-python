import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from downloader.models import ConversionItem, DownloadStatus, OutputFormat
from downloader.converter import ConvertService, AUDIO_EXTS


def _make_items(*paths):
    return [ConversionItem(input_path=p) for p in paths]


def _run_sync(service, items, out_dir="/tmp/out", fmt=OutputFormat.MP3):
    done = threading.Event()
    results = []

    def callback(item):
        results.append((item.input_path, item.status))
        if all(i.status in (DownloadStatus.DONE, DownloadStatus.FAILED) for i in items):
            done.set()

    service.convert_all(items, out_dir, fmt, callback)
    done.wait(timeout=5)
    return results


def _make_service_with_mock(returncode=0, stderr=b""):
    mock_result = MagicMock()
    mock_result.returncode = returncode
    mock_result.stderr = stderr
    svc = ConvertService(ffmpeg_path="/fake/ffmpeg")
    return svc, mock_result


# --- Status tests ---

def test_convert_all_sets_done_on_success():
    svc, mock_result = _make_service_with_mock(returncode=0)
    items = _make_items("/tmp/a.mp3")
    with patch("subprocess.run", return_value=mock_result):
        _run_sync(svc, items)
    assert items[0].status == DownloadStatus.DONE


def test_convert_all_sets_failed_on_nonzero():
    svc, mock_result = _make_service_with_mock(returncode=1, stderr=b"error msg")
    items = _make_items("/tmp/a.mp3")
    with patch("subprocess.run", return_value=mock_result):
        _run_sync(svc, items)
    assert items[0].status == DownloadStatus.FAILED
    assert items[0].error_message is not None


def test_convert_all_continues_after_one_failure():
    svc = ConvertService(ffmpeg_path="/fake/ffmpeg")

    call_count = [0]

    def fake_run(cmd, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        result.returncode = 1 if call_count[0] == 1 else 0
        result.stderr = b"fail" if call_count[0] == 1 else b""
        return result

    items = _make_items("/tmp/a.mp3", "/tmp/b.wav")
    with patch("subprocess.run", side_effect=fake_run):
        _run_sync(svc, items)

    assert items[0].status == DownloadStatus.FAILED
    assert items[1].status == DownloadStatus.DONE


def test_convert_all_runs_in_thread():
    import time

    slow_called = threading.Event()

    def slow_run(cmd, **kwargs):
        slow_called.set()
        time.sleep(0.3)
        r = MagicMock()
        r.returncode = 0
        return r

    svc = ConvertService(ffmpeg_path="/fake/ffmpeg")
    items = _make_items("/tmp/a.mp3")

    start = time.monotonic()
    svc.convert_all(items, "/tmp/out", OutputFormat.MP3, lambda i: None)
    elapsed = time.monotonic() - start

    assert elapsed < 0.2, f"convert_all blocked for {elapsed:.3f}s"
    slow_called.wait(timeout=2)


def test_convert_all_fails_all_when_ffmpeg_missing():
    with patch("shutil.which", return_value=None):
        svc = ConvertService()
    items = _make_items("/tmp/a.mp3", "/tmp/b.wav")
    _run_sync(svc, items)
    assert all(i.status == DownloadStatus.FAILED for i in items)
    assert all("ffmpeg" in (i.error_message or "").lower() for i in items)


# --- _build_cmd tests ---

def _svc():
    return ConvertService(ffmpeg_path="/usr/bin/ffmpeg")


def test_build_cmd_mp3():
    cmd = _svc()._build_cmd("/in/a.wav", "/out/a.mp3", OutputFormat.MP3)
    assert "-c:a" in cmd and "libmp3lame" in cmd
    assert "-vn" in cmd


def test_build_cmd_m4a():
    cmd = _svc()._build_cmd("/in/a.mp3", "/out/a.m4a", OutputFormat.M4A)
    assert "aac" in cmd
    assert "-vn" in cmd


def test_build_cmd_wav():
    cmd = _svc()._build_cmd("/in/a.mp3", "/out/a.wav", OutputFormat.WAV)
    assert "pcm_s16le" in cmd
    assert "-vn" in cmd


def test_build_cmd_ogg():
    cmd = _svc()._build_cmd("/in/a.mp3", "/out/a.ogg", OutputFormat.OGG)
    assert "libvorbis" in cmd
    assert "-vn" in cmd


def test_build_cmd_mp4_from_audio():
    cmd = _svc()._build_cmd("/in/a.mp3", "/out/a.mp4", OutputFormat.MP4)
    assert "lavfi" in cmd
    assert any("color=black" in arg for arg in cmd)
    assert "libx264" in cmd


def test_build_cmd_mp4_from_video():
    cmd = _svc()._build_cmd("/in/a.mp4", "/out/b.mp4", OutputFormat.MP4)
    assert "lavfi" not in cmd
    assert "libx264" in cmd


def test_same_format_same_dir_gets_converted_suffix():
    svc = ConvertService(ffmpeg_path="/fake/ffmpeg")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    items = _make_items("/tmp/out/song.mp3")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        _run_sync(svc, items, out_dir="/tmp/out", fmt=OutputFormat.MP3)

    called_cmd = mock_run.call_args[0][0]
    output_arg = called_cmd[-1]
    assert "_converted" in output_arg
