#!/usr/bin/env python3
"""
Migrate rag_storage/v2 JSON + GraphML + NanoVectorDB files to Postgres storages.

This keeps existing vectors (no re-embedding).

Usage:
  python -m lightrag.tools.migrate_rag_storage_to_postgres --source-dir data/rag_storage/v2 --workspace v2
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime
import json
import os
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pipmaster as pm
from dotenv import load_dotenv

from lightrag.namespace import NameSpace
from lightrag.utils import EmbeddingFunc, logger


@dataclass
class MigrationStats:
    name: str
    total: int = 0
    inserted: int = 0
    skipped: int = 0

    def log(self):
        logger.info(
            "Migration %s: total=%s inserted=%s skipped=%s",
            self.name,
            self.total,
            self.inserted,
            self.skipped,
        )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed for %s (%s); retrying with streaming decode", path, exc)
        content = path.read_text(encoding="utf-8")
        decoder = json.JSONDecoder()
        idx = 0
        parsed_objects = 0
        last_obj: dict[str, Any] | None = None

        while idx < len(content):
            while idx < len(content) and content[idx].isspace():
                idx += 1
            if idx >= len(content):
                break
            try:
                obj, end = decoder.raw_decode(content, idx)
            except json.JSONDecodeError as inner_exc:
                if last_obj is not None:
                    logger.warning(
                        "Trailing JSON data ignored for %s (%s)",
                        path,
                        inner_exc,
                    )
                    break
                raise
            parsed_objects += 1
            if isinstance(obj, dict):
                last_obj = obj
            else:
                logger.warning(
                    "Unexpected JSON root type in %s: %s",
                    path,
                    type(obj).__name__,
                )
                last_obj = None
            idx = end

        if last_obj is None:
            raise exc
        if parsed_objects > 1:
            logger.warning(
                "Multiple JSON objects found in %s; using last (%s parsed)",
                path,
                parsed_objects,
            )
        return last_obj


def _batch_dict_items(
    data: dict[str, Any], batch_size: int
) -> Iterable[dict[str, Any]]:
    batch: dict[str, Any] = {}
    for key, value in data.items():
        batch[key] = value
        if len(batch) >= batch_size:
            yield batch
            batch = {}
    if batch:
        yield batch


def _decode_vector(encoded: Any, embedding_dim: int, record_id: str) -> np.ndarray | None:
    if encoded is None:
        return None
    if isinstance(encoded, (list, tuple, np.ndarray)):
        vec = np.array(encoded, dtype=np.float32)
    elif isinstance(encoded, str):
        try:
            compressed = base64.b64decode(encoded)
            raw = zlib.decompress(compressed)
            vec = np.frombuffer(raw, dtype=np.float16).astype(np.float32)
        except Exception as exc:
            logger.warning("Failed to decode vector for %s: %s", record_id, exc)
            return None
    else:
        logger.warning("Unsupported vector type for %s: %s", record_id, type(encoded))
        return None

    if embedding_dim and len(vec) != embedding_dim:
        logger.warning(
            "Vector dim mismatch for %s: got %s expected %s",
            record_id,
            len(vec),
            embedding_dim,
        )
        return None
    return vec


async def _migrate_kv_storage(storage, name: str, data: dict[str, Any], batch_size: int):
    stats = MigrationStats(name=name, total=len(data))
    for batch in _batch_dict_items(data, batch_size):
        await storage.upsert(batch)
        stats.inserted += len(batch)
    stats.log()


async def _migrate_doc_status(storage, data: dict[str, Any]):
    stats = MigrationStats(name="doc_status", total=len(data))
    await storage.upsert(data)
    stats.inserted = len(data)
    stats.log()


async def _migrate_graph(storage, graphml_path: Path):
    if not pm.is_installed("networkx"):
        pm.install("networkx")
    import networkx as nx  # type: ignore

    stats_nodes = MigrationStats(name="graph_nodes")
    stats_edges = MigrationStats(name="graph_edges")

    graph = nx.read_graphml(graphml_path)
    stats_nodes.total = graph.number_of_nodes()
    stats_edges.total = graph.number_of_edges()

    for node_id, node_data in graph.nodes(data=True):
        node_props = dict(node_data)
        node_props.setdefault("entity_id", node_id)
        await storage.upsert_node(node_id, node_props)
        stats_nodes.inserted += 1

    for src_id, tgt_id, edge_data in graph.edges(data=True):
        edge_props = dict(edge_data)
        await storage.upsert_edge(src_id, tgt_id, edge_props)
        stats_edges.inserted += 1

    stats_nodes.log()
    stats_edges.log()


async def _batch_vector_upsert(db, upsert_sql: str, batch_values: list[tuple[Any, ...]]):
    async def _batch_insert(connection):
        await connection.executemany(upsert_sql, batch_values)

    await db._run_with_retry(_batch_insert)


async def _migrate_vectors_chunks(
    vector_storage,
    vdb_data: dict[str, Any],
    text_chunks: dict[str, Any],
    embedding_dim: int,
    batch_size: int,
):
    stats = MigrationStats(name="vectors_chunks")
    upsert_sql = None
    batch_values: list[tuple[Any, ...]] = []
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    for record in vdb_data.get("data", []):
        stats.total += 1
        record_id = record.get("__id__")
        if not record_id:
            stats.skipped += 1
            continue

        vec = _decode_vector(record.get("vector"), embedding_dim, record_id)
        if vec is None:
            stats.skipped += 1
            continue

        chunk_meta = text_chunks.get(record_id, {})
        item = {
            "__id__": record_id,
            "tokens": chunk_meta.get("tokens"),
            "chunk_order_index": chunk_meta.get("chunk_order_index"),
            "full_doc_id": record.get("full_doc_id"),
            "content": record.get("content"),
            "file_path": record.get("file_path") or chunk_meta.get("file_path"),
            "__vector__": vec,
        }
        upsert_sql, values = vector_storage._upsert_chunks(item, current_time)
        batch_values.append(values)
        if len(batch_values) >= batch_size:
            await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
            stats.inserted += len(batch_values)
            batch_values = []

    if batch_values and upsert_sql:
        await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
        stats.inserted += len(batch_values)

    stats.log()


async def _migrate_vectors_entities(
    vector_storage,
    vdb_data: dict[str, Any],
    embedding_dim: int,
    batch_size: int,
):
    stats = MigrationStats(name="vectors_entities")
    upsert_sql = None
    batch_values: list[tuple[Any, ...]] = []
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    for record in vdb_data.get("data", []):
        stats.total += 1
        record_id = record.get("__id__")
        if not record_id:
            stats.skipped += 1
            continue

        vec = _decode_vector(record.get("vector"), embedding_dim, record_id)
        if vec is None:
            stats.skipped += 1
            continue

        item = {
            "__id__": record_id,
            "entity_name": record.get("entity_name"),
            "content": record.get("content"),
            "source_id": record.get("source_id", ""),
            "file_path": record.get("file_path"),
            "__vector__": vec,
        }
        upsert_sql, values = vector_storage._upsert_entities(item, current_time)
        batch_values.append(values)
        if len(batch_values) >= batch_size:
            await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
            stats.inserted += len(batch_values)
            batch_values = []

    if batch_values and upsert_sql:
        await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
        stats.inserted += len(batch_values)

    stats.log()


async def _migrate_vectors_relationships(
    vector_storage,
    vdb_data: dict[str, Any],
    embedding_dim: int,
    batch_size: int,
):
    stats = MigrationStats(name="vectors_relationships")
    upsert_sql = None
    batch_values: list[tuple[Any, ...]] = []
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    for record in vdb_data.get("data", []):
        stats.total += 1
        record_id = record.get("__id__")
        if not record_id:
            stats.skipped += 1
            continue

        vec = _decode_vector(record.get("vector"), embedding_dim, record_id)
        if vec is None:
            stats.skipped += 1
            continue

        src_id = record.get("src_id")
        tgt_id = record.get("tgt_id")
        content = record.get("content")
        if not content:
            keywords = record.get("keywords") or ""
            description = record.get("description") or ""
            content = f"{keywords}\t{src_id}\n{tgt_id}\n{description}"

        item = {
            "__id__": record_id,
            "src_id": src_id,
            "tgt_id": tgt_id,
            "content": content,
            "source_id": record.get("source_id", ""),
            "file_path": record.get("file_path"),
            "__vector__": vec,
        }
        upsert_sql, values = vector_storage._upsert_relationships(item, current_time)
        batch_values.append(values)
        if len(batch_values) >= batch_size:
            await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
            stats.inserted += len(batch_values)
            batch_values = []

    if batch_values and upsert_sql:
        await _batch_vector_upsert(vector_storage.db, upsert_sql, batch_values)
        stats.inserted += len(batch_values)

    stats.log()


def _build_dummy_embedding_func(embedding_dim: int, model_name: str | None):
    async def _noop_embed(*_args, **_kwargs):
        raise RuntimeError("embedding function should not be called during migration")

    return EmbeddingFunc(
        embedding_dim=embedding_dim,
        func=_noop_embed,
        model_name=model_name,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate rag_storage/v2 files into PostgreSQL storages",
    )
    parser.add_argument(
        "--source-dir",
        default="data/rag_storage/v2",
        help="Directory containing kv_store_*.json, vdb_*.json, graph_*.graphml",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Target workspace in Postgres (sets POSTGRES_WORKSPACE)",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.environ.get("EMBEDDING_MODEL"),
        help="Embedding model name for vector table suffix",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=None,
        help="Embedding dimension (must match vdb files)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for vector inserts",
    )
    parser.add_argument("--skip-kv", action="store_true", help="Skip KV storages")
    parser.add_argument(
        "--skip-doc-status", action="store_true", help="Skip doc_status storage"
    )
    parser.add_argument("--skip-vectors", action="store_true", help="Skip vectors")
    parser.add_argument("--skip-graph", action="store_true", help="Skip graph")
    return parser.parse_args()


async def _run_migration():
    args = _parse_args()
    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        logger.error("Source dir not found: %s", source_dir)
        return 2

    if args.workspace:
        os.environ["POSTGRES_WORKSPACE"] = args.workspace

    load_dotenv(dotenv_path=".env", override=False)

    from lightrag.kg.shared_storage import initialize_share_data
    from lightrag.kg.postgres_impl import (
        ClientManager,
        PGDocStatusStorage,
        PGGraphStorage,
        PGKVStorage,
        PGVectorStorage,
    )

    initialize_share_data()

    vdb_chunks_path = source_dir / "vdb_chunks.json"
    vdb_entities_path = source_dir / "vdb_entities.json"
    vdb_relationships_path = source_dir / "vdb_relationships.json"
    graph_path = source_dir / "graph_chunk_entity_relation.graphml"

    embedding_dim = args.embedding_dim
    if not args.skip_vectors:
        vdb_chunks_data = _load_json(vdb_chunks_path)
        vdb_entities_data = _load_json(vdb_entities_path)
        vdb_relationships_data = _load_json(vdb_relationships_path)
        file_dim = vdb_chunks_data.get("embedding_dim")
        if embedding_dim is None:
            embedding_dim = file_dim
        if embedding_dim != file_dim:
            logger.error(
                "Embedding dim mismatch: file=%s arg=%s", file_dim, embedding_dim
            )
            return 2
        if embedding_dim is None:
            logger.error("Embedding dimension is required for vector migration")
            return 2
    else:
        vdb_chunks_data = vdb_entities_data = vdb_relationships_data = {}
        if embedding_dim is None:
            env_dim = os.environ.get("EMBEDDING_DIM")
            if env_dim:
                embedding_dim = int(env_dim)
            else:
                embedding_dim = 1
                logger.warning(
                    "Embedding dim not provided; using %s for non-vector migration",
                    embedding_dim,
                )

    embedding_model = args.embedding_model
    if not embedding_model:
        logger.warning(
            "Embedding model name is missing; vector tables will not use model suffix"
        )

    workspace = os.environ.get("POSTGRES_WORKSPACE") or os.environ.get("WORKSPACE")
    if not workspace:
        workspace = "default"

    global_config = {
        "embedding_batch_num": int(os.environ.get("EMBEDDING_BATCH_NUM", "16")),
        "vector_db_storage_cls_kwargs": {
            "cosine_better_than_threshold": float(
                os.environ.get("COSINE_THRESHOLD", "0.2")
            )
        },
        "working_dir": os.environ.get("WORKING_DIR", str(source_dir)),
    }

    dummy_embedding = _build_dummy_embedding_func(embedding_dim, embedding_model)

    db = await ClientManager.get_client()

    if not args.skip_kv:
        kv_full_docs = PGKVStorage(
            namespace=NameSpace.KV_STORE_FULL_DOCS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_text_chunks = PGKVStorage(
            namespace=NameSpace.KV_STORE_TEXT_CHUNKS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_full_entities = PGKVStorage(
            namespace=NameSpace.KV_STORE_FULL_ENTITIES,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_full_relations = PGKVStorage(
            namespace=NameSpace.KV_STORE_FULL_RELATIONS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_entity_chunks = PGKVStorage(
            namespace=NameSpace.KV_STORE_ENTITY_CHUNKS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_relation_chunks = PGKVStorage(
            namespace=NameSpace.KV_STORE_RELATION_CHUNKS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        kv_llm_cache = PGKVStorage(
            namespace=NameSpace.KV_STORE_LLM_RESPONSE_CACHE,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )

        full_docs = _load_json(source_dir / "kv_store_full_docs.json")
        text_chunks = _load_json(source_dir / "kv_store_text_chunks.json")
        full_entities = _load_json(source_dir / "kv_store_full_entities.json")
        full_relations = _load_json(source_dir / "kv_store_full_relations.json")
        entity_chunks = _load_json(source_dir / "kv_store_entity_chunks.json")
        relation_chunks = _load_json(source_dir / "kv_store_relation_chunks.json")
        llm_cache = _load_json(source_dir / "kv_store_llm_response_cache.json")

        await _migrate_kv_storage(kv_full_docs, "full_docs", full_docs, args.batch_size)
        await _migrate_kv_storage(
            kv_text_chunks, "text_chunks", text_chunks, args.batch_size
        )
        await _migrate_kv_storage(
            kv_full_entities, "full_entities", full_entities, args.batch_size
        )
        await _migrate_kv_storage(
            kv_full_relations, "full_relations", full_relations, args.batch_size
        )
        await _migrate_kv_storage(
            kv_entity_chunks, "entity_chunks", entity_chunks, args.batch_size
        )
        await _migrate_kv_storage(
            kv_relation_chunks, "relation_chunks", relation_chunks, args.batch_size
        )
        await _migrate_kv_storage(kv_llm_cache, "llm_cache", llm_cache, args.batch_size)
    else:
        text_chunks = _load_json(source_dir / "kv_store_text_chunks.json")

    if not args.skip_doc_status:
        doc_status_storage = PGDocStatusStorage(
            namespace=NameSpace.DOC_STATUS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
        )
        await doc_status_storage.initialize()
        doc_status_data = _load_json(source_dir / "kv_store_doc_status.json")
        await _migrate_doc_status(doc_status_storage, doc_status_data)

    if not args.skip_vectors:
        vectors_chunks = PGVectorStorage(
            namespace=NameSpace.VECTOR_STORE_CHUNKS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        vectors_entities = PGVectorStorage(
            namespace=NameSpace.VECTOR_STORE_ENTITIES,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )
        vectors_relationships = PGVectorStorage(
            namespace=NameSpace.VECTOR_STORE_RELATIONSHIPS,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
            db=db,
        )

        await vectors_chunks.initialize()
        await vectors_entities.initialize()
        await vectors_relationships.initialize()

        await _migrate_vectors_chunks(
            vectors_chunks,
            vdb_chunks_data,
            text_chunks,
            embedding_dim,
            args.batch_size,
        )
        await _migrate_vectors_entities(
            vectors_entities,
            vdb_entities_data,
            embedding_dim,
            args.batch_size,
        )
        await _migrate_vectors_relationships(
            vectors_relationships,
            vdb_relationships_data,
            embedding_dim,
            args.batch_size,
        )

    if not args.skip_graph:
        graph_storage = PGGraphStorage(
            namespace=NameSpace.GRAPH_STORE_CHUNK_ENTITY_RELATION,
            workspace=workspace,
            global_config=global_config,
            embedding_func=dummy_embedding,
        )
        await graph_storage.initialize()
        await _migrate_graph(graph_storage, graph_path)

    await ClientManager.release_client(db)
    return 0


def main() -> int:
    start = time.time()
    try:
        return asyncio.run(_run_migration())
    finally:
        logger.info("Migration finished in %.2fs", time.time() - start)


if __name__ == "__main__":
    sys.exit(main())
