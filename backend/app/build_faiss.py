from __future__ import annotations

import argparse
import logging
import time

from .config import settings
from .hpo_store import build_or_load_store


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or load FAISS index for HPO RAG.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild even if an index already exists.",
    )
    args = parser.parse_args()

    start = time.time()
    logger.info(
        "Initializing FAISS store (csv=%s, dir=%s, rebuild=%s)",
        settings.hpo_csv_path,
        settings.faiss_dir,
        args.rebuild,
    )
    store, hpo_by_id = build_or_load_store(force_rebuild=bool(args.rebuild))
    elapsed = time.time() - start
    logger.info("FAISS ready (terms=%d, elapsed=%.2fs)", len(hpo_by_id), elapsed)

    _ = store


if __name__ == "__main__":
    main()

