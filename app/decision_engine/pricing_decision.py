from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from datetime import date


EXPIRY_TIERS = [
    {"max_days": 7,  "min_discount": 40, "max_discount": 50, "label": "🔴 CRITICAL"},
    {"max_days": 15, "min_discount": 25, "max_discount": 35, "label": "🟠 HIGH"},
    {"max_days": 30, "min_discount": 20, "max_discount": 30, "label": "🟡 MEDIUM-HIGH"},
    {"max_days": 60, "min_discount": 10, "max_discount": 20, "label": "🟢 MEDIUM"},
    {"max_days": 90, "min_discount": 5,  "max_discount": 10, "label": "🔵 LOW"},
]


def suggest_expiry_discount(days_to_expiry: int) -> Dict[str, Any]:
    if days_to_expiry <= 0:
        return {
            "discount_pct": 50,
            "label":        "🔴 EXPIRED / CLEARANCE",
            "action":       "Pull from shelf immediately. Donate or discard.",
            "urgency":      "IMMEDIATE",
        }
    for tier in EXPIRY_TIERS:
        if days_to_expiry <= tier["max_days"]:
            mid = (tier["min_discount"] + tier["max_discount"]) // 2
            return {
                "discount_pct":   mid,
                "discount_range": f"{tier['min_discount']}–{tier['max_discount']}%",
                "label":          tier["label"],
                "days_to_expiry": days_to_expiry,
                "action":         f"Apply {mid}% discount immediately. Sell within {days_to_expiry} days.",
                "urgency": (
                    "IMMEDIATE" if days_to_expiry <= 7 else
                    "HIGH"      if days_to_expiry <= 15 else
                    "MEDIUM"
                ),
            }
    return {"discount_pct": 0, "label": "✅ FRESH", "action": "No discount needed.", "urgency": "NONE"}


def calculate_clearance_price(
    selling_price: float,
    cost_price:    float,
    discount_pct:  float,
) -> Dict[str, Any]:
    discounted_price = selling_price * (1 - discount_pct / 100)
    floor_price      = cost_price * 1.01
    final_price      = max(discounted_price, floor_price)
    actual_discount  = round((1 - final_price / selling_price) * 100, 2)
    margin_after     = round((final_price - cost_price) / final_price * 100, 2)
    return {
        "original_price":      round(selling_price, 2),
        "clearance_price":     round(final_price, 2),
        "cost_price":          round(cost_price, 2),
        "actual_discount_pct": actual_discount,
        "margin_after_pct":    margin_after,
        "floor_applied":       final_price > discounted_price,
    }


async def get_expiry_pricing_alerts(
    db: AsyncSession,
    days_window: int = 90
) -> List[Dict[str, Any]]:

    sql = text("""
        SELECT
            i.product_id,
            p.product_name,
            c.category_name,
            i.store_id,
            s.store_name,
            i.closing_stock,
            i.unit_cost,
            p.selling_price,
            p.cost_price,
            p.mrp,
            i.expiry_date,
            (i.expiry_date - CURRENT_DATE)::INTEGER        AS days_to_expiry,
            ROUND((i.closing_stock * i.unit_cost)::NUMERIC, 2) AS value_at_risk
        FROM inventory i
        JOIN product  p  ON i.product_id  = p.product_id
        JOIN category c  ON p.category_id = c.category_id
        JOIN store    s  ON i.store_id    = s.store_id
        WHERE i.expiry_date IS NOT NULL
          AND i.closing_stock > 0
          AND (i.expiry_date - CURRENT_DATE)::INTEGER BETWEEN 0 AND :days_window
        ORDER BY days_to_expiry ASC
    """)

    result = await db.execute(sql, {"days_window": days_window})
    rows   = result.mappings().all()

    output = []
    for row in rows:
        r    = dict(row)
        days = int(r["days_to_expiry"] or 0)
        disc  = suggest_expiry_discount(days)
        price = calculate_clearance_price(
            float(r["selling_price"] or 0),
            float(r["cost_price"]    or 0),
            disc["discount_pct"],
        )
        r.update({**disc, **price})
        output.append(r)

    return output


async def get_low_margin_products(db: AsyncSession) -> List[Dict]:

    sql = text("""
        SELECT
            p.product_id,
            p.product_name,
            c.category_name,
            p.cost_price,
            p.selling_price,
            p.mrp,
            sup.supplier_name,
            sup.supplier_id,
            ROUND(
                (p.selling_price - p.cost_price)
                / NULLIF(p.selling_price, 0) * 100
            , 2) AS margin_pct,
            CASE
                WHEN p.selling_price < p.cost_price
                THEN '🔴 SELLING BELOW COST'
                WHEN (p.selling_price - p.cost_price)
                     / NULLIF(p.selling_price, 0) * 100 < 5
                THEN '🟠 NEAR ZERO MARGIN'
                ELSE '🟡 LOW MARGIN'
            END AS margin_label
        FROM product p
        JOIN category c   ON p.category_id = c.category_id
        JOIN supplier sup ON p.supplier_id  = sup.supplier_id
        WHERE (
            (p.selling_price - p.cost_price)
            / NULLIF(p.selling_price, 0) * 100
        ) < 10
        ORDER BY margin_pct ASC
    """)

    result = await db.execute(sql)
    output = []
    for row in result.mappings().all():
        r      = dict(row)
        margin = float(r["margin_pct"] or 0)
        r["recommended_action"] = (
            "Raise price to at least cost + 5% OR renegotiate supplier cost"
            if margin < 0
            else "Review pricing — margin too thin for sustainable business"
        )
        output.append(r)
    return output