from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "tandem-recipes"
    env: str = "local"

    postgres_dsn: str = "postgresql+psycopg2://tandem:tandem@postgres:5432/tandem"
    neo4j_uri: str = "neo4j://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    redis_url: str = "redis://redis:6379/0"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_model_reasoning: str = "gpt-4o"  # Smarter model for math/reasoning (SKU conversion, etc.)
    llm_api_key: str = ""
    llm_temperature: float = 0.2
    llm_timeout_s: int = 30

    instacart_api_key: str = ""
    instacart_base_url: str = "https://api.parse.bot/scraper/fe062683-8089-4dd2-98b2-48603e6795f8"
    default_postal_code: str = "10001"
    sku_cache_ttl_hours: int = 24

    # Tune parallelism: ThreadPoolExecutor workers for ingredient match+normalize per recipe.
    # Set INGREDIENT_BATCH_MAX_WORKERS in .env to override.
    ingredient_batch_max_workers: int = 8

    # Celery prefork concurrency for fetch_skus_for_ingredient tasks.
    celery_worker_concurrency: int = 10

    # Hybrid ingredient matching: above this count, use embedding retrieval for top-k
    ingredient_match_full_context_threshold: int = 20
    ingredient_retrieval_top_k: int = 10

    # Use LLM for allergen inference (more robust). If False, use keyword fallback.
    use_llm_allergens: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
