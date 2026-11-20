"""Download the raw Superstore file from Kaggle (used by the online web app).

The dataset is not stored in the public GitHub repo. When the app runs online
(Streamlit Community Cloud) and finds no local data, it downloads the file from
Kaggle with the owner's API key, which is kept in Streamlit "Secrets" - never in
the code or the repo.

Kaggle API: GET /api/v1/datasets/download/<owner>/<dataset> returns a zip file.
- Classic keys (from kaggle.json) use HTTP basic auth: username + key.
- Newer API tokens (starting with "KGAT_") use a Bearer header.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from salesinsight import config

KAGGLE_DATASET = "vivek468/superstore-dataset-final"
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/{dataset}"


class KaggleDownloadError(RuntimeError):
    """Raised with a message that tells the user what to fix."""


def auth_options(username: str, key: str) -> dict:
    """requests.get() keyword arguments for the two kinds of Kaggle credentials."""
    if key.startswith("KGAT_"):
        return {"headers": {"Authorization": f"Bearer {key}"}}
    return {"auth": (username, key)}


def extract_csv(content: bytes) -> bytes:
    """Return the CSV bytes from a Kaggle download (a zip, or occasionally the bare file)."""
    if zipfile.is_zipfile(io.BytesIO(content)):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            csvs = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
            if not csvs:
                raise KaggleDownloadError("The Kaggle download contains no CSV file.")
            biggest = max(csvs, key=lambda i: i.file_size)
            return zf.read(biggest)
    if content[:200].count(b",") >= 5:          # looks like a CSV header line
        return content
    raise KaggleDownloadError("The Kaggle download is neither a zip nor a CSV file.")


def download_raw(username: str, key: str, dest: Path = config.RAW_DATA_FILE,
                 dataset: str = KAGGLE_DATASET, session=None, timeout: int = 60) -> Path:
    """Download the dataset and save its CSV to `dest` (data/raw/Superstore.csv)."""
    if not username or not key:
        raise KaggleDownloadError("Kaggle credentials are missing (KAGGLE_USERNAME and KAGGLE_KEY).")
    if session is None:
        import requests
        session = requests.Session()
    try:
        response = session.get(DOWNLOAD_URL.format(dataset=dataset), timeout=timeout,
                               allow_redirects=True, **auth_options(username, key))
    except Exception as exc:  # noqa: BLE001 - network problems of any kind
        raise KaggleDownloadError(f"Could not reach Kaggle: {exc}") from exc

    status = getattr(response, "status_code", 200)
    if status in (401, 403):
        raise KaggleDownloadError(
            f"Kaggle refused the download (HTTP {status}). Check KAGGLE_USERNAME and KAGGLE_KEY "
            "in the app's Secrets.")
    if status == 404:
        raise KaggleDownloadError(f"Kaggle dataset not found: {dataset}")
    if status >= 400:
        raise KaggleDownloadError(f"Kaggle download failed (HTTP {status}).")

    data = extract_csv(response.content)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest
