from __future__ import annotations

import csv
import os
import threading
from dataclasses import dataclass

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .config import settings
from .openai_clients import get_embeddings


@dataclass(frozen=True)
class HPOEntry:
    hpo_id: str
    label_en: str
    label_ja: str
    definition_ja: str


_faiss_store: FAISS | None = None
_hpo_by_id: dict[str, HPOEntry] | None = None

_store_init_lock = threading.Lock()
_store_init_started = False
_store_ready = threading.Event()
_store_error: Exception | None = None


class StoreNotReadyError(RuntimeError):
    pass


def _list_csv_files(dir_path: str) -> list[str]:
    try:
        names = os.listdir(dir_path)
    except FileNotFoundError:
        return []
    return sorted([name for name in names if name.lower().endswith(".csv")])


def _resolve_hpo_csv_path(configured_path: str) -> str:
    if os.path.isfile(configured_path):
        return configured_path

    if os.path.isdir(configured_path):
        default_name = "HPO_depth_ge3.csv"
        default_path = os.path.join(configured_path, default_name)
        if os.path.isfile(default_path):
            return default_path

        csv_files = _list_csv_files(configured_path)
        if len(csv_files) == 1:
            return os.path.join(configured_path, csv_files[0])

        if not csv_files:
            raise FileNotFoundError(
                "HPO_CSV_PATH points to a directory with no .csv files: "
                f"{configured_path} (mount a CSV file to /data/HPO_depth_ge3.csv, "
                f"or put {default_name} inside that directory)"
            )

        raise FileNotFoundError(
            "HPO_CSV_PATH points to a directory with multiple .csv files: "
            f"{configured_path} (set HPO_CSV_PATH to a specific file, or keep only one .csv here: "
            f"{', '.join(csv_files)})"
        )

    raise FileNotFoundError(
        f"HPO CSV not found: {configured_path} (set HPO_CSV_PATH to your HPO_depth_ge3.csv)"
    )


def _read_hpo_csv(csv_path: str) -> list[HPOEntry]:
    entries: list[HPOEntry] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hpo_id = (row.get("HPO_ID") or "").strip()
            if not hpo_id.startswith("HP:"):
                continue
            label_en = (row.get("name_en") or "").strip()
            label_ja = (row.get("jp_final") or "").strip()
            definition_ja = (row.get("definition_ja") or "").strip()
            if not label_ja:
                continue
            entries.append(
                HPOEntry(
                    hpo_id=hpo_id,
                    label_en=label_en,
                    label_ja=label_ja,
                    definition_ja=definition_ja,
                )
            )
    return entries


def _entries_to_documents(entries: list[HPOEntry]) -> list[Document]:
    docs: list[Document] = []
    for e in entries:
        page_content = "\n".join(
            [
                f"HPO_ID: {e.hpo_id}",
                f"日本語ラベル: {e.label_ja}",
                f"英語ラベル: {e.label_en}",
                f"日本語定義: {e.definition_ja}",
            ]
        )
        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "hpo_id": e.hpo_id,
                    "label_ja": e.label_ja,
                    "label_en": e.label_en,
                },
            )
        )
    return docs


def build_or_load_store(force_rebuild: bool = False) -> tuple[FAISS, dict[str, HPOEntry]]:
    global _faiss_store, _hpo_by_id
    if not force_rebuild and _faiss_store is not None and _hpo_by_id is not None:
        _store_ready.set()
        return _faiss_store, _hpo_by_id

    os.makedirs(settings.faiss_dir, exist_ok=True)

    hpo_csv_path = _resolve_hpo_csv_path(settings.hpo_csv_path)
    entries = _read_hpo_csv(hpo_csv_path)
    hpo_by_id = {e.hpo_id: e for e in entries}
    embeddings = get_embeddings()

    index_exists = os.path.exists(os.path.join(settings.faiss_dir, "index.faiss")) and os.path.exists(
        os.path.join(settings.faiss_dir, "index.pkl")
    )

    should_rebuild = force_rebuild or settings.rebuild_faiss_on_startup

    if index_exists and not should_rebuild:
        store = FAISS.load_local(settings.faiss_dir, embeddings, allow_dangerous_deserialization=True)
    else:
        docs = _entries_to_documents(entries)
        store = FAISS.from_documents(docs, embeddings)
        store.save_local(settings.faiss_dir)

    _faiss_store = store
    _hpo_by_id = hpo_by_id
    _store_ready.set()
    return store, hpo_by_id


def start_store_init_background(force_rebuild: bool = False) -> None:
    global _store_init_started
    with _store_init_lock:
        if _store_ready.is_set() or _store_init_started:
            return
        _store_init_started = True

    def _worker() -> None:
        global _store_error
        try:
            build_or_load_store(force_rebuild=force_rebuild)
        except Exception as e:
            _store_error = e
            _store_ready.set()

    t = threading.Thread(target=_worker, name="hpo_store_init", daemon=True)
    t.start()


def store_ready() -> bool:
    return _store_ready.is_set() and _store_error is None and _faiss_store is not None and _hpo_by_id is not None


def require_store_ready() -> None:
    if store_ready():
        return

    start_store_init_background()

    if _store_ready.is_set() and _store_error is not None:
        raise StoreNotReadyError(f"HPO store initialization failed: {_store_error}")
    raise StoreNotReadyError("HPO store is initializing. Please wait and retry.")


def similarity_search(query: str, k: int = 8) -> list[HPOEntry]:
    require_store_ready()
    store, hpo_by_id = build_or_load_store()
    results = store.similarity_search(query, k=k)
    out: list[HPOEntry] = []
    for doc in results:
        hpo_id = (doc.metadata or {}).get("hpo_id")
        if not isinstance(hpo_id, str):
            continue
        entry = hpo_by_id.get(hpo_id)
        if entry is None:
            continue
        out.append(entry)
    return out
