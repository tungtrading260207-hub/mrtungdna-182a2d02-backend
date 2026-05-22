import logging
from httpx import AsyncClient
import httpx
from ..db import SupabaseClient


class AIAnalyzer:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client

    async def summarize_scan(self, summary: str, context: str | None = None) -> str:
        prompt = self._build_prompt(summary, context)
        try:
            return await self._call_supabase_function(prompt)
        except Exception as exc:
            logging.warning("Supabase function fallback failed: %s", exc)

        logging.error("AI annotation unavailable for scan summary.")
        return "Ghi chú AI không khả dụng do lỗi dịch vụ AI."

    def _build_prompt(self, summary: str, context: str | None = None) -> str:
        base = (
            "Bạn là MrTung Brain, chuyên gia phân tích tài chính. "
            "Dựa trên dữ liệu thô dưới đây, hãy viết một nhận định ngắn gọn chuyên sâu, "
            "nêu rõ xu hướng, cơ hội và rủi ro chính."
        )
        if context:
            base += f"\nDữ liệu bổ sung: {context}"
        base += f"\n\nDữ liệu thô:\n{summary}\n\nTóm tắt trong 2-3 câu."
        return base


    async def _call_supabase_function(self, prompt: str) -> str:
        try:
            body = {
                "messages": [
                    {"role": "system", "content": "Bạn là MrTung Brain, chuyên gia phân tích tài chính."},
                    {"role": "user", "content": prompt},
                ]
            }
            payload = await self.supabase_client.invoke_function("mrtung-chat", method="POST", body=body)
            if isinstance(payload, dict):
                if "text" in payload and isinstance(payload["text"], str):
                    return payload["text"].strip()
                if "data" in payload and isinstance(payload["data"], dict):
                    text = payload["data"].get("text")
                    if isinstance(text, str):
                        return text.strip()
            raise ValueError("Supabase function returned invalid AI response")
        except Exception as exc:
            raise RuntimeError(f"Supabase function error: {exc}")
