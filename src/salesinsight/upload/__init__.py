"""Phase 14: use the app with your own sales file (CSV or Excel).

Flow:  read_upload()  ->  suggest_mapping()  ->  (user confirms)  ->  prepare_sales()
The result has the same columns as the cleaned Superstore data, so the
existing analysis code can run on it. Nothing here writes to disk.
"""

from salesinsight.upload.detect import suggest_mapping
from salesinsight.upload.prepare import PrepResult, prepare_sales
from salesinsight.upload.reader import UploadError, read_upload, excel_sheets
from salesinsight.upload.schema import FIELDS, REQUIRED, field_label

__all__ = ["FIELDS", "REQUIRED", "PrepResult", "UploadError", "excel_sheets", "field_label",
           "prepare_sales", "read_upload", "suggest_mapping"]
