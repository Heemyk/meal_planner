"""
Generate final materials (descriptions, card metadata) post-plan.
"""

from fastapi import APIRouter, HTTPException

from app.services.llm.materials_generator import generate_materials

router = APIRouter()


@router.post("/generate-materials")
def post_generate_materials(body: dict):
    """
    Generate tone, descriptions, and card metadata for menu_card.
    Expects: { "menu_card": [ { "name", "ingredients", "instructions", "meal_type", ... } ] }
    Returns enriched menu_card with generated_description, theme.
    """
    menu_card = body.get("menu_card") or []
    if not menu_card:
        raise HTTPException(status_code=400, detail="menu_card is required and must not be empty")

    try:
        enriched = generate_materials(menu_card)
        return {"menu_card": enriched, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
