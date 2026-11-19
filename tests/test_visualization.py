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


def test_phase7_charts(sales_data, tmp_path):
    from salesinsight import products as pr
    perf = pr.product_performance(sales_data)
    paths = [
        viz.plot_top_products(pr.top_products(perf, "revenue"), "revenue", folder=tmp_path),
        viz.plot_top_products(pr.top_products(perf, "profit"), "profit", folder=tmp_path),
        viz.plot_category_performance(pr.category_performance(sales_data), folder=tmp_path),
        viz.plot_subcategory_profit(pr.subcategory_performance(sales_data), folder=tmp_path),
        viz.plot_pareto(pr.pareto(perf), folder=tmp_path),
        viz.plot_discount_margin_heatmap(pr.discount_margin_matrix(sales_data), folder=tmp_path),
    ]
    assert all(p.exists() and p.stat().st_size > 10_000 for p in paths)


def test_phase8_charts(sales_data, tmp_path):
    from salesinsight import regions as rg
    states = rg.state_performance(sales_data)
    paths = [
        viz.plot_region_performance(rg.region_performance(sales_data), folder=tmp_path),
        viz.plot_top_states_revenue(rg.top_states(states), folder=tmp_path),
        viz.plot_state_profit_extremes(states, folder=tmp_path),
        viz.plot_region_category_heatmap(rg.region_category_matrix(sales_data), folder=tmp_path),
        viz.plot_state_discount_vs_margin(states, -0.5, min_orders=1, folder=tmp_path),
        viz.plot_region_revenue_by_year(rg.region_yearly(sales_data), folder=tmp_path),
    ]
    assert all(p.exists() and p.stat().st_size > 10_000 for p in paths)


def test_phase9_charts(sales_data, tmp_path):
    from salesinsight import customers as cu
    customers = cu.customer_table(sales_data)
    paths = [
        viz.plot_segment_performance(cu.segment_performance(sales_data), folder=tmp_path),
        viz.plot_order_frequency(cu.order_frequency(customers), folder=tmp_path),
        viz.plot_pareto(cu.customer_pareto(customers), folder=tmp_path, entity="customers", name="p"),
        viz.plot_rfm_segments(cu.rfm_summary(cu.rfm_table(customers)), folder=tmp_path),
        viz.plot_new_vs_returning(cu.new_vs_returning(sales_data), folder=tmp_path),
    ]
    assert all(p.exists() and p.stat().st_size > 10_000 for p in paths)
