import os
import time

from langchain_groq import ChatGroq
from dotenv import load_dotenv

from backend.agents.research.services.progress import check_cancellation

load_dotenv(override=True)

MODEL = "openai/gpt-oss-120b"
MODEL_LIGHT = "openai/gpt-oss-20b"
MODEL_QWEN = "qwen/qwen3.8-27b"

_last_invoke_time: float = 0.0
_INVOKE_DELAY: float = 0.1


def invoke_with_timeout(llm, prompt: str, timeout: float = 15.0):
    """Call llm.invoke(prompt) with a hard wall-clock deadline.

    Every factory here pins request_timeout at construction time, so an
    interactive caller (the Assistant, the intent router) cannot tighten it
    without changing the shared client. This runs the call on a throwaway
    worker thread and gives up waiting after `timeout`.

    The pool is deliberately NOT used as a context manager: its __exit__ calls
    shutdown(wait=True), which would block past the timeout and defeat the
    whole point. The abandoned thread finishes on its own and is discarded.
    """
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(llm.invoke, prompt)
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        raise TimeoutError(f"LLM call exceeded {timeout}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class RateLimitedChatGroq(ChatGroq):
    def invoke(self, *args, **kwargs):
        check_cancellation()
        global _last_invoke_time
        elapsed = time.time() - _last_invoke_time
        if elapsed < _INVOKE_DELAY:
            time.sleep(_INVOKE_DELAY - elapsed)
        _last_invoke_time = time.time()
        return super().invoke(*args, **kwargs)


def init_llm(temperature: float = 0.1, max_tokens: int = 4096) -> ChatGroq:
    return RateLimitedChatGroq(
        model=MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=30.0,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def init_llm_light(temperature: float = 0.1, max_tokens: int = 2048) -> ChatGroq:
    return RateLimitedChatGroq(
        model=MODEL_LIGHT,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=20.0,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def init_llm_qwen(temperature: float = 0.1, max_tokens: int = 2048) -> ChatGroq:
    return RateLimitedChatGroq(
        model=MODEL_QWEN,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=30.0,
        api_key=os.getenv("GROQ_API_KEY"),
    )

