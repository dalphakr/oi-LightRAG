from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

ENV_PATH = os.getenv("LIGHTRAG_ENV_PATH")
if ENV_PATH:
    load_dotenv(ENV_PATH, override=False)
else:
    candidate_envs = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        Path(__file__).parent / ".env",
    ]
    for env_path in candidate_envs:
        if env_path.exists():
            load_dotenv(env_path, override=False)

from lightrag import LightRAG
from lightrag.base import QueryParam
from lightrag.utils import EmbeddingFunc, get_env_value, logger, wrap_embedding_func_with_attrs

from mcp.server.fastmcp import FastMCP


def _default_host(binding: str) -> str:
    binding = binding.lower()
    if binding == "ollama":
        return "http://localhost:11434"
    if binding == "lollms":
        return "http://localhost:9600"
    if binding == "openai":
        return "https://api.openai.com/v1"
    if binding == "azure_openai":
        return os.getenv("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
    if binding == "gemini":
        return "https://generativelanguage.googleapis.com"
    return "http://localhost:11434"


@dataclass(frozen=True)
class MCPSettings:
    working_dir: str
    workspace: str
    kv_storage: str
    vector_storage: str
    graph_storage: str
    doc_status_storage: str
    llm_binding: str
    llm_model: str
    llm_binding_host: str
    llm_binding_api_key: str | None
    llm_timeout: int
    embedding_binding: str
    embedding_model: str | None
    embedding_dim: int | None
    embedding_binding_host: str
    embedding_binding_api_key: str | None
    embedding_token_limit: int | None
    embedding_send_dim: bool
    embedding_timeout: int

    @classmethod
    def from_env(cls) -> "MCPSettings":
        llm_binding = get_env_value("LLM_BINDING", "ollama").lower()
        embedding_binding = get_env_value("EMBEDDING_BINDING", "ollama").lower()
        if llm_binding == "openai-ollama":
            llm_binding = "openai"
            if os.getenv("EMBEDDING_BINDING") is None:
                embedding_binding = "ollama"

        return cls(
            working_dir=get_env_value("WORKING_DIR", "./rag_storage"),
            workspace=get_env_value("WORKSPACE", ""),
            kv_storage=get_env_value("LIGHTRAG_KV_STORAGE", "JsonKVStorage"),
            vector_storage=get_env_value("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage"),
            graph_storage=get_env_value("LIGHTRAG_GRAPH_STORAGE", "NetworkXStorage"),
            doc_status_storage=get_env_value(
                "LIGHTRAG_DOC_STATUS_STORAGE", "JsonDocStatusStorage"
            ),
            llm_binding=llm_binding,
            llm_model=get_env_value("LLM_MODEL", "mistral-nemo:latest"),
            llm_binding_host=get_env_value(
                "LLM_BINDING_HOST", _default_host(llm_binding)
            ),
            llm_binding_api_key=get_env_value("LLM_BINDING_API_KEY", None),
            llm_timeout=get_env_value("LLM_TIMEOUT", 150, int),
            embedding_binding=embedding_binding,
            embedding_model=get_env_value("EMBEDDING_MODEL", None, special_none=True),
            embedding_dim=get_env_value("EMBEDDING_DIM", None, int, special_none=True),
            embedding_binding_host=get_env_value(
                "EMBEDDING_BINDING_HOST", _default_host(embedding_binding)
            ),
            embedding_binding_api_key=get_env_value("EMBEDDING_BINDING_API_KEY", None),
            embedding_token_limit=get_env_value(
                "EMBEDDING_TOKEN_LIMIT", None, int, special_none=True
            ),
            embedding_send_dim=get_env_value("EMBEDDING_SEND_DIM", False, bool),
            embedding_timeout=get_env_value("EMBEDDING_TIMEOUT", 30, int),
        )


def _build_llm_model_func(
    settings: MCPSettings,
) -> tuple[Callable[..., Any], dict[str, Any]]:
    binding = settings.llm_binding
    llm_kwargs: dict[str, Any] = {}

    if binding == "ollama":
        from lightrag.llm.ollama import ollama_model_complete

        llm_func = ollama_model_complete
        llm_kwargs = {
            "host": settings.llm_binding_host,
            "api_key": settings.llm_binding_api_key,
            "timeout": settings.llm_timeout,
        }
    elif binding == "openai":
        from lightrag.llm.openai import openai_complete

        llm_func = openai_complete
        llm_kwargs = {
            "base_url": settings.llm_binding_host,
            "api_key": settings.llm_binding_api_key,
            "timeout": settings.llm_timeout,
        }
    elif binding == "azure_openai":
        from lightrag.llm.azure_openai import azure_openai_complete

        llm_func = azure_openai_complete
        llm_kwargs = {
            "base_url": settings.llm_binding_host,
            "api_key": settings.llm_binding_api_key,
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
            "timeout": settings.llm_timeout,
        }
    elif binding == "gemini":
        from lightrag.llm.gemini import gemini_complete_if_cache

        async def llm_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, Any]] | None = None,
            enable_cot: bool = False,
            **kwargs: Any,
        ) -> str:
            return await gemini_complete_if_cache(
                settings.llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                enable_cot=enable_cot,
                **kwargs,
            )

        llm_kwargs = {
            "base_url": settings.llm_binding_host,
            "api_key": settings.llm_binding_api_key,
            "timeout": settings.llm_timeout,
        }
    elif binding == "aws_bedrock":
        from lightrag.llm.bedrock import bedrock_model_complete

        llm_func = bedrock_model_complete
    elif binding == "lollms":
        from lightrag.llm.lollms import lollms_model_complete

        llm_func = lollms_model_complete
        llm_kwargs = {
            "host": settings.llm_binding_host,
            "api_key": settings.llm_binding_api_key,
        }
    else:
        raise ValueError(f"Unsupported LLM_BINDING: {binding}")

    return llm_func, llm_kwargs


