from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import END
from langgraph.graph import StateGraph
from pydantic import BaseModel
from pydantic import Field

from .hpo_store import HPOEntry
from .hpo_store import similarity_search
from .openai_clients import get_chat_model
from .config import settings
from .schemas import NormalizedSymptom
from .schemas import TextSpan
from .utils import dedupe_spans
from .utils import find_all_occurrences
from .utils import normalize_whitespace

logger = logging.getLogger(__name__)


class ExtractedSymptomRaw(BaseModel):
    symptom: str = Field(min_length=1)
    spans: list[TextSpan] = Field(default_factory=list)
    negated_spans: list[TextSpan] = Field(default_factory=list)


class ExtractionOutput(BaseModel):
    symptoms: list[ExtractedSymptomRaw] = Field(default_factory=list)


class HPOChoice(BaseModel):
    hpo_id: str | None = None


class GraphState(TypedDict):
    text: str
    extracted: list[ExtractedSymptomRaw]
    normalized: list[NormalizedSymptom]


def _extract_symptoms_node(state: GraphState) -> GraphState:
    text = normalize_whitespace(state["text"])
    model = get_chat_model().with_structured_output(ExtractionOutput)

    prompt = (
        "あなたは臨床文章から“症状(=患者の所見/症候)”を抽出する専門家です。\n"
        "次の日本語テキストから症状に当たる表現を抽出してJSONで返してください。\n"
        "\n"
        "要件:\n"
        "- 症状は重複させず、同じ症状語が複数回あっても symptom は1つにまとめる\n"
        "- ただしハイライトのため、spans には本文中の出現箇所を1つ以上入れる\n"
        "- spans の start/end は0始まりの文字インデックスで、text[start:end] と一致すること\n"
        "- 否定(例: 〜ない/〜なし/否定/認めず)の症状は negated_spans に入れ、spans(肯定)には入れない\n"
        "- 病名・検査名・臓器名・年齢・性別などは症状ではないので除外\n"
        "- 出力は必ずJSONのみ\n"
        "\n"
        f"本文:\n{text}"
    )

    try:
        out = model.invoke(prompt)
        logger.info(f"Extracted {len(out.symptoms)} raw symptoms from text")
    except Exception as e:
        logger.error(f"Failed to extract symptoms: {e}")
        raise

    extracted: list[ExtractedSymptomRaw] = []
    for s in out.symptoms:
        symptom = s.symptom.strip()
        if not symptom:
            continue
        extracted.append(
            ExtractedSymptomRaw(
                symptom=symptom,
                spans=s.spans,
                negated_spans=s.negated_spans,
            )
        )

    logger.debug(f"Processed {len(extracted)} valid symptoms")
    return {**state, "text": text, "extracted": extracted}


def _expand_spans(text: str, symptom: str, spans: list[TextSpan]) -> list[TextSpan]:
    occurrences = find_all_occurrences(text, symptom)
    if occurrences:
        pairs = dedupe_spans(occurrences)
        return [TextSpan(start=s, end=e, text=text[s:e]) for s, e in pairs]

    repaired: list[tuple[int, int]] = []
    for sp in spans:
        if 0 <= sp.start < sp.end <= len(text) and text[sp.start : sp.end] == sp.text:
            repaired.append((sp.start, sp.end))
        elif sp.text:
            repaired.extend(find_all_occurrences(text, sp.text))

    repaired = dedupe_spans(repaired)
    return [TextSpan(start=s, end=e, text=text[s:e]) for s, e in repaired]


def _choose_hpo_id(symptom: str, evidence: str, candidates: list[HPOEntry]) -> str:
    model = get_chat_model().with_structured_output(HPOChoice)
    c_text = "\n\n".join(
        [
            f"- {c.hpo_id}\n  日本語:{c.label_ja}\n  英語:{c.label_en}\n  定義:{c.definition_ja}"
            for c in candidates
        ]
    )
    no_fit_rule = (
        "- 候補に適切なものが無い場合は hpo_id を null にする\n"
        if settings.allow_no_candidate_fit
        else "- 候補に適切なものが無い場合でも、最も近いものを選ぶ\n"
    )
    prompt = (
        "あなたはHPO(Human Phenotype Ontology)の正規化担当です。\n"
        "与えられた症状表現を、候補リストの中から最も適切なHPO IDを1つだけ選んでください。\n"
        "制約:\n"
        "- 返す hpo_id は必ず候補のいずれかと完全一致させる\n"
        f"{no_fit_rule}"
        "\n"
        f"症状表現: {symptom}\n"
        f"根拠(本文抜粋): {evidence}\n"
        "\n"
        f"候補:\n{c_text}"
    )
    
    try:
        choice = model.invoke(prompt)
        chosen_id = choice.hpo_id.strip() if choice.hpo_id else ""

        if not chosen_id:
            return ""
        
        # バリデーション: LLMが候補以外のIDを返した場合
        valid_ids = {c.hpo_id for c in candidates}
        if chosen_id not in valid_ids:
            logger.warning(
                f"LLM returned invalid HPO ID: {chosen_id} for symptom '{symptom}'. "
                f"Using first candidate: {candidates[0].hpo_id}"
            )
            return candidates[0].hpo_id
        
        logger.debug(f"Mapped symptom '{symptom}' to {chosen_id}")
        return chosen_id
    except Exception as e:
        logger.error(f"Failed to choose HPO ID for symptom '{symptom}': {e}")
        # フォールバック: 最初の候補を使用
        return candidates[0].hpo_id if candidates else ""


def _normalize_hpo_node(state: GraphState) -> GraphState:
    text = state["text"]
    normalized: list[NormalizedSymptom] = []

    for s in state["extracted"]:
        symptom = s.symptom.strip()
        spans = _expand_spans(text, symptom, s.spans)
        if not spans:
            continue
        evidence = " / ".join([sp.text for sp in spans[:3]])

        candidates = similarity_search(query=f"{symptom}\n{evidence}", k=8)
        chosen_id = ""
        chosen: HPOEntry | None = None
        if candidates:
            chosen_id = _choose_hpo_id(symptom=symptom, evidence=evidence, candidates=candidates)
            if chosen_id:
                chosen = next((c for c in candidates if c.hpo_id == chosen_id), candidates[0])

        normalized.append(
            NormalizedSymptom(
                symptom=symptom,
                spans=spans,
                evidence=evidence,
                hpo_id=chosen.hpo_id if chosen else None,
                label_en=chosen.label_en if chosen else None,
                label_ja=chosen.label_ja if chosen else None,
                hpo_url=f"https://hpo.jax.org/browse/term/{chosen.hpo_id}" if chosen else None,
            )
        )

    normalized.sort(key=lambda x: (x.hpo_id is None, x.hpo_id or ""))
    return {**state, "normalized": normalized}


graph = StateGraph(GraphState)
graph.add_node("extract", _extract_symptoms_node)
graph.add_node("normalize", _normalize_hpo_node)
graph.set_entry_point("extract")
graph.add_edge("extract", "normalize")
graph.add_edge("normalize", END)

app_graph = graph.compile()


def run_graph(text: str) -> list[NormalizedSymptom]:
    state: GraphState = {"text": text, "extracted": [], "normalized": []}
    out = app_graph.invoke(state)
    return out["normalized"]
