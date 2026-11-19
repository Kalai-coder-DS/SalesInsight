-- =====================================================================
-- SalesInsight - Step 3: business analysis queries
--
-- Each query starts with "-- name: <query_name>". Python reads this file,
-- runs every query and saves the result to reports/tables/sql/<name>.csv.
-- You can also run any single query in MySQL Workbench (select it, Ctrl+Enter).
--
-- Definitions (same as Phase 0):
--   revenue        = SUM(sales)            (sales is already after discount)
--   profit margin  = SUM(profit) / SUM(sales)
--   orders         = COUNT(DISTINCT order_id)
--   avg order value (AOV) = revenue / orders
-- =====================================================================

USE salesinsight;


-- ---------------------------------------------------------------------
-- Q1. Total revenue and profit
-- ---------------------------------------------------------------------
-- name: kpi_overview
SELECT
    ROUND(SUM(sales), 2)                                       AS total_revenue,
    ROUND(SUM(profit), 2)                                      AS total_profit,
    ROUND(100 * SUM(profit) / SUM(sales), 2)                   AS profit_margin_pct,
    COUNT(DISTINCT order_id)                                   AS total_orders,
    COUNT(DISTINCT customer_id)                                AS total_customers,
    SUM(quantity)                                              AS units_sold,
    ROUND(SUM(sales) / COUNT(DISTINCT order_id), 2)            AS avg_order_value,
    MIN(order_date)                                            AS first_order_date,
    MAX(order_date)                                            AS last_order_date
FROM fact_sales;


-- ---------------------------------------------------------------------
-- Q2. Sales trends
-- ---------------------------------------------------------------------
-- name: yearly_sales
WITH yearly AS (
    SELECT order_year,
           SUM(sales)               AS revenue,
           SUM(profit)              AS profit,
           COUNT(DISTINCT order_id) AS total_orders
    FROM fact_sales
    GROUP BY order_year
)
SELECT order_year,
       ROUND(revenue, 2)                        AS revenue,
       ROUND(profit, 2)                         AS profit,
       ROUND(100 * profit / revenue, 2)         AS profit_margin_pct,
       total_orders,
       ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY order_year))
                 / LAG(revenue) OVER (ORDER BY order_year), 2) AS revenue_growth_pct
FROM yearly
ORDER BY order_year;

-- name: quarterly_sales
SELECT order_year,
       order_quarter,
       ROUND(SUM(sales), 2)     AS revenue,
       ROUND(SUM(profit), 2)    AS profit,
       COUNT(DISTINCT order_id) AS total_orders
FROM fact_sales
GROUP BY order_year, order_quarter
ORDER BY order_year, order_quarter;

-- name: monthly_sales
SELECT order_period,
       ROUND(SUM(sales), 2)     AS revenue,
       ROUND(SUM(profit), 2)    AS profit,
       COUNT(DISTINCT order_id) AS total_orders
FROM fact_sales
GROUP BY order_period
ORDER BY order_period;

-- name: seasonality_by_month
-- Which calendar month sells most, adding all years together.
SELECT order_month,
       order_month_name,
       ROUND(SUM(sales), 2)     AS revenue,
       ROUND(SUM(profit), 2)    AS profit,
       COUNT(DISTINCT order_id) AS total_orders
FROM fact_sales
GROUP BY order_month, order_month_name
ORDER BY order_month;


-- ---------------------------------------------------------------------
-- Q3. Best-selling products
-- ---------------------------------------------------------------------
-- name: top10_products_by_revenue
SELECT p.product_name,
       p.category,
       p.sub_category,
       ROUND(SUM(f.sales), 2)  AS revenue,
       SUM(f.quantity)         AS units_sold,
       ROUND(SUM(f.profit), 2) AS profit
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.product_key, p.product_name, p.category, p.sub_category
ORDER BY revenue DESC, p.product_key
LIMIT 10;

-- name: top10_products_by_quantity
SELECT p.product_name,
       p.category,
       p.sub_category,
       SUM(f.quantity)         AS units_sold,
       ROUND(SUM(f.sales), 2)  AS revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.product_key, p.product_name, p.category, p.sub_category
ORDER BY units_sold DESC, revenue DESC, p.product_key
LIMIT 10;

-- name: top10_products_by_profit
SELECT p.product_name,
       p.category,
       p.sub_category,
       ROUND(SUM(f.profit), 2) AS profit,
       ROUND(SUM(f.sales), 2)  AS revenue
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.product_key, p.product_name, p.category, p.sub_category
ORDER BY profit DESC, p.product_key
LIMIT 10;

-- name: bottom10_products_by_profit
-- The products that lose the most money.
SELECT p.product_name,
       p.category,
       p.sub_category,
       ROUND(SUM(f.profit), 2)                      AS profit,
       ROUND(SUM(f.sales), 2)                       AS revenue,
       ROUND(AVG(f.discount) * 100, 1)              AS avg_discount_pct
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.product_key, p.product_name, p.category, p.sub_category
ORDER BY profit ASC, p.product_key
LIMIT 10;


-- ---------------------------------------------------------------------
-- Q4. Category performance
-- ---------------------------------------------------------------------
-- name: category_performance
SELECT p.category,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(100 * SUM(f.profit) / SUM(f.sales), 2)      AS profit_margin_pct,
       SUM(f.quantity)                                   AS units_sold,
       COUNT(DISTINCT f.order_id)                        AS total_orders
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.category
ORDER BY revenue DESC;

-- name: subcategory_performance
SELECT p.category,
       p.sub_category,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(100 * SUM(f.profit) / SUM(f.sales), 2)      AS profit_margin_pct,
       ROUND(AVG(f.discount) * 100, 1)                   AS avg_discount_pct
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
GROUP BY p.category, p.sub_category
ORDER BY profit DESC;


