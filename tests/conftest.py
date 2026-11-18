"""Shared test data: a tiny, hand-made Superstore-style dataset.

Tests never use the real 9,994-row file, so they are fast and work on
any computer, even before the dataset is downloaded.
"""

from __future__ import annotations

import pandas as pd
import pytest

RAW_ROWS = [
    # Row ID, Order ID, Order Date, Ship Date, Ship Mode, Customer ID, Customer Name, Segment,
    # Country, City, State, Postal Code, Region, Product ID, Category, Sub-Category,
    # Product Name, Sales, Quantity, Discount, Profit
    [1, "CA-2016-152156", "11/8/2016", "11/11/2016", "Second Class", "CG-12520", "Claire Gute", "Consumer",
     "United States", "Henderson", "Kentucky", "42420", "South", "FUR-BO-10001798", "Furniture", "Bookcases",
     "Bush Somerset Collection Bookcase", 261.96, 2, 0.0, 41.9136],
    [2, "CA-2016-152156", "11/8/2016", "11/11/2016", "Second Class", "CG-12520", "Claire Gute", "Consumer",
     "United States", "Henderson", "Kentucky", "42420", "South", "FUR-CH-10000454", "Furniture", "Chairs",
     "Hon Deluxe Fabric Upholstered Stacking Chairs", 731.94, 3, 0.0, 219.582],
    [3, "CA-2016-138688", "6/12/2016", "6/16/2016", "Second Class", "DV-13045", "Darrin Van Huff", "Corporate",
     "United States", "Los Angeles", "California", "90036", "West", "OFF-LA-10000240", "Office Supplies",
     "Labels", "Self-Adhesive Address Labels", 14.62, 2, 0.0, 6.8714],
    [4, "US-2015-108966", "10/11/2015", "10/18/2015", "Standard Class", "SO-20335", "Sean O'Donnell",
     "Consumer", "United States", "Fort Lauderdale", "Florida", "33311", "South", "FUR-TA-10000577",
     "Furniture", "Tables", "Bretford CR4500 Series Slim Rectangular Table", 957.5775, 5, 0.45, -383.031],
    [5, "US-2015-108966", "10/11/2015", "10/18/2015", "Standard Class", "SO-20335", "Sean O'Donnell",
     "Consumer", "United States", "Fort Lauderdale", "Florida", "33311", "South", "OFF-ST-10000760",
     "Office Supplies", "Storage", "Eldon Fold 'N Roll Cart System", 22.368, 2, 0.2, 2.5164],
    [6, "CA-2014-115812", "6/9/2014", "6/14/2014", "Standard Class", "BH-11710", "Brosina Hoffman", "Consumer",
     "United States", "Burlington", "Vermont", "05401", "East", "TEC-PH-10002275", "Technology", "Phones",
     "Mitel 5320 IP Phone VoIP phone", 907.152, 6, 0.2, 90.7152],
    [7, "CA-2017-114412", "4/15/2017", "4/20/2017", "Standard Class", "AA-10480", "Andrew Allen", "Home Office",
     "United States", "Concord", "North Carolina", "28027", "Central", "OFF-PA-10002365", "Office Supplies",
     "Paper", "Xerox 1967", 15.552, 3, 0.2, 5.4432],
    [8, "CA-2017-161389", "12/5/2017", "12/10/2017", "First Class", "IM-15070", "Irene Maddox", "Consumer",
     "United States", "Seattle", "Washington", "98103", "West", "TEC-AC-10003027", "Technology",
     "Accessories", "Imation 8GB Mini TravelDrive USB 2.0 Flash Drive", 90.57, 3, 0.0, 11.7741],
]

COLUMNS = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID", "Customer Name",
    "Segment", "Country", "City", "State", "Postal Code", "Region", "Product ID", "Category",
    "Sub-Category", "Product Name", "Sales", "Quantity", "Discount", "Profit",
]


@pytest.fixture
def raw_frame() -> pd.DataFrame:
    """The sample rows exactly as they look in the CSV (dates are text)."""
    return pd.DataFrame(RAW_ROWS, columns=COLUMNS)


@pytest.fixture
def raw_csv(tmp_path, raw_frame):
    """The sample rows written to a temporary latin-1 CSV file, like the real one."""
    df = raw_frame.copy()
    # A non-ASCII character, as in the real file (both rows of this customer).
    df.loc[df["Customer ID"] == "CG-12520", "Customer Name"] = "Claire Guté"
    path = tmp_path / "Superstore.csv"
    df.to_csv(path, index=False, encoding="latin-1")
    return path


@pytest.fixture
def clean_sample(raw_csv) -> pd.DataFrame:
    """The sample loaded through the real loader (valid data, all checks should pass)."""
    from salesinsight.data_loader import load_raw_data
    return load_raw_data(raw_csv)
