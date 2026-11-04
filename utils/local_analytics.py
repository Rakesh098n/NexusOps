"""Deterministic analytics for the seeded demo database."""

import re
import sqlite3
from math import ceil

import pandas as pd

from utils.tools import DB_URI


def _query_frame(query: str, parameters: tuple = ()) -> pd.DataFrame:
    connection = sqlite3.connect(DB_URI, uri=True)
    try:
        return pd.read_sql_query(query, connection, params=parameters)
    finally:
        connection.close()


def get_inventory_snapshot(include_demand: bool = False) -> pd.DataFrame:
    """Return inventory quantities and coverage from the read-only sample DB."""
    demand_column = "i.avg_daily_demand, " if include_demand else ""
    return _query_frame(
        "SELECT p.name AS product, i.units_in_stock, i.units_on_order, "
        "i.reorder_threshold, "
        f"{demand_column}i.as_of_date AS snapshot_date, "
        "ROUND(i.units_in_stock / i.avg_daily_demand, 1) "
        "AS days_of_cover FROM inventory i JOIN products p "
        "ON p.product_id = i.product_id ORDER BY days_of_cover"
    )


def build_inventory_scenario(
    inventory: pd.DataFrame, lead_time_days: int, safety_stock_days: int
) -> dict:
    """Estimate replenishment needs for a lead-time and safety-stock scenario."""
    coverage_days = lead_time_days + safety_stock_days
    rows = []
    for row in inventory.itertuples(index=False):
        target_stock = ceil(float(row.avg_daily_demand) * coverage_days)
        available_stock = int(row.units_in_stock) + int(row.units_on_order)
        order_quantity = max(target_stock - available_stock, 0)
        rows.append(
            {
                "product": row.product,
                "on_hand": int(row.units_in_stock),
                "on_order": int(row.units_on_order),
                "avg_daily_demand": float(row.avg_daily_demand),
                "target_stock": target_stock,
                "suggested_order_quantity": order_quantity,
                "decision": "REORDER" if order_quantity else "COVERED",
            }
        )
    return {
        "snapshot_date": str(inventory["snapshot_date"].max()),
        "lead_time_days": lead_time_days,
        "safety_stock_days": safety_stock_days,
        "rows": rows,
    }


def build_inventory_recommendation(inventory: pd.DataFrame) -> dict[str, str | int]:
    """Create a cautious, evidence-based inventory decision from a snapshot."""
    below_threshold = inventory[
        inventory["units_in_stock"] < inventory["reorder_threshold"]
    ]
    without_incoming_stock = below_threshold[below_threshold["units_on_order"] <= 0]
    with_incoming_stock = below_threshold[below_threshold["units_on_order"] > 0]
    low_coverage = inventory[inventory["days_of_cover"] <= 30]
    at_risk = inventory[
        (inventory["units_in_stock"] < inventory["reorder_threshold"])
        | (inventory["days_of_cover"] <= 30)
    ]
    snapshot_date = str(inventory["snapshot_date"].max())

    if not without_incoming_stock.empty:
        decision = "REORDER"
        urgency = "MEDIUM"
        products = ", ".join(without_incoming_stock["product"].tolist())
        top_action = (
            "Verify live stock and open purchase orders, then raise purchase "
            f"orders for {products} if they remain below threshold."
        )
        evidence_rows = without_incoming_stock
    elif not with_incoming_stock.empty:
        decision = "INVESTIGATE"
        urgency = "MEDIUM"
        products = ", ".join(with_incoming_stock["product"].tolist())
        top_action = (
            "Check the quantities and arrival dates of open purchase orders for "
            f"{products} before placing additional orders."
        )
        evidence_rows = with_incoming_stock
    elif not low_coverage.empty:
        decision = "MONITOR"
        urgency = "LOW"
        products = ", ".join(low_coverage["product"].tolist())
        top_action = (
            "Review current demand and incoming stock for "
            f"{products}; reorder only if live stock requires it."
        )
        evidence_rows = low_coverage
    else:
        decision = "MONITOR"
        urgency = "LOW"
        products = ""
        top_action = "Continue monitoring live stock and demand."
        evidence_rows = inventory.iloc[0:0]

    evidence = "; ".join(
        f"{row.product}: {row.units_in_stock} on hand vs "
        f"{row.reorder_threshold} reorder threshold, "
        f"{row.units_on_order} on order, {row.days_of_cover:.1f} days of cover"
        for row in evidence_rows.itertuples(index=False)
    )
    answer = (
        f"**{decision} · {urgency.lower()} urgency.** "
        f"The snapshot flags {len(at_risk)} of {len(inventory)} products by "
        "reorder threshold or 30-day coverage. "
        f"The {snapshot_date} sample snapshot shows {evidence}."
        if evidence
        else f"**{decision} · {urgency.lower()} urgency.** "
        f"The {snapshot_date} sample snapshot has no products below threshold "
        f"or at 30 days or less of coverage."
    )
    recommendation = (
        f"{answer} {top_action} This historical snapshot does not include "
        "current demand or supplier lead times."
    )
    return {
        "decision": decision,
        "urgency": urgency,
        "confidence": 85,
        "top_action": top_action,
        "snapshot_date": snapshot_date,
        "recommendation": recommendation,
    }


