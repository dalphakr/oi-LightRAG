from __future__ import annotations

import json
import time
from typing import Any, Mapping

from lightrag.prompt import PROMPTS


def _normalize_timestamp(value: Any) -> Any:
    """Convert numeric timestamps to readable strings; leave others as-is."""
    if isinstance(value, (int, float)):
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))
        except (OverflowError, ValueError):
            return value
    return value


def _as_context_entity(entity: Mapping[str, Any]) -> dict[str, Any]:
    """Shape an entity record into the form used inside the LLM context block."""
    return {
        "entity": entity.get("entity_name", ""),
        "type": entity.get("entity_type", "UNKNOWN"),
        "description": entity.get("description", ""),
        "created_at": _normalize_timestamp(entity.get("created_at", "")),
        "file_path": entity.get("file_path", "unknown_source"),
    }


def _as_context_relation(relation: Mapping[str, Any]) -> dict[str, Any]:
    """Shape a relationship record into the form used inside the LLM context block."""
    return {
        "entity1": relation.get("src_id", ""),
        "entity2": relation.get("tgt_id", ""),
        "description": relation.get("description", ""),
        "created_at": _normalize_timestamp(relation.get("created_at", "")),
        "file_path": relation.get("file_path", "unknown_source"),
    }


def _as_context_chunk(chunk: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only fields the prompt template expects for chunks."""
    return {
        "reference_id": str(chunk.get("reference_id", "")).strip(),
        "content": chunk.get("content", ""),
    }


def _render_reference_list(
    references: list[Mapping[str, Any]], chunks: list[Mapping[str, Any]]
) -> str:
    """
    Render the Reference Document List section.

    If references are missing, fall back to unique (reference_id, file_path) pairs from chunks.
    """
    ref_entries: list[tuple[str, str]] = []

    for ref in references or []:
        ref_id = str(ref.get("reference_id", "")).strip()
        file_path = ref.get("file_path", "")
        if ref_id:
            ref_entries.append((ref_id, file_path))

    if not ref_entries:
        seen_ids = set()
        for chunk in chunks or []:
            ref_id = str(chunk.get("reference_id", "")).strip()
            file_path = chunk.get("file_path", "")
            if ref_id and ref_id not in seen_ids:
                seen_ids.add(ref_id)
                ref_entries.append((ref_id, file_path))

    return "\n".join(f"[{ref_id}] {file_path}" for ref_id, file_path in ref_entries if ref_id)


def build_context_from_retrieval(payload: Mapping[str, Any]) -> str:
    """
    Build the LLM-ready context block from a retrieval result.

    Supports two shapes:
    - Full API response: {"status": "...", "data": {"entities": [...], "relationships": [...], "chunks": [...], "references": [...]} }
    - Raw data dict: {"entities": [...], "relationships": [...], "chunks": [...], "references": [...]}
    """
    data_section = payload.get("data", payload)
    entities = [_as_context_entity(e) for e in data_section.get("entities", [])]
    relationships = [
        _as_context_relation(r) for r in data_section.get("relationships", [])
    ]
    chunks = [_as_context_chunk(c) for c in data_section.get("chunks", [])]
    references = data_section.get("references", []) or []

    # Pick template: use KG template when we have any graph signals, otherwise the naive one.
    has_graph = bool(entities or relationships)
    template_key = "kg_query_context" if has_graph else "naive_query_context"
    template = PROMPTS[template_key]

    entities_str = "\n".join(json.dumps(entity, ensure_ascii=False) for entity in entities)
    relations_str = "\n".join(
        json.dumps(relation, ensure_ascii=False) for relation in relationships
    )
    text_chunks_str = "\n".join(
        json.dumps(chunk, ensure_ascii=False)
        for chunk in chunks
        if chunk.get("content", "")
    )
    reference_list_str = _render_reference_list(references, chunks)

    return template.format(
        entities_str=entities_str,
        relations_str=relations_str,
        text_chunks_str=text_chunks_str,
        reference_list_str=reference_list_str,
    )


def build_prompt_from_retrieval(
    payload: Mapping[str, Any],
    user_query: str,
    *,
    response_type: str = "Multiple Paragraphs",
    user_prompt: str = "",
) -> str:
    """
    Build the full LLM prompt (system + user) from a retrieval result.

    Mirrors the behavior of only_need_prompt=True in the API layer.
    """
    context_block = build_context_from_retrieval(payload)
    has_graph = any(payload.get("data", payload).get(k) for k in ("entities", "relationships"))
    system_template_key = "rag_response" if has_graph else "naive_rag_response"
    system_template = PROMPTS[system_template_key]

    system_prompt = system_template.format(
        response_type=response_type,
        user_prompt=f"\n\n{user_prompt}" if user_prompt else "n/a",
        context_data=context_block,
    )

    return "\n\n".join([system_prompt, "---User Query---", user_query])
