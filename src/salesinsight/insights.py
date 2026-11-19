"""Phase 11 (Q7): business insights and recommendations, generated from the data.

Every number in the report is calculated here from the clean data, using the
same functions as Phases 5-10. Nothing is typed in by hand, so the report is
always correct for the data it was run on.

Recommendations come from simple, transparent rules. Each rule checks a
finding (e.g. "lines with over 40% discount lose money") and, if it is true,
writes a recommendation with the evidence and the money involved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from salesinsight import config
from salesinsight import customers as cu
from salesinsight import kpis as kp
from salesinsight import products as pr
from salesinsight import regions as rg
from salesinsight import stats_tests as st
from salesinsight import trends as tr
from salesinsight.kpis import format_value, short_money


@dataclass
class Recommendation:
    priority: int          # 1 = do first
    area: str
    title: str
    finding: str
    action: str
    impact: str


# ---------------------------------------------------------------------------
# 1. Collect every finding in one place
# ---------------------------------------------------------------------------
def collect_findings(df: pd.DataFrame) -> dict[str, object]:
    customers = cu.customer_table(df)
    high_disc = df[df["discount"] > 0.2]
    return {
        "kpis": kp.compute_kpis(df),
        "yearly": kp.yearly_kpis(df),
        "trends": tr.trend_summary(df),
        "products": pr.product_summary(df),
        "categories": pr.category_performance(df),
        "subcategories": pr.subcategory_performance(df),
        "discount_bands": pr.discount_band_performance(df),
        "regions": rg.region_performance(df),
        "region_summary": rg.region_summary(df),
        "segments": cu.segment_performance(df),
        "customers": cu.customer_summary(df),
        "rfm": cu.rfm_summary(cu.rfm_table(customers)) if len(customers) >= 5 else pd.DataFrame(),
        "tests": st.run_all_tests(df),
        "aov_ci": st.aov_confidence_by_year(df),
        "high_discount_loss": float(high_disc.loc[high_disc["profit"] < 0, "profit"].sum()),
        "high_discount_lines_pct": 100 * len(high_disc) / len(df),
    }


# ---------------------------------------------------------------------------
# 2. Rules that turn findings into recommendations
# ---------------------------------------------------------------------------
def _band(f: dict, band: str, col: str) -> float | None:
    bands = f["discount_bands"].assign(discount_band=lambda d: d["discount_band"].astype(str))
    row = bands[bands["discount_band"] == band]
    return float(row[col].iloc[0]) if len(row) else None


def rule_discount_cap(f: dict) -> Recommendation | None:
    over40 = _band(f, "Over 40%", "profit_margin_pct")
    band_21_40 = _band(f, "21-40%", "profit_margin_pct")
    if over40 is None or over40 >= 0:
        return None
    loss_lines = _band(f, "Over 40%", "loss_lines_pct")
    second = f" and {band_21_40:.1f}% at 21-40%" if band_21_40 is not None else ""
    return Recommendation(
        1, "Pricing", "Cap discounts at 20% and require approval above it",
        f"Order lines discounted over 40% have a {over40:.1f}% margin{second}; "
        f"{loss_lines:.0f}% of over-40% lines lose money. Lines discounted above 20% "
        f"({f['high_discount_lines_pct']:.1f}% of all lines) lost {short_money(-f['high_discount_loss'])} in total.",
        "Set a default discount ceiling of 20%. Discounts above it need manager approval "
        "and a written reason (clearing old stock, strategic account).",
        f"Up to {short_money(-f['high_discount_loss'])} of losses would be avoided if those "
        "lines were sold at 20% or less, or not sold at a loss.",
    )


def rule_loss_subcategories(f: dict) -> Recommendation | None:
    subs = f["subcategories"]
    losing = subs[subs["profit"] < 0].sort_values("profit")
    if losing.empty:
        return None
    names = ", ".join(f"{r.sub_category} ({short_money(r.profit)}, discount {r.effective_discount_pct:.0f}%)"
                      for r in losing.itertuples())
    return Recommendation(
        2, "Products", "Fix or reprice the loss-making sub-categories",
        f"{len(losing)} sub-categories lose money overall: {names}.",
        "Review list prices and supplier costs for these sub-categories, stop deep discounts on them, "
        "and drop individual products that lose money even without a discount.",
        f"Bringing these sub-categories to break-even adds {short_money(-losing['profit'].sum())} profit.",
    )


def rule_weak_category(f: dict) -> Recommendation | None:
    cats = f["categories"]
    overall = f["kpis"]["profit_margin_pct"]
    weak = cats[cats["profit_margin_pct"] < overall / 2]
    if weak.empty:
        return None
    w = weak.sort_values("profit_margin_pct").iloc[0]
    return Recommendation(
        2, "Products", f"Raise the {w['category']} margin",
        f"{w['category']} earns {short_money(w['revenue'])} revenue but only a {w['profit_margin_pct']:.1f}% "
        f"margin (company average {overall:.1f}%), with {w['loss_lines_pct']:.0f}% of its lines at a loss, "
        f"at a {w['effective_discount_pct']:.0f}% effective discount.",
        f"Use a lower discount limit for {w['category']} than for other categories and include "
        "shipping/handling costs in its prices.",
        f"Each extra percentage point of margin on {w['category']} adds about "
        f"{short_money(w['revenue'] / 100)} profit on the same sales.",
    )


def rule_loss_states(f: dict) -> Recommendation | None:
    s = f["region_summary"]
    if s["loss_making_states"] == 0:
        return None
    corr = s["state_discount_margin_correlation"]
    corr_text = (f" Across states, discount rate and margin are strongly linked (correlation {corr:.2f})."
                 if pd.notna(corr) and corr < -0.5 else "")
    return Recommendation(
        1, "Regions", "Change the discount policy in the loss-making states",
        f"{s['loss_making_states']} states lose money in total ({short_money(s['loss_making_states_total'])}): "
        f"{s['loss_making_states_list']}. The worst is {s['worst_state_by_profit']} "
        f"({short_money(s['worst_state_profit'])}).{corr_text}",
        "Apply the discount cap first in these states and review local promotions and sales-team incentives "
        "that reward revenue instead of profit.",
        f"Bringing these states to break-even adds {short_money(-s['loss_making_states_total'])} profit.",
    )


def rule_region_focus(f: dict) -> Recommendation | None:
    s = f["region_summary"]
    regions = f["regions"].set_index("region")
    worst = s["worst_margin_region"]
    worst_disc = regions.loc[worst, "effective_discount_pct"]
    disc_text = ("the highest discount rate" if worst_disc >= regions["effective_discount_pct"].max()
                 else "a discount rate")
    return Recommendation(
        3, "Regions", f"Grow {s['fastest_growing_region']} and repair {worst}",
        f"{s['top_region_by_revenue']} is the largest region ({s['top_region_revenue_share_pct']:.1f}% of revenue); "
        f"{s['fastest_growing_region']} grows fastest ({s['fastest_growing_region_cagr_pct']:.1f}% a year). "
        f"{worst} has the lowest margin ({s['worst_margin_region_pct']:.1f}%) and {disc_text} "
        f"({worst_disc:.1f}%).",
        f"Put growth budget into {s['fastest_growing_region']}; in {worst}, reduce discounting before adding volume.",
        f"Lifting {worst} to the company margin of {f['kpis']['profit_margin_pct']:.1f}% adds about "
        f"{short_money(regions.loc[worst, 'revenue'] * (f['kpis']['profit_margin_pct'] - s['worst_margin_region_pct']) / 100)} profit.",
    )


def rule_seasonality(f: dict) -> Recommendation | None:
    t = f["trends"]
    if t["peak_season_index"] < 120:
        return None
    return Recommendation(
        3, "Planning", "Plan stock, staff and marketing around the Q4 peak",
        f"{t['peak_season_month']} is the busiest month (index {t['peak_season_index']:.0f}, 100 = average) and "
        f"{t['low_season_month']} the quietest (index {t['low_season_index']:.0f}); Q4 brings "
        f"{t['q4_share_of_revenue_pct']:.1f}% of yearly revenue.",
        f"Build stock and staffing before {t['peak_season_month']}; use full-price campaigns in the peak and "
        f"small, margin-safe promotions in {t['low_season_month']} to smooth demand.",
        "Fewer stock-outs in the peak and better use of capacity in quiet months.",
    )


def rule_at_risk(f: dict) -> Recommendation | None:
    rfm = f["rfm"]
    if rfm.empty or "At risk" not in set(rfm["rfm_segment"]):
        return None
    row = rfm.set_index("rfm_segment").loc["At risk"]
    return Recommendation(
        2, "Customers", "Win back the 'At risk' customers",
        f"{int(row['total_customers'])} customers used to buy often but have not ordered for "
        f"{row['avg_recency_days']:.0f} days on average; they brought {row['share_of_revenue_pct']:.1f}% of revenue.",
        "Contact them personally (account managers for Corporate, email offers for Consumer) with "
        "a reason to return that does not rely on deep discounts.",
        f"Winning back a quarter of them protects about {short_money(row['revenue'] * 0.25)} of revenue.",
    )


def rule_acquisition(f: dict) -> Recommendation | None:
    c = f["customers"]
    if c["last_year_returning_revenue_share_pct"] < 85:
        return None
    return Recommendation(
        3, "Customers", "Invest in finding new customers",
        f"Returning customers made {c['last_year_returning_revenue_share_pct']:.1f}% of last year's revenue and "
        f"retention is {c['last_year_retention_pct']:.1f}%: the business keeps customers well but adds few new ones.",
        "Start a referral programme with Champions and test new channels; track new-customer revenue as a KPI.",
        "Reduces dependence on the existing customer base and creates the next group of loyal customers.",
    )


def rule_order_value(f: dict) -> Recommendation | None:
    ci = f["aov_ci"].sort_values("order_year")
    if len(ci) < 2:
        return None
    first, last = ci.iloc[0], ci.iloc[-1]
    if last["avg_order_value"] >= first["avg_order_value"]:
        return None
    overlap = last["ci_upper"] >= first["ci_lower"]
    certainty = ("the 95% confidence intervals overlap, so the fall is not statistically certain"
                 if overlap else "the 95% confidence intervals do not overlap, so the fall is real")
    return Recommendation(
        4, "Customers", "Raise average order value with bundles",
        f"Average order value went from ${first['avg_order_value']:,.0f} ({int(first['order_year'])}) to "
        f"${last['avg_order_value']:,.0f} ({int(last['order_year'])}); {certainty}.",
        "Offer bundles (e.g. chair + table, phone + accessories) and a free-shipping threshold above the "
        "current average order value. Keep monitoring the trend.",
        f"Each $10 on average order value is worth about {short_money(10 * f['kpis']['total_orders'] / len(ci))} "
        "a year at current order volume.",
    )


RULES = [rule_discount_cap, rule_loss_states, rule_loss_subcategories, rule_weak_category,
         rule_at_risk, rule_region_focus, rule_seasonality, rule_acquisition, rule_order_value]


def build_recommendations(f: dict) -> list[Recommendation]:
    recs = [r for rule in RULES if (r := rule(f)) is not None]
    return sorted(recs, key=lambda r: r.priority)


def recommendations_to_frame(recs: list[Recommendation]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in recs])


# ---------------------------------------------------------------------------
# 3. Write the Markdown report
# ---------------------------------------------------------------------------
def _md_table(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, sep, *rows])


def _figure(name: str, caption: str) -> str:
    """Markdown image link, only if the chart file exists."""
    if (config.FIGURES_DIR / f"{name}.png").exists():
        return f"\n![{caption}](figures/{name}.png)\n"
    return ""


def build_report(f: dict, recs: list[Recommendation]) -> str:
    k, t, p, s, c = f["kpis"], f["trends"], f["products"], f["region_summary"], f["customers"]
    y = f["yearly"]
    lines: list[str] = []
    add = lines.append

    add("# SalesInsight - Business Insights Report\n")
    add(f"Superstore sales, {k['first_order_date']:%d %b %Y} to {k['last_order_date']:%d %b %Y}. "
        f"{k['total_orders']:,} orders, {k['total_customers']:,} customers, {k['total_products']:,} products. "
        "All figures are generated from the cleaned data by `scripts/run_insights.py`.\n")

    add("## Executive summary\n")
    add(f"- **Revenue {format_value(k['total_revenue'], 'money')}, profit {format_value(k['total_profit'], 'money')} "
        f"({k['profit_margin_pct']:.1f}% margin).** Revenue grew {t['revenue_cagr_pct']:.1f}% a year "
        f"({t['first_year']}-{t['last_year']}).")
    add(f"- **Discounts are the main profit leak.** {format_value(k['discount_given'], 'money')} was given away "
        f"({k['effective_discount_pct']:.1f}% of list price); {k['loss_lines_pct']:.1f}% of order lines lose money, "
        f"{format_value(k['loss_amount'], 'money')} in total.")
    n_states = s["loss_making_states"]
    corr = s["state_discount_margin_correlation"]
    corr_text = (f", and the states that discount more earn less (correlation {corr:.2f})"
                 if pd.notna(corr) else "")
    add(f"- **{n_states} {'state loses' if n_states == 1 else 'states lose'} money** "
        f"({short_money(s['loss_making_states_total'])}){corr_text}.")
    add(f"- **Sales are seasonal:** {t['peak_season_month']} is the peak month and Q4 brings "
        f"{t['q4_share_of_revenue_pct']:.1f}% of revenue.")
    loyal = c["repeat_rate_pct"] >= 70
    newcomers = ("but few new customers arrive" if c["last_year_returning_revenue_share_pct"] >= 85
                 else "and new customers keep arriving")
    add(f"- **{'Customers are loyal' if loyal else 'Most customers buy only once'}** "
        f"({c['repeat_rate_pct']:.1f}% buy again), {newcomers}.\n")

    add("## Top recommendations\n")
    add(_md_table(pd.DataFrame([{"#": i + 1, "Area": r.area, "Recommendation": r.title, "Impact": r.impact}
                                for i, r in enumerate(recs)])))
    add("")

    add("## 1. Revenue and profit (Q1)\n")
    yt = y[["order_year", "revenue", "profit", "profit_margin_pct", "total_orders", "revenue_growth_pct"]].copy()
    yt["revenue"] = yt["revenue"].map(short_money)
    yt["profit"] = yt["profit"].map(short_money)
    yt["profit_margin_pct"] = yt["profit_margin_pct"].map(lambda v: f"{v:.1f}%")
    yt["revenue_growth_pct"] = yt["revenue_growth_pct"].map(lambda v: "-" if pd.isna(v) else f"{v:+.1f}%")
    yt.columns = ["Year", "Revenue", "Profit", "Margin", "Orders", "Revenue growth"]
    add(_md_table(yt))
    add(f"\nAverage order value is {format_value(k['avg_order_value'], 'money')}; "
        f"customers buy {k['avg_units_per_order']:.1f} units per order.")
    add(_figure("05_revenue_profit_by_year", "Revenue and profit by year"))

    add("## 2. Sales trends (Q2)\n")
    add(f"- Best month: **{t['best_month']}** ({short_money(t['best_month_revenue'])}); weakest: "
        f"{t['worst_month']} ({short_money(t['worst_month_revenue'])}).")
    add(f"- Seasonality: {t['peak_season_month']} index {t['peak_season_index']:.0f}, "
        f"{t['low_season_month']} index {t['low_season_index']:.0f} (100 = average month).")
    add(f"- Trend line: {t['monthly_trend_slope']:+,.0f} dollars per month; R-squared "
        f"{t['monthly_trend_r_squared']:.2f}, so seasonality explains much of the month-to-month movement.")
    add(f"- Busiest weekday for orders: {t['busiest_weekday']}.")
    add(_figure("06_revenue_heatmap", "Revenue by month and year"))

    add("## 3. Best-selling products (Q3)\n")
    add(f"- Top product by revenue: **{p['top_product_by_revenue']}** ({short_money(p['top_product_revenue'])}).")
    add(f"- Biggest loss-maker: **{p['worst_product_by_profit']}** ({short_money(p['worst_product_profit'])}).")
    add(f"- {p['products_for_80pct_revenue']:,} products ({p['products_for_80pct_revenue_pct']:.1f}%) make 80% of "
        f"revenue; the top 20% of products make {p['top20pct_products_revenue_share']:.1f}%.")
    add(f"- {p['loss_making_products']:,} products lose money overall ({short_money(p['loss_making_products_total'])}).")
    add(_figure("07_pareto_revenue", "Pareto curve of product revenue"))

    add("## 4. Category performance (Q4)\n")
    ct = f["categories"][["category", "revenue", "profit", "profit_margin_pct", "effective_discount_pct",
                          "loss_lines_pct"]].copy()
    ct["revenue"] = ct["revenue"].map(short_money)
    ct["profit"] = ct["profit"].map(short_money)
    for col in ("profit_margin_pct", "effective_discount_pct", "loss_lines_pct"):
        ct[col] = ct[col].map(lambda v: f"{v:.1f}%")
    ct.columns = ["Category", "Revenue", "Profit", "Margin", "Discount", "Lines at a loss"]
    add(_md_table(ct))
    add(f"\nBest sub-category: {p['best_subcategory_by_profit']} ({short_money(p['best_subcategory_profit'])}); "
        f"worst: {p['worst_subcategory_by_profit']} ({short_money(p['worst_subcategory_profit'])}). "
        f"Margin with no discount is {p['margin_no_discount_pct']:.1f}% versus "
        f"{p['margin_over_40pct_discount_pct']:.1f}% with over 40% off.")
    add(_figure("07_discount_margin_heatmap", "Margin by sub-category and discount level"))

    add("## 5. Region-wise sales (Q5)\n")
    rt = f["regions"][["region", "revenue", "profit", "profit_margin_pct", "effective_discount_pct"]].copy()
    rt["revenue"] = rt["revenue"].map(short_money)
    rt["profit"] = rt["profit"].map(short_money)
    for col in ("profit_margin_pct", "effective_discount_pct"):
        rt[col] = rt[col].map(lambda v: f"{v:.1f}%")
    rt.columns = ["Region", "Revenue", "Profit", "Margin", "Discount"]
    add(_md_table(rt))
    add(f"\nTop state: {s['top_state_by_revenue']} ({short_money(s['top_state_revenue'])} revenue). "
        f"Loss-making states: {s['loss_making_states_list'] or 'none'}.")
    add(_figure("08_state_discount_vs_margin", "Discount vs margin by state"))

    add("## 6. Customer behaviour (Q6)\n")
    gap = c["median_days_between_orders"]
    gap_text = f"median {gap:.0f} days between orders" if pd.notna(gap) else "no repeat orders to time yet"
    add(f"- {c['total_customers']:,} customers; {c['repeat_rate_pct']:.1f}% ordered more than once; "
        f"{c['avg_orders_per_customer']:.1f} orders each; {gap_text}.")
    add(f"- Top 10% of customers bring {c['top10pct_customers_revenue_share']:.1f}% of revenue; top 20% bring "
        f"{c['top20pct_customers_revenue_share']:.1f}%.")
    add(f"- {c['top_segment_by_revenue']} is the largest segment ({c['top_segment_revenue_share_pct']:.1f}% of revenue); "
        f"{c['best_margin_segment']} has the best margin.")
    add(f"- Last-year retention {c['last_year_retention_pct']:.1f}%; returning customers made "
        f"{c['last_year_returning_revenue_share_pct']:.1f}% of last year's revenue.")
    if not f["rfm"].empty:
        r = f["rfm"][["rfm_segment", "total_customers", "share_of_customers_pct", "share_of_revenue_pct"]].copy()
        for col in ("share_of_customers_pct", "share_of_revenue_pct"):
            r[col] = r[col].map(lambda v: f"{v:.1f}%")
        r.columns = ["RFM segment", "Customers", "Share of customers", "Share of revenue"]
        add("")
        add(_md_table(r))
    add(_figure("09_rfm_segments", "RFM customer segments"))

    add("## 7. Statistical evidence\n")
    add("Each pattern was tested to check it is not chance. The effect size shows whether it matters in practice.\n")
    tt = pd.DataFrame([{"Question": r.question, "Result": "Significant" if r.significant else "Not significant",
                        "Effect": f"{r.effect_label} ({r.effect_measure} {r.effect_size:.2f})",
                        "Conclusion": r.conclusion} for r in f["tests"]])
    add(_md_table(tt))
    add(_figure("10_loss_rate_by_discount", "Share of loss-making lines by discount level"))

    add("## 8. Recommendations (Q7)\n")
    for i, r in enumerate(recs, 1):
        add(f"### {i}. {r.title}  \n*Area: {r.area} - priority {r.priority}*\n")
        add(f"- **Finding:** {r.finding}")
        add(f"- **Action:** {r.action}")
        add(f"- **Expected impact:** {r.impact}\n")

    add("## 9. Limitations\n")
    add("- The Superstore dataset is a public sample (US only, 2014-2017); results describe this data, "
        "not a specific real company.")
    add("- The data has profit but no cost breakdown, so the reasons behind low margins (supplier cost, "
        "shipping, returns) cannot be separated.")
    add("- Correlation is not causation: discounts and losses move together, but a controlled price test "
        "would be needed to measure exactly how much profit a discount cap would recover.")
    add("- Impact figures are upper-bound estimates that assume sales volume stays the same.")
    return "\n".join(lines) + "\n"
