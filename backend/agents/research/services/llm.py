import time

from langchain_groq import ChatGroq

from dotenv import load_dotenv
import os

load_dotenv(override=True)

MODEL = "openai/gpt-oss-120b"
MODEL_LIGHT = "openai/gpt-oss-20b"
MODEL_QWEN = "qwen/qwen3.8-27b"

_last_invoke_time: float = 0.0
_INVOKE_DELAY: float = 4.0


class RateLimitedChatGroq(ChatGroq):
    def invoke(self, *args, **kwargs):
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
        api_key=os.getenv("GROQ_API_KEY"),
    )


def init_llm_light(temperature: float = 0.1, max_tokens: int = 2048) -> ChatGroq:
    return RateLimitedChatGroq(
        model=MODEL_LIGHT,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def init_llm_qwen(temperature: float = 0.1, max_tokens: int = 2048) -> ChatGroq:
    return RateLimitedChatGroq(
        model=MODEL_QWEN,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv("GROQ_API_KEY"),
    )
