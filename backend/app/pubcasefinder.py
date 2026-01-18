from __future__ import annotations

import logging
import re

import httpx
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from .config import settings
from .schemas import DiseasePrediction

logger = logging.getLogger(__name__)


def _split_matched_hpo_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if parts:
        return parts
    return re.findall(r"HP:\d{7}", raw)


@retry(
    wait=wait_exponential(min=0.5, max=5),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(httpx.HTTPError),
    before_sleep=lambda retry_state: logger.warning(
        f"Retry {retry_state.attempt_number}/3 for PubCaseFinder API"
    ),
)
async def get_ranked_list(hpo_ids: list[str], target: str = "omim") -> list[dict]:
    params = {
        "target": target,
        "format": "json",
        "hpo_id": ",".join(hpo_ids),
    }
    logger.info(f"Calling PubCaseFinder API with {len(hpo_ids)} HPO IDs (target={target})")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{settings.pubcasefinder_base_url}/pcf_get_ranked_list", params=params)
        r.raise_for_status()
        result = r.json()
        logger.info(f"PubCaseFinder returned {len(result)} results")
        return result


async def predict_diseases(hpo_ids: list[str], target: str = "omim", limit: int = 20) -> list[DiseasePrediction]:
    raw = await get_ranked_list(hpo_ids=hpo_ids, target=target)
    out: list[DiseasePrediction] = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue

        disease_id = str(item.get("id", "")).strip()
        if not disease_id:
            continue

        score = None
        try:
            score = float(item.get("score")) if item.get("score") is not None else None
        except Exception:
            score = None

        rank = None
        try:
            rank = int(item.get("rank")) if item.get("rank") is not None else None
        except Exception:
            rank = None

        if target == "omim":
            name_en = item.get("omim_disease_name_en")
            name_ja = item.get("omim_disease_name_ja")
            url = item.get("omim_url")
        elif target == "orphanet":
            name_en = item.get("orpha_disease_name_en")
            name_ja = item.get("orpha_disease_name_ja")
            url = item.get("orpha_url")
        else:
            name_en = None
            name_ja = None
            url = None

        out.append(
            DiseasePrediction(
                id=disease_id,
                rank=rank,
                score=score,
                disease_name_en=name_en,
                disease_name_ja=name_ja,
                disease_url=url,
                matched_hpo_ids=_split_matched_hpo_ids(item.get("matched_hpo_id")),
            )
        )
    return out

