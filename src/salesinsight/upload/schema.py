"""The standard sales fields an uploaded file can be mapped to.

Every business names its columns differently ("Invoice Date", "Bill_Dt",
"Order Date"...). Each standard field lists common names; detection compares
them after normalising (lower case, letters and digits only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Field:
    key: str                 # standard column name used by the app
    label: str               # friendly name shown to the user
    kind: str                # "date", "money", "number", "percent", "text", "id"
    level: str               # "required", "recommended", "optional"
    help: str
    synonyms: tuple[str, ...] = field(default_factory=tuple)


FIELDS: list[Field] = [
    # --- Required ---------------------------------------------------------------
    Field("order_date", "Order date", "date", "required", "When the sale happened",
          ("order date", "orderdate", "date", "invoice date", "bill date", "billdt", "transaction date",
           "sale date", "sales date", "purchase date", "txn date", "order dt", "created at", "order created",
           "posting date", "document date", "day")),
    Field("sales", "Sales amount", "money", "required", "Money received for the line or order",
          ("sales", "sale", "amount", "sales amount", "revenue", "net sales", "total", "total amount",
           "line total", "net amount", "invoice amount", "value", "sales value", "turnover", "gross amount",
           "total price", "price total", "order value", "amount inr", "amount usd", "net revenue")),
    # --- Recommended -------------------------------------------------------------
    Field("order_id", "Order / invoice ID", "id", "recommended", "Groups lines into orders",
          ("order id", "orderid", "order no", "order number", "invoice", "invoice no", "invoice number",
           "invoice id", "bill no", "bill number", "receipt no", "transaction id", "txn id", "order ref",
           "sales order", "so number", "document no")),
    Field("product_name", "Product", "text", "recommended", "What was sold",
          ("product name", "product", "item", "item name", "item description", "description", "product title",
           "sku name", "article", "menu item", "goods", "product description")),
    Field("customer_name", "Customer", "text", "recommended", "Who bought it",
          ("customer name", "customer", "client", "client name", "buyer", "buyer name", "party name",
           "account name", "customer full name", "company")),
    # --- Optional ----------------------------------------------------------------
    Field("customer_id", "Customer ID", "id", "optional", "Unique customer code",
          ("customer id", "customerid", "cust id", "client id", "customer code", "account id", "buyer id",
           "member id", "customer no", "email", "customer email", "buyer email", "client email",
           "phone", "customer phone", "mobile")),
    Field("product_id", "Product ID / SKU", "id", "optional", "Unique product code",
          ("product id", "productid", "sku", "item code", "product code", "item id", "article no", "barcode")),
    Field("quantity", "Quantity", "number", "optional", "Units sold",
          ("quantity", "qty", "units", "unit sold", "units sold", "no of items", "pcs", "volume")),
    Field("unit_price", "Unit price", "money", "optional",
          "Price of one unit - used to calculate sales (price x quantity) when there is no sales column",
          ("unit price", "price", "rate", "selling price", "price per unit", "unit rate", "mrp", "sp")),
    Field("profit", "Profit", "money", "optional", "Sales minus costs",
          ("profit", "net profit", "gross profit", "margin amount", "earnings", "profit amount", "gp")),
    Field("cost", "Cost", "money", "optional", "What the goods cost you (profit = sales - cost)",
          ("cost", "total cost", "cogs", "cost of goods", "cost price", "purchase cost", "landed cost",
           "cost amount")),
    Field("discount", "Discount", "percent", "optional", "Discount rate (e.g. 0.2 or 20%)",
          ("discount", "discount rate", "discount pct", "discount percent", "disc", "disc pct", "markdown")),
    Field("category", "Category", "text", "optional", "Product group",
          ("category", "product category", "item category", "department", "dept", "group", "product group",
           "product line", "class")),
    Field("sub_category", "Sub-category", "text", "optional", "Smaller product group",
          ("sub category", "subcategory", "sub cat", "product subcategory", "subgroup", "sub group", "type",
           "product type", "item type")),
    Field("region", "Region", "text", "optional", "Sales region or zone",
          ("region", "zone", "area", "territory", "sales region", "market")),
    Field("state", "State / province", "text", "optional", "State, province or county",
          ("state", "province", "state name", "county", "state province")),
    Field("city", "City", "text", "optional", "City or town",
          ("city", "town", "city name", "location", "store location")),
    Field("country", "Country", "text", "optional", "Country",
          ("country", "country name", "nation")),
    Field("segment", "Customer segment", "text", "optional", "Customer type (e.g. Retail, Wholesale)",
          ("segment", "customer segment", "customer type", "channel", "sales channel", "customer group",
           "customer category")),
    Field("ship_date", "Ship / delivery date", "date", "optional", "When the order was shipped",
          ("ship date", "shipdate", "shipping date", "dispatch date", "delivery date", "shipped date",
           "delivered on")),
    Field("ship_mode", "Ship mode", "text", "optional", "Delivery method",
          ("ship mode", "shipping mode", "delivery mode", "shipping method", "delivery method", "courier")),
]

BY_KEY: dict[str, Field] = {f.key: f for f in FIELDS}
REQUIRED: list[str] = [f.key for f in FIELDS if f.level == "required"]
# Sales can also be calculated as unit_price x quantity when there is no sales column.
SALES_ALTERNATIVE: tuple[str, str] = ("unit_price", "quantity")
RECOMMENDED: list[str] = [f.key for f in FIELDS if f.level == "recommended"]


def normalise(name: object) -> str:
    """'Invoice_Date (dd/mm)' -> 'invoicedateddmm'. Used to compare column names."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def field_label(key: str) -> str:
    return BY_KEY[key].label
