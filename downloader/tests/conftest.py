import pytest


class FakeYDL:
    """Simulates yt_dlp.YoutubeDL for testing without network calls."""

    def __init__(self, opts, *, raise_on_url=None):
        self.opts = opts
        self.raise_on_url = raise_on_url or set()
        self.downloaded = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def download(self, urls):
        for url in urls:
            if url in self.raise_on_url:
                raise Exception(f"Download failed for {url}")
            self.downloaded.append(url)
            # Fire progress hook with a finished status if hooks present
            for hook in self.opts.get("progress_hooks", []):
                hook({"status": "finished", "url": url})


def make_fake_ydl_factory(raise_on_url=None):
    """Returns a factory function that creates FakeYDL instances."""
    captured = []

    def factory(opts):
        ydl = FakeYDL(opts, raise_on_url=raise_on_url or set())
        captured.append(ydl)
        return ydl

    factory.instances = captured
    return factory


@pytest.fixture
def fake_ydl_factory():
    return make_fake_ydl_factory()
