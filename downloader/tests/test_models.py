from downloader.models import DownloadStatus, DownloadItem


def test_status_enum_has_expected_values():
    assert DownloadStatus.PENDING
    assert DownloadStatus.IN_PROGRESS
    assert DownloadStatus.DONE
    assert DownloadStatus.FAILED


def test_download_item_defaults():
    item = DownloadItem(url="https://youtube.com/watch?v=abc")
    assert item.url == "https://youtube.com/watch?v=abc"
    assert item.status == DownloadStatus.PENDING
    assert item.error_message is None


def test_download_item_is_mutable():
    item = DownloadItem(url="https://youtube.com/watch?v=abc")
    item.status = DownloadStatus.DONE
    assert item.status == DownloadStatus.DONE


def test_download_item_stores_error_message():
    item = DownloadItem(
        url="https://youtube.com/watch?v=abc",
        status=DownloadStatus.FAILED,
        error_message="Network error",
    )
    assert item.error_message == "Network error"
