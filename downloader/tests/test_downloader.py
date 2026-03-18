import time
import threading
import pytest

from downloader.models import DownloadItem, DownloadStatus
from downloader.downloader import DownloadService
from tests.conftest import make_fake_ydl_factory


def _make_items(*urls):
    return [DownloadItem(url=u) for u in urls]


def _run_sync(service, items, out_dir="/tmp/out"):
    """Run download_all and wait for completion."""
    done = threading.Event()
    results = []

    def callback(item):
        results.append((item.url, item.status))
        if item.status in (DownloadStatus.DONE, DownloadStatus.FAILED):
            # Check if all items are settled
            if all(
                i.status in (DownloadStatus.DONE, DownloadStatus.FAILED)
                for i in items
            ):
                done.set()

    service.download_all(items, out_dir, callback)
    done.wait(timeout=5)
    return results


# --- Status tests ---

def test_download_all_sets_status_done_on_success():
    factory = make_fake_ydl_factory()
    service = DownloadService(ydl_factory=factory)
    items = _make_items("https://youtube.com/watch?v=aaa")
    _run_sync(service, items)
    assert items[0].status == DownloadStatus.DONE


def test_download_all_sets_status_failed_on_exception():
    factory = make_fake_ydl_factory(raise_on_url={"https://youtube.com/watch?v=bad"})
    service = DownloadService(ydl_factory=factory)
    items = _make_items("https://youtube.com/watch?v=bad")
    _run_sync(service, items)
    assert items[0].status == DownloadStatus.FAILED
    assert items[0].error_message is not None


def test_download_all_continues_after_one_failure():
    bad_url = "https://youtube.com/watch?v=bad"
    good_url = "https://youtube.com/watch?v=good"
    factory = make_fake_ydl_factory(raise_on_url={bad_url})
    service = DownloadService(ydl_factory=factory)
    items = _make_items(bad_url, good_url)
    _run_sync(service, items)
    assert items[0].status == DownloadStatus.FAILED
    assert items[1].status == DownloadStatus.DONE


# --- Options tests ---

def test_download_all_uses_correct_output_path():
    factory = make_fake_ydl_factory()
    service = DownloadService(ydl_factory=factory)
    items = _make_items("https://youtube.com/watch?v=aaa")
    _run_sync(service, items, out_dir="/my/music")
    opts = factory.instances[0].opts
    assert "/my/music" in opts["outtmpl"]


def test_download_all_requests_mp3_format():
    factory = make_fake_ydl_factory()
    service = DownloadService(ydl_factory=factory)
    items = _make_items("https://youtube.com/watch?v=aaa")
    _run_sync(service, items)
    opts = factory.instances[0].opts
    assert opts["format"] == "bestaudio/best"
    postprocessors = opts["postprocessors"]
    assert any(
        p.get("key") == "FFmpegExtractAudio" and p.get("preferredcodec") == "mp3"
        for p in postprocessors
    )


# --- Callback tests ---

def test_download_all_fires_callback_per_item():
    factory = make_fake_ydl_factory()
    service = DownloadService(ydl_factory=factory)
    url1 = "https://youtube.com/watch?v=aaa"
    url2 = "https://youtube.com/watch?v=bbb"
    items = _make_items(url1, url2)

    callback_items = []
    done = threading.Event()

    def callback(item):
        callback_items.append(item.url)
        if all(i.status in (DownloadStatus.DONE, DownloadStatus.FAILED) for i in items):
            done.set()

    service.download_all(items, "/tmp/out", callback)
    done.wait(timeout=5)

    # Each item gets at least one callback (IN_PROGRESS + DONE/FAILED = 2 each)
    assert callback_items.count(url1) >= 2
    assert callback_items.count(url2) >= 2


# --- Threading test ---

def test_download_all_runs_in_thread():
    """download_all must return immediately without blocking."""
    import time

    slow_called = threading.Event()
    returned_at = None

    class SlowYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def download(self, urls):
            slow_called.set()
            time.sleep(0.3)

    service = DownloadService(ydl_factory=SlowYDL)
    items = _make_items("https://youtube.com/watch?v=aaa")

    start = time.monotonic()
    service.download_all(items, "/tmp/out", lambda item: None)
    elapsed = time.monotonic() - start

    # Should return well before the 0.3s sleep in SlowYDL
    assert elapsed < 0.2, f"download_all blocked for {elapsed:.3f}s"
    slow_called.wait(timeout=2)  # confirm thread actually ran