def _build_embedding_func(settings: MCPSettings) -> EmbeddingFunc:
    binding = settings.embedding_binding
    embedding_func: EmbeddingFunc | Callable[..., Any]

    if binding == "ollama":
        from lightrag.llm.ollama import ollama_embed as embedding_func
    elif binding == "openai":
        from lightrag.llm.openai import openai_embed as embedding_func
    elif binding == "azure_openai":
        from lightrag.llm.openai import openai_embed as embedding_func
    elif binding == "gemini":
        from lightrag.llm.gemini import gemini_embed as embedding_func
    elif binding == "jina":
        from lightrag.llm.jina import jina_embed as embedding_func
    elif binding == "lollms":
        from lightrag.llm.lollms import lollms_embed as embedding_func
    elif binding == "aws_bedrock":
        from lightrag.llm.bedrock import bedrock_embed as embedding_func
    else:
        raise ValueError(f"Unsupported EMBEDDING_BINDING: {binding}")

    provider_dim = embedding_func.embedding_dim if isinstance(embedding_func, EmbeddingFunc) else None
    provider_max_tokens = (
        embedding_func.max_token_size if isinstance(embedding_func, EmbeddingFunc) else None
    )
    provider_model = (
        embedding_func.model_name if isinstance(embedding_func, EmbeddingFunc) else None
    )
    raw_func = embedding_func.func if isinstance(embedding_func, EmbeddingFunc) else embedding_func

    embedding_dim = settings.embedding_dim or provider_dim
    if embedding_dim is None:
        raise ValueError("EMBEDDING_DIM is required for this embedding binding")

    if binding in {"ollama", "lollms", "aws_bedrock"} and provider_dim:
        if settings.embedding_dim and settings.embedding_dim != provider_dim:
            raise ValueError(
                f"{binding} does not support custom EMBEDDING_DIM (expected {provider_dim})"
            )

    model_name = settings.embedding_model or provider_model
    max_token_size = settings.embedding_token_limit or provider_max_tokens

    send_dimensions = settings.embedding_send_dim
    if binding in {"jina", "gemini"}:
        send_dimensions = True
    elif provider_dim and settings.embedding_dim and settings.embedding_dim != provider_dim:
        send_dimensions = True

    async def embed(texts: list[str], embedding_dim: int | None = None, **kwargs: Any):
        if binding == "ollama":
            return await raw_func(
                texts,
                embed_model=model_name or "bge-m3:latest",
                host=settings.embedding_binding_host,
                api_key=settings.embedding_binding_api_key,
                timeout=settings.embedding_timeout,
                **kwargs,
            )
        if binding == "openai":
            call_kwargs = {
                "base_url": settings.embedding_binding_host,
                "api_key": settings.embedding_binding_api_key,
                "embedding_dim": embedding_dim,
            }
            if model_name:
                call_kwargs["model"] = model_name
            return await raw_func(texts, **call_kwargs)
        if binding == "azure_openai":
            deployment = model_name or os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
            call_kwargs = {
                "base_url": settings.embedding_binding_host,
                "api_key": settings.embedding_binding_api_key,
                "embedding_dim": embedding_dim,
                "use_azure": True,
                "azure_deployment": deployment,
                "api_version": os.getenv("AZURE_EMBEDDING_API_VERSION"),
            }
            if deployment:
                call_kwargs["model"] = deployment
            return await raw_func(texts, **call_kwargs)
        if binding == "gemini":
            call_kwargs = {
                "base_url": settings.embedding_binding_host,
                "api_key": settings.embedding_binding_api_key,
                "embedding_dim": embedding_dim,
                "timeout": settings.embedding_timeout,
            }
            if model_name:
                call_kwargs["model"] = model_name
            return await raw_func(texts, **call_kwargs)
        if binding == "jina":
            call_kwargs = {
                "base_url": settings.embedding_binding_host,
                "api_key": settings.embedding_binding_api_key,
                "embedding_dim": embedding_dim,
            }
            if model_name:
                call_kwargs["model"] = model_name
            return await raw_func(texts, **call_kwargs)
        if binding == "lollms":
            return await raw_func(
                texts,
                embed_model=model_name,
                base_url=settings.embedding_binding_host,
                api_key=settings.embedding_binding_api_key,
            )
        if binding == "aws_bedrock":
            call_kwargs = {}
            if model_name:
                call_kwargs["model"] = model_name
            return await raw_func(texts, **call_kwargs)
        raise ValueError(f"Unsupported EMBEDDING_BINDING: {binding}")

    return wrap_embedding_func_with_attrs(
        embedding_dim=embedding_dim,
        max_token_size=max_token_size,
        model_name=model_name,
        send_dimensions=send_dimensions,
    )(embed)


