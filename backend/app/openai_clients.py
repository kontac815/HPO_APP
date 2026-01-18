from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings

from .config import settings


def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_chat_model,
        temperature=0,
    )


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embed_model,
    )

