#!/usr/bin/env python3
"""
Re-embed PostgreSQL vector tables into a new embedding model.

This keeps all non-vector data intact and repopulates vector tables for the
target embedding model (table suffix changes with model name).

Example:
  python -m lightrag.tools.reembed_postgres_vectors \\
    --workspace v3 \\
    --source-model text-embedding-3-large \\
    --source-dim 3072 \\
    --target-model text-embedding-3-small \\
    --target-dim 1536
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable

from dotenv import load_dotenv

from lightrag.namespace import NameSpace
from lightrag.utils import EmbeddingFunc, logger


@dataclass
class ReembedStats:
    name: str
    total: int = 0
    processed: int = 0
    skipped: int = 0

    def log(self) -> None:
        logger.info(
            "Re-embed %s: total=%s processed=%s skipped=%s",
            self.name,
            self.total,
            self.processed,
            self.skipped,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-embed PostgreSQL vector tables into a new embedding model",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Target workspace (defaults to POSTGRES_WORKSPACE or WORKSPACE)",
    )
    parser.add_argument(
        "--source-model",
        default=os.environ.get("SOURCE_EMBEDDING_MODEL"),
        help="Source embedding model (table suffix) to read from",
    )
    parser.add_argument(
        "--source-dim",
        type=int,
        default=(
            int(os.environ["SOURCE_EMBEDDING_DIM"])
            if os.environ.get("SOURCE_EMBEDDING_DIM")
            else None
        ),
        help="Source embedding dimension",
    )
    parser.add_argument(
        "--target-model",
        default=os.environ.get("EMBEDDING_MODEL"),
        help="Target embedding model name",
    )
    parser.add_argument(
        "--target-dim",
        type=int,
        default=(
            int(os.environ["EMBEDDING_DIM"]) if os.environ.get("EMBEDDING_DIM") else None
        ),
        help="Target embedding dimension",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size per upsert call",
    )
    parser.add_argument("--skip-chunks", action="store_true", help="Skip chunks")
    parser.add_argument("--skip-entities", action="store_true", help="Skip entities")
    parser.add_argument("--skip-relations", action="store_true", help="Skip relations")
    return parser.parse_args()


def _build_embedding_func(
    binding: str,
    model: str | None,
    embedding_dim: int,
    host: str | None,
    api_key: str | None,
    embedding_send_dim: bool,
    embedding_token_limit: int | None,
) -> EmbeddingFunc:
    async def _embed(texts: list[str], embedding_dim: int | None = None):
        if binding == "gemini":
            from lightrag.llm.gemini import gemini_embed

            actual_func = (
                gemini_embed.func
                if isinstance(gemini_embed, EmbeddingFunc)
                else gemini_embed
            )
            kwargs = {
                "texts": texts,
                "base_url": host,
                "api_key": api_key,
                "embedding_dim": embedding_dim,
                "task_type": "RETRIEVAL_DOCUMENT",
            }
            if model:
                kwargs["model"] = model
            return await actual_func(**kwargs)

        from lightrag.llm.openai import openai_embed

        actual_func = (
            openai_embed.func
            if isinstance(openai_embed, EmbeddingFunc)
            else openai_embed
        )
        kwargs = {
            "texts": texts,
            "base_url": host,
            "api_key": api_key,
            "embedding_dim": embedding_dim,
        }
        if model:
            kwargs["model"] = model
        return await actual_func(**kwargs)

    embedding_func = EmbeddingFunc(
        embedding_dim=embedding_dim,
        func=_embed,
        max_token_size=embedding_token_limit,
        send_dimensions=False,
        model_name=model,
    )

    if binding in ("gemini", "jina"):
        embedding_func.send_dimensions = True
    else:
        embedding_func.send_dimensions = embedding_send_dim

    return embedding_func


async def _count_rows(db, table_name: str, workspace: str) -> int:
    sql = f"SELECT COUNT(*) AS count FROM {table_name} WHERE workspace=$1"
    res = await db.query(sql, [workspace])
    return int(res["count"]) if res else 0


async def _fetch_rows(
    db,
    table_name: str,
    columns: list[str],
    workspace: str,
    batch_size: int,
) -> Iterable[list[dict[str, Any]]]:
    last_id: str | None = None
    column_list = ", ".join(columns)
    while True:
        if last_id is None:
            sql = (
                f"SELECT {column_list} FROM {table_name} "
                "WHERE workspace=$1 ORDER BY id LIMIT $2"
            )
            params = [workspace, batch_size]
        else:
            sql = (
                f"SELECT {column_list} FROM {table_name} "
                "WHERE workspace=$1 AND id > $2 ORDER BY id LIMIT $3"
            )
            params = [workspace, last_id, batch_size]
        rows = await db.query(sql, params, multirows=True)
        if not rows:
            break
        last_id = rows[-1]["id"]
        yield rows


def _chunk_ids_to_source_id(chunk_ids: Any) -> str:
    if not chunk_ids:
        return ""
    if isinstance(chunk_ids, (list, tuple)):
        return "<SEP>".join(str(c) for c in chunk_ids if c)
    return str(chunk_ids)


async def _reembed_chunks(
    db,
    table_name: str,
    storage,
    workspace: str,
    batch_size: int,
) -> None:
    stats = ReembedStats(name="chunks")
    stats.total = await _count_rows(db, table_name, workspace)

    async for rows in _fetch_rows(
        db,
        table_name,
        ["id", "full_doc_id", "chunk_order_index", "tokens", "content", "file_path"],
        workspace,
        batch_size,
    ):
        batch: dict[str, dict[str, Any]] = {}
        for row in rows:
            content = row.get("content")
            if not content:
                stats.skipped += 1
                continue
            batch[row["id"]] = {
                "full_doc_id": row.get("full_doc_id"),
                "chunk_order_index": row.get("chunk_order_index"),
                "tokens": row.get("tokens"),
                "content": content,
                "file_path": row.get("file_path"),
            }
        if batch:
            await storage.upsert(batch)
            stats.processed += len(batch)
            logger.info("Re-embed chunks progress: %s/%s", stats.processed, stats.total)

    stats.log()


async def _reembed_entities(
    db,
    table_name: str,
    storage,
    workspace: str,
    batch_size: int,
) -> None:
    stats = ReembedStats(name="entities")
    stats.total = await _count_rows(db, table_name, workspace)

    async for rows in _fetch_rows(
        db,
        table_name,
        ["id", "entity_name", "content", "chunk_ids", "file_path"],
        workspace,
        batch_size,
    ):
        batch: dict[str, dict[str, Any]] = {}
        for row in rows:
            content = row.get("content")
            if not content:
                stats.skipped += 1
                continue
            batch[row["id"]] = {
                "entity_name": row.get("entity_name"),
                "content": content,
                "source_id": _chunk_ids_to_source_id(row.get("chunk_ids")),
                "file_path": row.get("file_path"),
            }
        if batch:
            await storage.upsert(batch)
            stats.processed += len(batch)
            logger.info(
                "Re-embed entities progress: %s/%s", stats.processed, stats.total
            )

    stats.log()


async def _reembed_relations(
    db,
    table_name: str,
    storage,
    workspace: str,
    batch_size: int,
) -> None:
    stats = ReembedStats(name="relations")
    stats.total = await _count_rows(db, table_name, workspace)

    async for rows in _fetch_rows(
        db,
        table_name,
        ["id", "source_id", "target_id", "content", "chunk_ids", "file_path"],
        workspace,
        batch_size,
    ):
        batch: dict[str, dict[str, Any]] = {}
        for row in rows:
            content = row.get("content")
            if not content:
                stats.skipped += 1
                continue
            batch[row["id"]] = {
                "src_id": row.get("source_id"),
                "tgt_id": row.get("target_id"),
                "content": content,
                "source_id": _chunk_ids_to_source_id(row.get("chunk_ids")),
                "file_path": row.get("file_path"),
            }
        if batch:
            await storage.upsert(batch)
            stats.processed += len(batch)
            logger.info(
                "Re-embed relations progress: %s/%s", stats.processed, stats.total
            )

    stats.log()


async def _run() -> int:
    args = _parse_args()
    load_dotenv(dotenv_path=".env", override=False)

    from lightrag.kg.shared_storage import initialize_share_data
    from lightrag.kg.postgres_impl import ClientManager, PGVectorStorage

    initialize_share_data()

    source_model = args.source_model
    source_dim = args.source_dim
    target_model = args.target_model
    target_dim = args.target_dim

    if not source_model or not source_dim:
        logger.error("source-model and source-dim are required")
        return 2
    if not target_model or not target_dim:
        logger.error("target-model and target-dim are required")
        return 2

    workspace = args.workspace or os.environ.get("POSTGRES_WORKSPACE") or os.environ.get(
        "WORKSPACE"
    )
    if not workspace:
        workspace = "default"

    embedding_binding = os.environ.get("EMBEDDING_BINDING", "openai")
    embedding_host = os.environ.get("EMBEDDING_BINDING_HOST")
    embedding_api_key = os.environ.get("EMBEDDING_BINDING_API_KEY")
    embedding_send_dim = (
        os.environ.get("EMBEDDING_SEND_DIM", "false").lower() == "true"
    )
    embedding_token_limit = (
        int(os.environ["EMBEDDING_TOKEN_LIMIT"])
        if os.environ.get("EMBEDDING_TOKEN_LIMIT")
        else None
    )

    target_embedding_func = _build_embedding_func(
        binding=embedding_binding,
        model=target_model,
        embedding_dim=target_dim,
        host=embedding_host,
        api_key=embedding_api_key,
        embedding_send_dim=embedding_send_dim,
        embedding_token_limit=embedding_token_limit,
    )

    global_config = {
        "embedding_batch_num": int(os.environ.get("EMBEDDING_BATCH_NUM", "16")),
        "vector_db_storage_cls_kwargs": {
            "cosine_better_than_threshold": float(
                os.environ.get("COSINE_THRESHOLD", "0.2")
            )
        },
        "working_dir": os.environ.get("WORKING_DIR", "./data/rag_storage"),
    }

    db = await ClientManager.get_client()

    source_embedding = EmbeddingFunc(
        embedding_dim=source_dim,
        func=lambda *_args, **_kwargs: None,
        model_name=source_model,
    )

    source_chunks = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_CHUNKS,
        workspace=workspace,
        global_config=global_config,
        embedding_func=source_embedding,
        db=db,
    )
    source_entities = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_ENTITIES,
        workspace=workspace,
        global_config=global_config,
        embedding_func=source_embedding,
        db=db,
    )
    source_relations = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_RELATIONSHIPS,
        workspace=workspace,
        global_config=global_config,
        embedding_func=source_embedding,
        db=db,
    )

    target_chunks = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_CHUNKS,
        workspace=workspace,
        global_config=global_config,
        embedding_func=target_embedding_func,
        db=db,
    )
    target_entities = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_ENTITIES,
        workspace=workspace,
        global_config=global_config,
        embedding_func=target_embedding_func,
        db=db,
    )
    target_relations = PGVectorStorage(
        namespace=NameSpace.VECTOR_STORE_RELATIONSHIPS,
        workspace=workspace,
        global_config=global_config,
        embedding_func=target_embedding_func,
        db=db,
    )

    await target_chunks.initialize()
    await target_entities.initialize()
    await target_relations.initialize()

    if not args.skip_chunks:
        await _reembed_chunks(
            db, source_chunks.table_name, target_chunks, workspace, args.batch_size
        )
    if not args.skip_entities:
        await _reembed_entities(
            db, source_entities.table_name, target_entities, workspace, args.batch_size
        )
    if not args.skip_relations:
        await _reembed_relations(
            db,
            source_relations.table_name,
            target_relations,
            workspace,
            args.batch_size,
        )

    await ClientManager.release_client(db)
    return 0


def main() -> int:
    start = time.time()
    try:
        return asyncio.run(_run())
    finally:
        logger.info("Re-embedding finished in %.2fs", time.time() - start)


if __name__ == "__main__":
    sys.exit(main())
