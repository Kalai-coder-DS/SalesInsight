"""Phase 5 tests: every chart function creates a non-empty PNG file."""

from __future__ import annotations

from salesinsight import visualization as viz
from salesinsight.kpis import compute_kpis, yearly_kpis


def test_palette_fixed_order():
    assert viz.REVENUE_COLOR == viz.SERIES[0]
    assert viz.PROFIT_COLOR == viz.SERIES[1]
    assert len(set(viz.SERIES)) == len(viz.SERIES)


def test_kpi_tiles_png(sales_data, tmp_path):
    path = viz.plot_kpi_tiles(compute_kpis(sales_data), folder=tmp_path)
    assert path.exists() and path.stat().st_size > 10_000


def test_revenue_profit_png(sales_data, tmp_path):
    path = viz.plot_revenue_profit_by_year(yearly_kpis(sales_data), folder=tmp_path)
    assert path.exists() and path.stat().st_size > 10_000


def test_margin_png(sales_data, tmp_path):
    kpis = compute_kpis(sales_data)
    path = viz.plot_margin_by_year(yearly_kpis(sales_data), kpis["profit_margin_pct"], folder=tmp_path)
    assert path.exists() and path.stat().st_size > 10_000


def test_axis_money_labels():
    assert [viz.axis_money(v) for v in (0, 200_000, 1_500_000, -50_000)] == ["$0", "$200K", "$1.5M", "-$50K"]


def test_phase6_charts(sales_data, tmp_path):
    from salesinsight import trends as t
    monthly = t.monthly_sales(sales_data)
    paths = [
        viz.plot_monthly_trend(monthly, folder=tmp_path),
        viz.plot_revenue_heatmap(t.revenue_matrix(monthly), folder=tmp_path),
        viz.plot_seasonality_index(t.seasonality(monthly), folder=tmp_path),
        viz.plot_weekday_orders(t.weekday_sales(sales_data), folder=tmp_path),
    ]
    assert all(p.exists() and p.stat().st_size > 10_000 for p in paths)