def get_dashboard_data() -> dict:
    """Return compact KPIs and trend tables for the dashboard."""
    totals = _query_frame(
        "SELECT COUNT(*) AS transactions, SUM(revenue) AS revenue, "
        "COUNT(DISTINCT customer_id) AS customers, MAX(sale_date) AS latest_sale "
        "FROM sales"
    ).iloc[0].to_dict()
    monthly = _query_frame(
        "SELECT substr(sale_date, 1, 7) AS month, ROUND(SUM(revenue), 2) AS revenue "
        "FROM sales GROUP BY month ORDER BY month"
    )
    inventory = get_inventory_snapshot()
    return {"totals": totals, "monthly": monthly, "inventory": inventory}


def get_data_table(dataset: str) -> pd.DataFrame:
    """Load one allow-listed table for the data explorer."""
    queries = {
        "Sales": (
            "SELECT sale_id, sale_date, product_id, customer_id, quantity, revenue "
            "FROM sales ORDER BY sale_date DESC LIMIT 500"
        ),
        "Products": "SELECT * FROM products ORDER BY product_id",
        "Customers": "SELECT * FROM customers ORDER BY customer_id LIMIT 500",
        "Inventory": "SELECT * FROM inventory ORDER BY product_id",
    }
    if dataset not in queries:
        raise ValueError("Unknown dataset selected.")
    return _query_frame(queries[dataset])