-- ---------------------------------------------------------------------
-- Q5. Region-wise sales
-- ---------------------------------------------------------------------
-- name: region_performance
SELECT l.region,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(100 * SUM(f.profit) / SUM(f.sales), 2)      AS profit_margin_pct,
       COUNT(DISTINCT f.order_id)                        AS total_orders,
       COUNT(DISTINCT f.customer_id)                     AS total_customers
FROM fact_sales f
JOIN dim_location l ON l.location_id = f.location_id
GROUP BY l.region
ORDER BY revenue DESC;

-- name: top10_states_by_revenue
SELECT l.state,
       l.region,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(100 * SUM(f.profit) / SUM(f.sales), 2)      AS profit_margin_pct
FROM fact_sales f
JOIN dim_location l ON l.location_id = f.location_id
GROUP BY l.state, l.region
ORDER BY revenue DESC, l.state
LIMIT 10;

-- name: bottom10_states_by_profit
SELECT l.state,
       l.region,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(AVG(f.discount) * 100, 1)                   AS avg_discount_pct
FROM fact_sales f
JOIN dim_location l ON l.location_id = f.location_id
GROUP BY l.state, l.region
ORDER BY profit ASC, l.state
LIMIT 10;

-- name: region_category_profit
SELECT l.region,
       p.category,
       ROUND(SUM(f.sales), 2)                            AS revenue,
       ROUND(SUM(f.profit), 2)                           AS profit,
       ROUND(100 * SUM(f.profit) / SUM(f.sales), 2)      AS profit_margin_pct
FROM fact_sales f
JOIN dim_location l ON l.location_id = f.location_id
JOIN dim_product  p ON p.product_key = f.product_key
GROUP BY l.region, p.category
ORDER BY l.region, p.category;


-- ---------------------------------------------------------------------
-- Q6. Customer purchasing behaviour
-- ---------------------------------------------------------------------
-- name: segment_performance
SELECT c.segment,
       COUNT(DISTINCT f.customer_id)                             AS total_customers,
       COUNT(DISTINCT f.order_id)                                AS total_orders,
       ROUND(SUM(f.sales), 2)                                    AS revenue,
       ROUND(SUM(f.profit), 2)                                   AS profit,
       ROUND(SUM(f.sales) / COUNT(DISTINCT f.order_id), 2)       AS avg_order_value,
       ROUND(1.0 * COUNT(DISTINCT f.order_id)
                 / COUNT(DISTINCT f.customer_id), 2)             AS orders_per_customer
FROM fact_sales f
JOIN dim_customer c ON c.customer_id = f.customer_id
GROUP BY c.segment
ORDER BY revenue DESC;

-- name: top10_customers_by_revenue
SELECT c.customer_id,
       c.customer_name,
       c.segment,
       COUNT(DISTINCT f.order_id) AS total_orders,
       ROUND(SUM(f.sales), 2)     AS revenue,
       ROUND(SUM(f.profit), 2)    AS profit
FROM fact_sales f
JOIN dim_customer c ON c.customer_id = f.customer_id
GROUP BY c.customer_id, c.customer_name, c.segment
ORDER BY revenue DESC, c.customer_id
LIMIT 10;

-- name: customer_order_frequency
-- How many customers ordered once, 2-3 times, 4-6 times, 7+ times.
WITH per_customer AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS n_orders
    FROM fact_sales
    GROUP BY customer_id
),
banded AS (
    SELECT CASE
               WHEN n_orders = 1 THEN 1
               WHEN n_orders <= 3 THEN 2
               WHEN n_orders <= 6 THEN 3
               ELSE 4
           END AS band_order,
           CASE
               WHEN n_orders = 1 THEN '1 order'
               WHEN n_orders <= 3 THEN '2-3 orders'
               WHEN n_orders <= 6 THEN '4-6 orders'
               ELSE '7+ orders'
           END AS order_band
    FROM per_customer
)
SELECT order_band,
       COUNT(*) AS total_customers
FROM banded
GROUP BY band_order, order_band
ORDER BY band_order;

-- name: repeat_customer_rate
WITH per_customer AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS n_orders
    FROM fact_sales
    GROUP BY customer_id
)
SELECT COUNT(*)                                                   AS total_customers,
       SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END)             AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END)
                   / COUNT(*), 2)                                 AS repeat_rate_pct,
       ROUND(AVG(n_orders), 2)                                    AS avg_orders_per_customer
FROM per_customer;


-- ---------------------------------------------------------------------
-- Supporting analysis for insights (Q7)
-- ---------------------------------------------------------------------
-- name: discount_impact
-- Does a bigger discount lead to lower profit?
SELECT discount_band,
       COUNT(*)                                          AS order_lines,
       ROUND(SUM(sales), 2)                              AS revenue,
       ROUND(SUM(profit), 2)                             AS profit,
       ROUND(100 * SUM(profit) / SUM(sales), 2)          AS profit_margin_pct,
       ROUND(100.0 * SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS loss_lines_pct
FROM fact_sales
GROUP BY discount_band
ORDER BY MIN(discount);

-- name: ship_mode_performance
SELECT ship_mode,
       COUNT(DISTINCT order_id)                          AS total_orders,
       ROUND(AVG(ship_days), 2)                          AS avg_ship_days,
       ROUND(SUM(sales), 2)                              AS revenue,
       ROUND(SUM(profit), 2)                             AS profit
FROM fact_sales
GROUP BY ship_mode
ORDER BY avg_ship_days;
