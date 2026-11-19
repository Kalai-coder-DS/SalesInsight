-- =====================================================================
-- SalesInsight - Step 2: star schema tables (MySQL 8)
--
--   dim_customer ─┐
--   dim_product  ─┼── fact_sales
--   dim_location ─┘
--
-- Money columns use DECIMAL (exact), not FLOAT (approximate).
-- This file matches the table definitions in src/salesinsight/database.py;
-- a test checks that both have the same columns.
-- =====================================================================

USE salesinsight;

-- Drop in reverse order: the fact table points to the dimensions.
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_customer;

CREATE TABLE dim_customer (
    customer_id    VARCHAR(20)  NOT NULL,
    customer_name  VARCHAR(100) NOT NULL,
    segment        VARCHAR(20)  NOT NULL,
    PRIMARY KEY (customer_id)
) ENGINE = InnoDB;

CREATE TABLE dim_product (
    product_key    VARCHAR(10)  NOT NULL,   -- one key per (product_id, product_name)
    product_id     VARCHAR(20)  NOT NULL,
    product_name   VARCHAR(255) NOT NULL,
    category       VARCHAR(30)  NOT NULL,
    sub_category   VARCHAR(30)  NOT NULL,
    PRIMARY KEY (product_key),
    INDEX ix_product_category (category, sub_category)
) ENGINE = InnoDB;

CREATE TABLE dim_location (
    location_id    INT          NOT NULL,
    country        VARCHAR(50)  NOT NULL,
    region         VARCHAR(10)  NOT NULL,
    state          VARCHAR(50)  NOT NULL,
    city           VARCHAR(60)  NOT NULL,
    postal_code    VARCHAR(10),
    PRIMARY KEY (location_id),
    INDEX ix_location_region_state (region, state)
) ENGINE = InnoDB;

CREATE TABLE fact_sales (
    row_id            INT           NOT NULL,
    order_id          VARCHAR(20)   NOT NULL,
    order_date        DATE          NOT NULL,
    ship_date         DATE          NOT NULL,
    ship_mode         VARCHAR(20)   NOT NULL,
    ship_days         INT           NOT NULL,
    customer_id       VARCHAR(20)   NOT NULL,
    product_key       VARCHAR(10)   NOT NULL,
    location_id       INT           NOT NULL,
    order_year        INT           NOT NULL,
    order_quarter     INT           NOT NULL,
    order_month       INT           NOT NULL,
    order_month_name  VARCHAR(3)    NOT NULL,
    order_period      VARCHAR(7)    NOT NULL,   -- e.g. 2016-11 ("year_month" is reserved in MySQL)
    sales             DECIMAL(12,4) NOT NULL,
    quantity          INT           NOT NULL,
    discount          DECIMAL(5,4)  NOT NULL,
    discount_band     VARCHAR(20)   NOT NULL,
    profit            DECIMAL(12,4) NOT NULL,
    PRIMARY KEY (row_id),
    INDEX ix_fact_order_id (order_id),
    INDEX ix_fact_order_date (order_date),
    INDEX ix_fact_year_month (order_year, order_month),
    CONSTRAINT fk_fact_customer FOREIGN KEY (customer_id) REFERENCES dim_customer (customer_id),
    CONSTRAINT fk_fact_product  FOREIGN KEY (product_key) REFERENCES dim_product (product_key),
    CONSTRAINT fk_fact_location FOREIGN KEY (location_id) REFERENCES dim_location (location_id)
) ENGINE = InnoDB;