def run_local_analysis(question: str) -> dict:
    """Answer common business questions without an external model or SQL generation."""
    normalized = question.casefold()
    inventory_question = any(
        term in normalized for term in ("stock", "inventory", "reorder", "supply")
    )
    products = _query_frame("SELECT product_id, name, category FROM products")
    matched_product = next(
        (
            (int(row.product_id), row.name)
            for row in products.itertuples(index=False)
            if row.name.casefold() in normalized
        ),
        None,
    )
    matched_category = next(
        (
            row.category
            for row in products.itertuples(index=False)
            if row.category.casefold() in normalized
        ),
        None,
    )
    if inventory_question:
        matched_product = None

    if matched_product:
        product_id, product_name = matched_product
        findings = _query_frame(
            "SELECT substr(s.sale_date, 1, 7) AS month, "
            "ROUND(SUM(s.revenue), 2) AS revenue, COUNT(*) AS transactions "
            "FROM sales s WHERE s.product_id = ? GROUP BY month ORDER BY month",
            (product_id,),
        )
        focus = f"Monthly sales for {product_name}"
        march = findings[findings["month"].str.endswith("-03")]
        february = findings[findings["month"].str.endswith("-02")]
        if not march.empty and not february.empty:
            change = march.iloc[0]["revenue"] - february.iloc[0]["revenue"]
            percentage = change / february.iloc[0]["revenue"] * 100
            interpretation = (
                f"March recorded USD {march.iloc[0]['revenue']:,.2f} in revenue, "
                f"{abs(percentage):.1f}% {'below' if change < 0 else 'above'} "
                f"February's USD {february.iloc[0]['revenue']:,.2f}. The database "
                "does not contain information that establishes the cause."
            )
        else:
            interpretation = (
                f"The sample contains {len(findings)} monthly observations for "
                f"{product_name}; compare the monthly values with targets and "
                "complete periods before inferring a trend."
            )
        recommendation = (
            "Check the transaction mix, discounts, pipeline, and whether the periods "
            "are complete. This seeded sales history cannot establish a cause or "
            "support a live forecast on its own."
        )
    elif not inventory_question and any(
        term in normalized for term in ("category", "analytics", "product")
    ):
        marketing_question = any(
            term in normalized for term in ("marketing", "campaign", "budget")
        )
        is_q4 = "q4" in normalized or "fourth quarter" in normalized
        date_filter = (
            "AND s.sale_date >= ? AND s.sale_date < ?" if is_q4 else ""
        )
        date_parameters = ("2025-10-01", "2026-01-01") if is_q4 else ()
        period = " for Q4 2025" if is_q4 else ""
        if matched_category:
            findings = _query_frame(
                "SELECT p.name AS product, ROUND(SUM(s.revenue), 2) AS revenue, "
                "COUNT(*) AS transactions FROM sales s "
                "JOIN products p ON p.product_id = s.product_id "
                f"WHERE p.category = ? {date_filter} "
                "GROUP BY p.product_id ORDER BY revenue DESC",
                (matched_category, *date_parameters),
            )
            focus = f"Revenue from {matched_category} products{period}"
            interpretation = (
                f"{findings.iloc[0]['product']} leads at "
                f"USD {findings.iloc[0]['revenue']:,.2f}; "
                f"{findings.iloc[-1]['product']} is lowest at "
                f"USD {findings.iloc[-1]['revenue']:,.2f}."
            )
        elif any(term in normalized for term in ("category", "categories")):
            findings = _query_frame(
                "SELECT p.category, ROUND(SUM(s.revenue), 2) AS revenue, "
                "COUNT(*) AS transactions, "
                "COUNT(DISTINCT p.product_id) AS products "
                "FROM sales s JOIN products p ON p.product_id = s.product_id "
                f"WHERE 1 = 1 {date_filter} "
                "GROUP BY p.category ORDER BY revenue DESC",
                date_parameters,
            )
            focus = f"Revenue by product category{period}"
            interpretation = (
                f"{findings.iloc[0]['category']} leads at "
                f"USD {findings.iloc[0]['revenue']:,.2f}; "
                f"{findings.iloc[-1]['category']} is lowest at "
                f"USD {findings.iloc[-1]['revenue']:,.2f}."
            )
        else:
            findings = _query_frame(
                "SELECT p.name AS product, p.category, "
                "ROUND(SUM(s.revenue), 2) AS revenue, COUNT(*) AS transactions "
                "FROM sales s JOIN products p ON p.product_id = s.product_id "
                f"WHERE 1 = 1 {date_filter} "
                "GROUP BY p.product_id ORDER BY revenue DESC",
                date_parameters,
            )
            focus = f"Revenue by product{period}"
            interpretation = (
                f"{findings.iloc[0]['product']} leads at "
                f"USD {findings.iloc[0]['revenue']:,.2f}; "
                f"{findings.iloc[-1]['product']} is lowest at "
                f"USD {findings.iloc[-1]['revenue']:,.2f}."
            )
        if marketing_question:
            recommendation = (
                "Compare category growth, contribution margin, and campaign-attributed "
                "conversions before reallocating marketing budget. Revenue alone does "
                "not establish marketing return."
            )
        elif matched_category or "category" in normalized or "categories" in normalized:
            recommendation = (
                "Compare category revenue with transaction volume, product mix, and "
                "targets. Review contribution margin before changing investment."
            )
        else:
            recommendation = (
                "Compare product revenue with units sold, contribution margin, "
                "discount levels, and targets before changing product investment."
            )
    elif inventory_question:
        findings = get_inventory_snapshot()
        focus = "Inventory and stock coverage"
        inventory_decision = build_inventory_recommendation(findings)
        interpretation = ""
        recommendation = inventory_decision["recommendation"]
    elif any(term in normalized for term in ("customer", "client", "account")):
        top_match = re.search(r"\btop\s+(\d+)\b", normalized)
        limit = min(max(int(top_match.group(1)), 1), 100) if top_match else 10
        findings = _query_frame(
            "SELECT c.name AS customer, c.segment, c.region, "
            "ROUND(SUM(s.revenue), 2) AS revenue, SUM(s.quantity) AS units "
            "FROM sales s JOIN customers c ON c.customer_id = s.customer_id "
            "GROUP BY c.customer_id ORDER BY revenue DESC LIMIT ?",
            (limit,),
        )
        focus = f"Top {limit} customers by recorded revenue"
        ranking = "\n".join(
            f"{rank}. {row.customer} — USD {row.revenue:,.2f}"
            for rank, row in enumerate(findings.itertuples(index=False), start=1)
        )
        interpretation = (
            f"Top {limit} customers by recorded revenue in the seeded 2025 sample:\n"
            f"{ranking}\n\nThis is historical sample data, not a live account ledger."
        )
        recommendation = ""
    elif any(term in normalized for term in ("region", "territory", "geography")):
        findings = _query_frame(
            "SELECT c.region, ROUND(SUM(s.revenue), 2) AS revenue, "
            "COUNT(*) AS transactions, COUNT(DISTINCT c.customer_id) AS customers "
            "FROM sales s JOIN customers c ON c.customer_id = s.customer_id "
            "GROUP BY c.region ORDER BY revenue DESC"
        )
        focus = "Recorded revenue by region"
        lowest = findings.iloc[-1]
        interpretation = (
            f"{lowest['region']} recorded the lowest sales revenue in the sample: "
            f"USD {lowest['revenue']:,.2f} across {int(lowest['transactions'])} "
            f"transactions. This historical revenue comparison does not account "
            "for regional targets or pipeline."
        )
        recommendation = ""
    else:
        findings = _query_frame(
            "SELECT substr(sale_date, 1, 7) AS month, "
            "ROUND(SUM(revenue), 2) AS revenue, COUNT(*) AS transactions "
            "FROM sales GROUP BY month ORDER BY month"
        )
        focus = "Monthly revenue trend"
        highest = findings.loc[findings["revenue"].idxmax()]
        lowest = findings.loc[findings["revenue"].idxmin()]
        interpretation = (
            f"Recorded monthly revenue ranges from USD {lowest['revenue']:,.2f} "
            f"in {lowest['month']} to USD {highest['revenue']:,.2f} "
            f"in {highest['month']}. "
            "The dataset contains seeded 2025 transactions."
        )
        recommendation = (
            "Validate the trend against your current source system and compare "
            "like-for-like periods before making a forecast or budget decision."
        )

    table = findings.to_markdown(index=False, floatfmt=",.2f")
    critic_review = (
        "**Confidence: 85% (moderate).** The recorded quantities are exact for "
        "the historical sample snapshot, but it does not include current demand, "
        "supplier lead times, or verified purchase-order status."
        if inventory_question
        else (
            "**Confidence: 85% (moderate).** The result is based on the synthetic "
            "historical sample and lacks external context or validated operational "
            "targets. Confirm the source, period, and definitions before acting."
        )
    )
    return {
        "mode": "Local demo analytics",
        "focus": focus,
        "analyst_findings": f"### {focus}\n\n{table}",
        "research_insights": (
            "This result is computed directly from the included sample database. "
            "It describes recorded values only; it does not establish business causes."
        ),
        "critic_review": critic_review,
        "final_recommendation": "\n\n".join(
            part for part in (interpretation, recommendation) if part
        ),
        "error": None,
    }