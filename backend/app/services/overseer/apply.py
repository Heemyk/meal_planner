"""Apply overseer corrections to DB."""

from __future__ import annotations

from sqlmodel import Session, select

from app.logging import get_logger
from app.storage.models import Ingredient, RecipeIngredient, SKU

logger = get_logger(__name__)


def apply_corrections(session: Session, corrections: list[dict]) -> int:
    """
    Apply overseer corrections. Returns count of changes applied.
    corrections: [{"type": "ingredient"|"recipe_ingredient"|"sku", "id": int, ...}]
    """
    applied = 0
    for c in corrections:
        ctype = (c.get("type") or "").strip().lower()
        cid = c.get("id")
        if cid is None:
            continue
        try:
            if ctype == "ingredient":
                ing = session.exec(select(Ingredient).where(Ingredient.id == int(cid))).first()
                if ing:
                    if "base_unit" in c and c["base_unit"]:
                        ing.base_unit = str(c["base_unit"]).strip().lower()
                        session.add(ing)
                        applied += 1
                        logger.info("overseer.apply ingredient id=%s base_unit=%s", cid, ing.base_unit)
            elif ctype == "recipe_ingredient":
                ri = session.exec(select(RecipeIngredient).where(RecipeIngredient.id == int(cid))).first()
                if ri:
                    if "quantity" in c:
                        try:
                            ri.quantity = float(c["quantity"])
                            session.add(ri)
                            applied += 1
                        except (TypeError, ValueError):
                            pass
                    if "unit" in c and c["unit"]:
                        ri.unit = str(c["unit"]).strip().lower()
                        session.add(ri)
                        applied += 1
                    if applied:
                        logger.info("overseer.apply recipe_ingredient id=%s quantity=%s unit=%s", cid, getattr(ri, "quantity", None), getattr(ri, "unit", None))
            elif ctype == "sku":
                sku = session.exec(select(SKU).where(SKU.id == int(cid))).first()
                if sku and "quantity_in_base_unit" in c:
                    try:
                        sku.quantity_in_base_unit = float(c["quantity_in_base_unit"])
                        session.add(sku)
                        applied += 1
                        logger.info("overseer.apply sku id=%s quantity_in_base_unit=%s", cid, sku.quantity_in_base_unit)
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logger.warning("overseer.apply_failed type=%s id=%s error=%s", ctype, cid, e)
    if applied:
        session.commit()
    return applied
