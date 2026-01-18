from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .graph import run_graph
from .hpo_store import StoreNotReadyError
from .hpo_store import require_store_ready
from .hpo_store import start_store_init_background
from .hpo_store import store_ready
from .pubcasefinder import predict_diseases
from .schemas import ExtractRequest
from .schemas import ExtractResponse
from .schemas import PredictRequest
from .schemas import PredictResponse
from .utils import normalize_whitespace

# ロギング設定
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HPO Normalizer + PubCaseFinder Demo", version="0.1.0")

# CORS設定を環境変数化
allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    logger.info(f"Starting HPO Normalizer with CORS origins: {allowed_origins}")
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is not set. API endpoints will fail.")
        return
    start_store_init_background()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "store_ready": store_ready()}


@app.post("/api/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest) -> ExtractResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is missing")
    try:
        require_store_ready()
    except StoreNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    text = normalize_whitespace(req.text)
    symptoms = run_graph(text)
    return ExtractResponse(text=text, symptoms=symptoms)


@app.post("/api/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    if not req.hpo_ids:
        return PredictResponse(target=req.target, hpo_ids=[], predictions=[])
    preds = await predict_diseases(hpo_ids=req.hpo_ids, target=req.target, limit=req.limit)
    return PredictResponse(target=req.target, hpo_ids=req.hpo_ids, predictions=preds)