def _build_query_param(
    *,
    mode: str,
    only_need_context: bool | None,
    only_need_prompt: bool | None,
    response_type: str | None,
    top_k: int | None,
    chunk_top_k: int | None,
    max_entity_tokens: int | None,
    max_relation_tokens: int | None,
    max_total_tokens: int | None,
    hl_keywords: list[str] | None,
    ll_keywords: list[str] | None,
    conversation_history: list[dict[str, str]] | None,
    user_prompt: str | None,
    enable_rerank: bool | None,
    include_references: bool | None,
) -> QueryParam:
    param = QueryParam(mode=mode)
    param.stream = False
    if only_need_context is not None:
        param.only_need_context = only_need_context
    if only_need_prompt is not None:
        param.only_need_prompt = only_need_prompt
    if response_type:
        param.response_type = response_type
    if top_k is not None:
        param.top_k = top_k
    if chunk_top_k is not None:
        param.chunk_top_k = chunk_top_k
    if max_entity_tokens is not None:
        param.max_entity_tokens = max_entity_tokens
    if max_relation_tokens is not None:
        param.max_relation_tokens = max_relation_tokens
    if max_total_tokens is not None:
        param.max_total_tokens = max_total_tokens
    if hl_keywords is not None:
        param.hl_keywords = hl_keywords
    if ll_keywords is not None:
        param.ll_keywords = ll_keywords
    if conversation_history is not None:
        param.conversation_history = conversation_history
    if user_prompt is not None:
        param.user_prompt = user_prompt
    if enable_rerank is not None:
        param.enable_rerank = enable_rerank
    if include_references is not None:
        param.include_references = include_references
    return param


_rag: LightRAG | None = None
_rag_lock = asyncio.Lock()


