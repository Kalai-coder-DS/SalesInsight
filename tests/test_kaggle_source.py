"""Tests for the Kaggle download used by the online app (no internet needed: a fake session)."""

from __future__ import annotations

import io
import zipfile

import pytest

from salesinsight import kaggle_source as ks

CSV = b"Row ID,Order ID,Order Date,Ship Date,Ship Mode,Customer ID\n1,CA-1,11/8/2016,11/11/2016,Second Class,CG-1\n"


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content, self.status_code = content, status_code


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_download_saves_csv_from_zip(tmp_path):
    session = FakeSession(FakeResponse(make_zip({"readme.txt": b"hi", "Sample - Superstore.csv": CSV})))
    dest = ks.download_raw("kalai", "abc123", dest=tmp_path / "raw" / "Superstore.csv", session=session)
    assert dest.read_bytes() == CSV
    url, kwargs = session.calls[0]
    assert url.endswith("/datasets/download/vivek468/superstore-dataset-final")
    assert kwargs["auth"] == ("kalai", "abc123")


def test_new_style_token_uses_bearer_header():
    assert ks.auth_options("kalai", "KGAT_xyz") == {"headers": {"Authorization": "Bearer KGAT_xyz"}}


def test_plain_csv_download_is_accepted():
    assert ks.extract_csv(CSV) == CSV


@pytest.mark.parametrize("content", [make_zip({"notes.txt": b"no csv"}), b"<html>not data</html>"])
def test_bad_downloads_raise(content):
    with pytest.raises(ks.KaggleDownloadError):
        ks.extract_csv(content)


@pytest.mark.parametrize("status, text", [(401, "KAGGLE_KEY"), (403, "KAGGLE_KEY"), (404, "not found"),
                                          (500, "HTTP 500")])
def test_http_errors_have_clear_messages(tmp_path, status, text):
    session = FakeSession(FakeResponse(b"", status))
    with pytest.raises(ks.KaggleDownloadError, match=text):
        ks.download_raw("kalai", "abc", dest=tmp_path / "x.csv", session=session)
    assert not (tmp_path / "x.csv").exists()


def test_missing_credentials_and_network_errors(tmp_path):
    with pytest.raises(ks.KaggleDownloadError, match="missing"):
        ks.download_raw("", "", dest=tmp_path / "x.csv", session=FakeSession())
    with pytest.raises(ks.KaggleDownloadError, match="Could not reach"):
        ks.download_raw("kalai", "abc", dest=tmp_path / "x.csv", session=FakeSession(error=OSError("offline")))
