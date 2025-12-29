#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import os
import sys
import time
from functools import partial
from typing import Any

from lightrag.api import config as api_config
from lightrag.api.config import get_default_host
from lightrag.constants import DEFAULT_LLM_TIMEOUT
from lightrag.llm.binding_options import (
    GeminiLLMOptions,
    OllamaLLMOptions,
    OpenAILLMOptions,
)
from lightrag.llm.gemini import gemini_complete_if_cache
from lightrag.llm.lollms import lollms_model_if_cache
from lightrag.llm.ollama import _ollama_model_if_cache
from lightrag.llm.openai import (
    azure_openai_complete_if_cache,
    openai_complete_if_cache,
)
from lightrag.utils import use_llm_func_with_cache


def _load_env_config() -> argparse.Namespace:
    saved_argv = sys.argv[:]
    sys.argv = [saved_argv[0]]
    try:
        return api_config.get_config()
    finally:
        sys.argv = saved_argv


def _read_text_arg(value: str | None, path: str | None) -> str:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    if value is not None:
        return value
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ValueError("Missing prompt input. Use --prompt, --prompt-file, or stdin.")


def _read_json_arg(value: str | None, path: str | None) -> Any | None:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    if value is None:
        return None
    return json.loads(value)


def _filter_options(options: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in options.items():
        if value is None:
            continue
        if value == [] or value == {}:
            continue
        cleaned[key] = value
    return cleaned


def _build_llm_func(
    binding: str,
    model: str,
    host: str | None,
    api_key: str | None,
    timeout: int | None,
    config_args: argparse.Namespace,
):
    if binding in ["openai", "azure_openai"]:
        openai_options = _filter_options(OpenAILLMOptions.options_dict(config_args))
        if binding == "azure_openai":
            return partial(
                azure_openai_complete_if_cache,
                model=model,
                base_url=host,
                api_key=api_key,
                timeout=timeout,
                **openai_options,
            )
        return partial(
            openai_complete_if_cache,
            model=model,
            base_url=host,
            api_key=api_key,
            timeout=timeout,
            **openai_options,
        )

    if binding == "gemini":
        gemini_options = _filter_options(GeminiLLMOptions.options_dict(config_args))
        generation_config = gemini_options or None
        return partial(
            gemini_complete_if_cache,
            model=model,
            base_url=host,
            api_key=api_key,
            timeout=timeout,
            generation_config=generation_config,
        )

    if binding == "ollama":
        ollama_options = _filter_options(OllamaLLMOptions.options_dict(config_args))
        return partial(
            _ollama_model_if_cache,
            model=model,
            host=host,
            api_key=api_key,
            timeout=timeout,
            options=ollama_options or {},
        )

    if binding == "lollms":
        return partial(
            lollms_model_if_cache,
            model,
            base_url=host or "http://localhost:9600",
        )

    raise ValueError(f"Unsupported LLM binding: {binding}")


async def _run_once(
    use_llm_func,
    prompt: str,
    system_prompt: str | None,
    history_messages: list[dict[str, Any]] | None,
    max_tokens: int | None,
) -> tuple[str, int]:
    start = time.monotonic()
    output, _ = await use_llm_func_with_cache(
        prompt,
        use_llm_func,
        llm_response_cache=None,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        history_messages=history_messages,
        cache_type="test_llm",
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    return output, duration_ms


def _run_once_sync(
    use_llm_func,
    prompt: str,
    system_prompt: str | None,
    history_messages: list[dict[str, Any]] | None,
    max_tokens: int | None,
) -> tuple[str, int]:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _run_once(
                use_llm_func,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                max_tokens=max_tokens,
            )
        )
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def main() -> None:
    parser = argparse.ArgumentParser(description="LightRAG LLM call smoke test")
    parser.add_argument("--prompt", type=str, default=None)
    parser.add_argument("--prompt-file", type=str, default=None)
    parser.add_argument("--system-prompt", type=str, default=None)
    parser.add_argument("--system-prompt-file", type=str, default=None)
    parser.add_argument("--history-json", type=str, default=None)
    parser.add_argument("--history-file", type=str, default=None)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--binding", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--host", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()

    config_args = _load_env_config()
    binding = args.binding or os.getenv("LLM_BINDING") or config_args.llm_binding
    model = args.model or os.getenv("LLM_MODEL") or config_args.llm_model
    host = args.host or os.getenv("LLM_BINDING_HOST") or get_default_host(binding)
    api_key = args.api_key or os.getenv("LLM_BINDING_API_KEY")
    timeout = args.timeout or os.getenv("LLM_TIMEOUT")
    timeout_value = int(timeout) if timeout is not None else DEFAULT_LLM_TIMEOUT

    prompt = _read_text_arg(args.prompt, args.prompt_file)
    system_prompt = None
    if args.system_prompt is not None or args.system_prompt_file is not None:
        system_prompt = _read_text_arg(args.system_prompt, args.system_prompt_file)
        if system_prompt == "":
            system_prompt = None
    history_messages = _read_json_arg(args.history_json, args.history_file)

    use_llm_func = _build_llm_func(
        binding=binding,
        model=model,
        host=host,
        api_key=api_key,
        timeout=timeout_value,
        config_args=config_args,
    )

    threads = max(1, args.threads)
    if threads == 1 or args.repeat == 1:
        for idx in range(args.repeat):
            output, duration_ms = _run_once_sync(
                use_llm_func,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                max_tokens=args.max_tokens,
            )
            print(f"[run {idx + 1}/{args.repeat}] {duration_ms}ms")
            print(output)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {}
        for idx in range(args.repeat):
            futures[
                executor.submit(
                    _run_once_sync,
                    use_llm_func,
                    prompt,
                    system_prompt,
                    history_messages,
                    args.max_tokens,
                )
            ] = idx + 1

        for future in concurrent.futures.as_completed(futures):
            run_id = futures[future]
            output, duration_ms = future.result()
            print(f"[run {run_id}/{args.repeat}] {duration_ms}ms")
            print(output)


if __name__ == "__main__":
    main()
