# app/agents/supplier_agent.py
# Formats and groups restock orders by supplier
# YOUR DATA: 66 suppliers with contact numbers in the DB

from typing import List, Dict, Any
from datetime import date
import logging

logger = logging.getLogger(__name__)


def group_orders_by_supplier(
    restock_orders: List[Dict]
) -> Dict[str, Dict]:
    """
    Groups restock orders by supplier.
    One supplier might supply products to multiple stores.
    YOUR DATA: 66 suppliers, lead times 5–12 days.
    """
    grouped = {}

    for order in restock_orders:
        sid = order.get("supplier_id", "UNKNOWN")
        if sid not in grouped:
            grouped[sid] = {
                "supplier_id":       sid,
                "supplier_name":     order.get("supplier_name", ""),
                "supplier_phone":    order.get("supplier_phone", ""),
                "orders":            [],
                "total_items":       0,
                "total_value":       0.0,
                "earliest_deadline": order.get("order_deadline", ""),
            }
        grouped[sid]["orders"].append(order)
        grouped[sid]["total_items"] += 1
        grouped[sid]["total_value"] += float(order.get("estimated_order_value", 0))

        # Track earliest deadline
        if order.get("order_deadline", "") < grouped[sid]["earliest_deadline"]:
            grouped[sid]["earliest_deadline"] = order["order_deadline"]

    # Round totals
    for sid in grouped:
        grouped[sid]["total_value"] = round(grouped[sid]["total_value"], 2)

    return grouped


def format_supplier_order_message(
    supplier_data: Dict,
) -> str:
    """
    Formats a supplier order as a WhatsApp/SMS-ready message.
    This exact text gets sent in Phase 6.
    """
    orders   = supplier_data["orders"]
    name     = supplier_data["supplier_name"]
    deadline = supplier_data["earliest_deadline"]
    total    = supplier_data["total_value"]

    lines = [
        f"🏪 KIRANA RETAIL — Purchase Order Request",
        f"📅 Date: {date.today().strftime('%d %b %Y')}",
        f"📦 Supplier: {name}",
        f"⏰ Please confirm by: {deadline}",
        f"",
        f"ORDER DETAILS:",
    ]

    for i, o in enumerate(orders[:10], 1):   # max 10 items per message
        lines.append(
            f"{i}. {o['product_name']} | Store: {o['store_id']} "
            f"| Qty: {int(o['restock_qty'])} units "
            f"| Urgency: {o.get('urgency', '')}"
        )

    if len(orders) > 10:
        lines.append(f"... and {len(orders) - 10} more items.")

    lines += [
        f"",
        f"💰 Estimated Order Value: ₹{total:,.0f}",
        f"",
        f"Please reply to confirm or call us.",
        f"— Kirana Retail Intelligence System",
    ]

    return "\n".join(lines)


async def prepare_supplier_orders(
    restock_orders: List[Dict],
    dry_run: bool = True,
) -> List[Dict]:
    """
    Full pipeline: group by supplier → format messages → ready to send.
    dry_run=True: returns formatted messages without sending.
    dry_run=False: Phase 6 will send via WhatsApp/email.
    """
    if not restock_orders:
        return [{"message": "No restock orders to process."}]

    grouped  = group_orders_by_supplier(restock_orders)
    prepared = []

    for sid, supplier_data in grouped.items():
        message = format_supplier_order_message(supplier_data)
        logger.info(
            f"Prepared order for {supplier_data['supplier_name']}: "
            f"{supplier_data['total_items']} items, ₹{supplier_data['total_value']:,.0f}"
        )

        prepared.append({
            "supplier_id":       sid,
            "supplier_name":     supplier_data["supplier_name"],
            "supplier_phone":    supplier_data["supplier_phone"],
            "total_items":       supplier_data["total_items"],
            "total_value":       supplier_data["total_value"],
            "earliest_deadline": supplier_data["earliest_deadline"],
            "order_message":     message,
            "sent":              not dry_run,
            "dry_run":           dry_run,
        })

    return sorted(prepared, key=lambda x: x["earliest_deadline"])
