import sys
import pytest

# Skip entire module if tkinter is unavailable (headless CI)
tkinter_available = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception:
    tkinter_available = False

pytestmark = pytest.mark.skipif(
    not tkinter_available, reason="tkinter not available or no display"
)

if tkinter_available:
    from unittest.mock import patch, MagicMock
    from downloader.app import MainWindow


@pytest.fixture
def app(monkeypatch):
    """Create a MainWindow without showing it."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    window = MainWindow(root)
    yield window
    root.destroy()


def test_app_starts_with_empty_url_box(app):
    text = app.url_text.get("1.0", "end-1c")
    assert text == ""


def test_app_starts_with_no_output_folder(app):
    assert app.output_folder.get() == ""


def test_download_button_disabled_without_folder(app):
    # Paste a URL but no folder selected
    app.url_text.insert("1.0", "https://youtube.com/watch?v=abc")
    app._on_url_change()
    state = str(app.download_btn["state"])
    assert state == "disabled"


def test_browse_sets_output_folder(app):
    with patch("downloader.app.filedialog.askdirectory", return_value="/my/music"):
        app._browse_folder()
    assert app.output_folder.get() == "/my/music"


def test_download_calls_service(app):
    app.url_text.insert("1.0", "https://youtube.com/watch?v=abc")
    app.output_folder.set("/tmp/out")

    with patch.object(app.service, "download_all") as mock_dl:
        app._start_download()
        mock_dl.assert_called_once()
        items, out_dir, callback = mock_dl.call_args[0]
        assert out_dir == "/tmp/out"
        assert len(items) == 1
        assert items[0].url == "https://youtube.com/watch?v=abc"


def test_status_label_updates_on_callback(app):
    from downloader.models import DownloadItem, DownloadStatus

    item = DownloadItem(url="https://youtube.com/watch?v=abc", status=DownloadStatus.DONE)
    app._on_status_change(item)
    app.root.update()  # process pending after() callbacks

    # Find label for this URL and verify it shows DONE
    label_text = app.status_labels[item.url]["text"]
    assert "DONE" in label_text or "done" in label_text.lower()
