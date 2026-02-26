from pydantic import BaseModel


class RecipeUploadResponse(BaseModel):
    recipes_created: int
    ingredients_created: int
    sku_jobs_enqueued: int
