"""OpenAI-compatible multimodal VLM client."""

import asyncio
import base64
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class VLMClient:
    """Async VLM client for OpenAI-compatible multimodal APIs."""

    def __init__(self, config):
        self.api_base = config.vlm_api_base.rstrip("/")
        self.api_key = config.vlm_api_key
        self.model = config.vlm_model
        self.timeout = config.vlm_timeout
        self.retry_count = getattr(config, "vlm_retry_count", 5)
        self.use_bearer_auth = getattr(config, "vlm_use_bearer_auth", True)
        self.disable_proxy = getattr(config, "vlm_disable_proxy", True)
        self._semaphore = asyncio.Semaphore(config.vlm_concurrency)
        self._total_calls = 0
        self._total_tokens = 0

    def set_parallel_limit(self, limit: int):
        self._semaphore = asyncio.Semaphore(max(1, int(limit or 1)))

    @staticmethod
    def encode_image(path: str) -> tuple[str, str]:
        """Read an image and return (base64_str, mime_type)."""
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "image/jpeg"
        return b64, mime

    async def chat_with_image(
        self,
        system: str,
        user_text: str,
        image_path: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        retry_count: int | None = None,
    ) -> VLMResponse:
        return await self.chat_with_images(
            system=system,
            user_text=user_text,
            image_paths=[image_path],
            temperature=temperature,
            max_tokens=max_tokens,
            retry_count=retry_count,
        )

    async def chat_with_images(
        self,
        system: str,
        user_text: str,
        image_paths: list[str],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        retry_count: int | None = None,
    ) -> VLMResponse:
        retry_count = self.retry_count if retry_count is None else retry_count
        content = []
        for image_path in image_paths:
            b64, mime = self.encode_image(image_path)
            data_uri = f"data:{mime};base64,{b64}"
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                }
            )
        content.append({"type": "text", "text": user_text})

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": content,
            },
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": self._auth_header_value(self.api_key),
            "Content-Type": "application/json",
        }

        async with self._semaphore:
            for attempt in range(retry_count):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout, trust_env=not self.disable_proxy
                    ) as client:
                        resp = await client.post(
                            f"{self.api_base}/v1/chat/completions",
                            headers=headers,
                            json=payload,
                        )
                        if resp.status_code == 429:
                            wait = 2 ** (attempt + 1)
                            logger.warning(f"VLM rate limited, retrying in {wait}s...")
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        body = resp.json()

                    usage = body.get("usage", {})
                    choice = body["choices"][0]
                    result = VLMResponse(
                        content=choice["message"]["content"],
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                    )
                    self._total_calls += 1
                    self._total_tokens += result.total_tokens
                    return result
                except httpx.HTTPStatusError as e:
                    if attempt < retry_count - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"VLM HTTP {e.response.status_code}, retry in {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        raise
                except (httpx.ConnectError, httpx.ReadTimeout) as e:
                    if attempt < retry_count - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "VLM %s: %r, retry in %ss",
                            type(e).__name__,
                            e,
                            wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise

        raise RuntimeError(f"VLM call failed after {retry_count} retries")

    def _auth_header_value(self, api_key: str) -> str:
        if self.use_bearer_auth and not api_key.startswith("Bearer "):
            return f"Bearer {api_key}"
        return api_key

    @property
    def stats(self) -> dict:
        return {"total_calls": self._total_calls, "total_tokens": self._total_tokens}
