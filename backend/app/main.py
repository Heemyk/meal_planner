from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.logging import configure_logging, get_logger
from app.services.llm.dspy_client import configure_dspy
from app.storage.db import create_db_and_tables

app = FastAPI(title="Tandem Recipes API")
logger = get_logger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    configure_logging()
    logger.info("startup: configuring services")
    configure_dspy()
    create_db_and_tables()


app.include_router(api_router)
