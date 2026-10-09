"""Meta-only native Chat Completions client."""
import asyncio
import httpx
from .settings import META_URL, MODEL


class MetaError(Exception):
    pass


class MetaClient:
    def __init__(self, api_key, transport=None):
        self.client = httpx.AsyncClient(
            timeout=60, transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(self, messages, tools=None):
        payload = {"model": MODEL, "messages": messages, "max_tokens": 3000}
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        for attempt in range(3):
            delay = 2 ** attempt
            try:
                response = await self.client.post(META_URL, json=payload)
            except httpx.TransportError:
                if attempt == 2:
                    raise MetaError("Koneksi Meta gagal setelah tiga percobaan.") from None
            else:
                if response.status_code in (401, 403):
                    raise MetaError("Autentikasi Meta gagal; periksa MODEL_API_KEY dan akses model.")
                if response.status_code == 429 or response.status_code >= 500:
                    try:
                        delay = min(60, max(delay, float(response.headers.get("Retry-After", delay))))
                    except ValueError:
                        pass
                    if attempt == 2:
                        raise MetaError(f"Meta belum tersedia (HTTP {response.status_code}).")
                elif response.is_error:
                    raise MetaError(f"Permintaan Meta ditolak (HTTP {response.status_code}).")
                else:
                    try:
                        message = response.json()["choices"][0]["message"]
                        if not isinstance(message, dict):
                            raise ValueError()
                        return message
                    except (ValueError, KeyError, IndexError, TypeError):
                        raise MetaError("Respons Meta tidak valid.") from None
            await asyncio.sleep(delay)
        raise MetaError("Meta tidak tersedia.")

    async def close(self):
        await self.client.aclose()
