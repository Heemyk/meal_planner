"""Detect anomalous purchase quantities or costs in plan results."""

from __future__ import annotations

import statistics


def detect_anomalies(
    sku_details: dict[str, dict],
    sku_id_to_ingredient_id: dict[str, int],
) -> list[dict]:
    """
    Flag SKU entries with unusually high purchase quantity or cost.
    Returns list of {"type": "sku", "sku_id", "ingredient_id", "detail": {...}, "reason": str}.
    """
    anomalies: list[dict] = []

    if not sku_details:
        return anomalies

    quantities = [d.get("quantity", 0) for d in sku_details.values() if d.get("quantity")]
    costs = []
    for d in sku_details.values():
        q = d.get("quantity", 0) or 0
        p = d.get("price") or 0
        if q and p:
            costs.append(p * q)

    qty_threshold = 10
    if len(quantities) >= 2:
        try:
            mean_qty = statistics.mean(quantities)
            stdev_qty = statistics.stdev(quantities)
            qty_threshold = max(10, mean_qty + 2 * stdev_qty)
        except statistics.StatisticsError:
            pass

    median_cost = statistics.median(costs) if costs else 0.0
    cost_threshold = median_cost * 3 if median_cost > 0 else 100.0

    for sku_id, d in sku_details.items():
        qty = d.get("quantity", 0) or 0
        price = d.get("price") or 0
        total_cost = price * qty
        ing_id = sku_id_to_ingredient_id.get(sku_id)
        if ing_id is None:
            continue
        reasons = []
        if qty > qty_threshold:
            reasons.append(f"purchase qty {qty} >> typical ({qty_threshold:.0f})")
        if median_cost > 0 and total_cost > cost_threshold:
            reasons.append(f"total ${total_cost:.2f} >> median ${median_cost:.2f}")
        if reasons:
            anomalies.append({
                "type": "sku",
                "sku_id": sku_id,
                "ingredient_id": ing_id,
                "detail": d,
                "reason": "; ".join(reasons),
            })

    return anomalies