async def _get_rag() -> LightRAG:
    global _rag
    if _rag is not None:
        return _rag
    async with _rag_lock:
        if _rag is not None:
            return _rag
        settings = MCPSettings.from_env()
        llm_model_func, llm_model_kwargs = _build_llm_model_func(settings)
        embedding_func = _build_embedding_func(settings)
        _rag = LightRAG(
            working_dir=settings.working_dir,
            workspace=settings.workspace,
            kv_storage=settings.kv_storage,
            vector_storage=settings.vector_storage,
            graph_storage=settings.graph_storage,
            doc_status_storage=settings.doc_status_storage,
            llm_model_func=llm_model_func,
            llm_model_kwargs=llm_model_kwargs,
            llm_model_name=settings.llm_model,
            embedding_func=embedding_func,
            default_llm_timeout=settings.llm_timeout,
        )
        await _rag.initialize_storages()
        await _rag.check_and_migrate_data()
        logger.info("LightRAG initialized for MCP queries.")
        return _rag


MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
mcp = FastMCP("LightRAG", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
async def rag_query(
    query: str,
    mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = "mix",
    only_need_context: bool | None = None,
    only_need_prompt: bool | None = None,
    response_type: str | None = None,
    top_k: int | None = None,
    chunk_top_k: int | None = None,
    max_entity_tokens: int | None = None,
    max_relation_tokens: int | None = None,
    max_total_tokens: int | None = None,
    hl_keywords: list[str] | None = None,
    ll_keywords: list[str] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    user_prompt: str | None = None,
    enable_rerank: bool | None = None,
    include_references: bool | None = True,
    include_chunk_content: bool | None = False,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Run a LightRAG query and return response + references."""
    rag = await _get_rag()
    param = _build_query_param(
        mode=mode,
        only_need_context=only_need_context,
        only_need_prompt=only_need_prompt,
        response_type=response_type,
        top_k=top_k,
        chunk_top_k=chunk_top_k,
        max_entity_tokens=max_entity_tokens,
        max_relation_tokens=max_relation_tokens,
        max_total_tokens=max_total_tokens,
        hl_keywords=hl_keywords,
        ll_keywords=ll_keywords,
        conversation_history=conversation_history,
        user_prompt=user_prompt,
        enable_rerank=enable_rerank,
        include_references=include_references,
    )

    result = await rag.aquery_llm(query, param=param, system_prompt=system_prompt)
    llm_response = result.get("llm_response", {})
    data = result.get("data", {})
    response_content = llm_response.get("content", "") or "No relevant context found."
    references = data.get("references", [])

    if include_references and include_chunk_content:
        chunks = data.get("chunks", [])
        ref_id_to_content: dict[str, list[str]] = {}
        for chunk in chunks:
            ref_id = chunk.get("reference_id", "")
            content = chunk.get("content", "")
            if ref_id and content:
                ref_id_to_content.setdefault(ref_id, []).append(content)

        enriched_references = []
        for ref in references:
            ref_copy = dict(ref)
            ref_id = ref.get("reference_id", "")
            if ref_id in ref_id_to_content:
                ref_copy["content"] = ref_id_to_content[ref_id]
            enriched_references.append(ref_copy)
        references = enriched_references

    if include_references:
        return {"response": response_content, "references": references}
    return {"response": response_content, "references": None}


@mcp.tool()
async def rag_query_data(
    query: str,
    mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = "mix",
    top_k: int | None = None,
    chunk_top_k: int | None = None,
    max_entity_tokens: int | None = None,
    max_relation_tokens: int | None = None,
    max_total_tokens: int | None = None,
    hl_keywords: list[str] | None = None,
    ll_keywords: list[str] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    user_prompt: str | None = None,
    enable_rerank: bool | None = None,
) -> dict[str, Any]:
    """Return structured retrieval data without LLM response."""
    rag = await _get_rag()
    param = _build_query_param(
        mode=mode,
        only_need_context=False,
        only_need_prompt=False,
        response_type=None,
        top_k=top_k,
        chunk_top_k=chunk_top_k,
        max_entity_tokens=max_entity_tokens,
        max_relation_tokens=max_relation_tokens,
        max_total_tokens=max_total_tokens,
        hl_keywords=hl_keywords,
        ll_keywords=ll_keywords,
        conversation_history=conversation_history,
        user_prompt=user_prompt,
        enable_rerank=enable_rerank,
        include_references=True,
    )
    return await rag.aquery_data(query, param=param)


def _run_mcp() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        mount_path = os.getenv("MCP_MOUNT_PATH")
        mcp.run(transport="sse", mount_path=mount_path)
        return
    else:
        mcp.run()


if __name__ == "__main__":
    _run_mcp()
