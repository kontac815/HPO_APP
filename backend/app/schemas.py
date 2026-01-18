from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class TextSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = Field(min_length=1)


class ExtractedSymptom(BaseModel):
    symptom: str = Field(min_length=1)
    spans: list[TextSpan] = Field(default_factory=list)


class NormalizedSymptom(BaseModel):
    symptom: str
    spans: list[TextSpan]
    evidence: str
    hpo_id: str | None = None
    label_en: str | None = None
    label_ja: str | None = None
    hpo_url: str | None = None


class ExtractResponse(BaseModel):
    text: str
    symptoms: list[NormalizedSymptom]


class PredictRequest(BaseModel):
    hpo_ids: list[str] = Field(default_factory=list)
    target: Literal["omim", "orphanet", "gene"] = "omim"
    limit: int = Field(default=20, ge=1, le=200)


class DiseasePrediction(BaseModel):
    id: str
    rank: int | None = None
    score: float | None = None
    disease_name_en: str | None = None
    disease_name_ja: str | None = None
    disease_url: str | None = None
    matched_hpo_ids: list[str] = Field(default_factory=list)


class PredictResponse(BaseModel):
    target: Literal["omim", "orphanet", "gene"]
    hpo_ids: list[str]
    predictions: list[DiseasePrediction]
