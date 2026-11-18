# SalesInsight – Business Sales Analytics and Intelligence Platform

Analyses the Superstore retail sales dataset with Python, Pandas, NumPy, SQL (MySQL), statistics, Matplotlib and Seaborn to answer:

1. Total revenue and profit
2. Monthly and yearly sales trends
3. Best-selling products
4. Category-wise performance
5. Region-wise sales
6. Customer purchasing behaviour
7. Business insights and recommendations

> Status: Phase 1 (environment setup) complete. Full README in Phase 12.

## Quick start (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
copy .env.example .env      # then put your MySQL password in .env
python scripts/check_setup.py
pytest
```
