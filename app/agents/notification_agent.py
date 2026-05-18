# app/agents/notification_agent.py
# Routes alerts to correct channel based on priority
# Phase 6 will plug in real WhatsApp/Telegram/email here

from typing import List, Dict, Any
from datetime import date
import logging

logger = logging.getLogger(__name__)


# ── Alert priority definitions ─────────────────────────
ALERT_CHANNELS = {
    "CRITICAL": ["whatsapp", "telegram"],   # Phase 6 plugs in here
    "HIGH":     ["telegram", "email"],
    "MEDIUM":   ["email"],
    "LOW":      ["dashboard"],              # Just shown on dashboard
}


class Alert:
    """Represents a single alert to be dispatched."""
    def __init__(
        self,
        alert_type: str,    # "RESTOCK" | "EXPIRY" | "STOCKOUT" | "MARGIN"
        priority:   str,    # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
        title:      str,
        message:    str,
        store_id:   str = None,
        product_id: str = None,
        data:       dict = None,
    ):
        self.alert_type = alert_type
        self.priority   = priority
        self.title      = title
        self.message    = message
        self.store_id   = store_id
        self.product_id = product_id
        self.data       = data or {}
        self.created_at = date.today().isoformat()

    def to_dict(self) -> Dict:
        return {
            "alert_type": self.alert_type,
            "priority":   self.priority,
            "title":      self.title,
            "message":    self.message,
            "store_id":   self.store_id,
            "product_id": self.product_id,
            "channels":   ALERT_CHANNELS.get(self.priority, ["dashboard"]),
            "created_at": self.created_at,
            "data":       self.data,
        }


def build_restock_alerts(restock_orders: List[Dict]) -> List[Alert]:
    """
    Converts restock orders into Alert objects.
    Groups by store to avoid flooding with individual alerts.
    """
    alerts = []

    # Group by store + urgency
    critical = [o for o in restock_orders if "CRITICAL" in o.get("urgency", "")]
    high     = [o for o in restock_orders if "HIGH"     in o.get("urgency", "")]

    if critical:
        # One alert per store for critical items
        stores = {}
        for o in critical:
            stores.setdefault(o["store_id"], []).append(o)

        for sid, orders in stores.items():
            top = orders[0]
            alerts.append(Alert(
                alert_type = "RESTOCK",
                priority   = "CRITICAL",
                title      = f"🔴 CRITICAL: {len(orders)} products stockout risk at {sid}",
                message    = (
                    f"Store {sid} has {len(orders)} products that will stock out "
                    f"before supplier delivery. Top item: {top['product_name']} "
                    f"(stock: {top['current_stock']}, order {top['restock_qty']} units "
                    f"from {top['supplier_name']} by {top['order_deadline']})."
                ),
                store_id = sid,
                data     = {"orders": orders[:5]},  # top 5 only in alert
            ))

    if high:
        total_value = sum(o.get("estimated_order_value", 0) for o in high)
        alerts.append(Alert(
            alert_type = "RESTOCK",
            priority   = "HIGH",
            title      = f"🟠 HIGH: {len(high)} restock orders needed today",
            message    = (
                f"{len(high)} products across stores need restock orders today. "
                f"Estimated total order value: ₹{total_value:,.0f}."
            ),
            data = {"orders": high[:10]},
        ))

    return alerts


def build_expiry_alerts(expiry_items: List[Dict]) -> List[Alert]:
    """Converts expiry pricing items into Alert objects."""
    alerts = []

    critical = [i for i in expiry_items if i.get("urgency") == "IMMEDIATE"
                and i.get("days_to_expiry", 99) <= 7]
    high     = [i for i in expiry_items if i.get("days_to_expiry", 99) <= 15
                and i.get("days_to_expiry", 99) > 7]

    if critical:
        total_value = sum(i.get("value_at_risk", 0) for i in critical)
        alerts.append(Alert(
            alert_type = "EXPIRY",
            priority   = "CRITICAL",
            title      = f"🔴 EXPIRY: {len(critical)} products expire within 7 days!",
            message    = (
                f"₹{total_value:,.0f} at risk. Apply 40–50% discount IMMEDIATELY. "
                f"Top item: {critical[0]['product_name']} at {critical[0]['store_name']}."
            ),
            data = {"items": critical[:5]},
        ))

    if high:
        total_value = sum(i.get("value_at_risk", 0) for i in high)
        alerts.append(Alert(
            alert_type = "EXPIRY",
            priority   = "HIGH",
            title      = f"🟠 EXPIRY: {len(high)} products expire in 8–15 days",
            message    = (
                f"₹{total_value:,.0f} at risk. Apply 25–35% discount this week."
            ),
            data = {"items": high[:5]},
        ))

    return alerts


async def dispatch(
    alerts:  List[Alert],
    dry_run: bool = True,   # True = just log, False = actually send
) -> List[Dict]:
    """
    Dispatches alerts to their channels.
    dry_run=True: just logs and returns — safe for testing.
    dry_run=False: calls real notification services (Phase 6).
    """
    dispatched = []

    for alert in alerts:
        channels = ALERT_CHANNELS.get(alert.priority, ["dashboard"])
        logger.info(f"[{alert.priority}] {alert.title} → {channels}")

        if not dry_run:
            # Phase 6 will plug in here:
            # from app.notifications.whatsapp_service import send_message
            # from app.notifications.telegram_service import send_message
            # for channel in channels:
            #     send_message(alert.message)
            pass

        dispatched.append({
            **alert.to_dict(),
            "dispatched": not dry_run,
            "dry_run":    dry_run,
        })

    return dispatched
