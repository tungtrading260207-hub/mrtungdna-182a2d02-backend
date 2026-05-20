import logging
from httpx import AsyncClient, HTTPError
from ..db import SupabaseClient
from ..config import settings


class AIAnalyzer:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.gemini_key = settings.gemini_api_key
        self.lovable_key = settings.lovable_api_key

    async def summarize_scan(self, summary: str, context: str | None = None) -> str:
        prompt = self._build_prompt(summary, context)
        if self.gemini_key:
            try:
                return await self._call_gemini(prompt)
            except Exception as exc:
                logging.warning("Gemini analysis failed, falling back to API: %s", exc)

        if self.lovable_key:
            try:
                return await self._call_lovable(prompt)
            except Exception as exc:
                logging.warning("Lovable AI fallback failed: %s", exc)

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

    async def _call_gemini(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
        async with AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
            response.raise_for_status()
            data = response.json()
            candidate = data.get("candidates", [{}])[0]
            text = candidate.get("content", {}).get("parts", [{}])[0].get("text")
            if not text:
                raise ValueError("Empty Gemini response")
            return text.strip()

    async def _call_lovable(self, prompt: str) -> str:
        url = "https://ai.gateway.lovable.dev/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.lovable_key}", "Content-Type": "application/json"}
        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {"role": "system", "content": "Bạn là chuyên gia phân tích tài chính MrTung."},
                {"role": "user", "content": prompt},
            ],
        }
        async with AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            candidate = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not candidate:
                raise ValueError("Empty Lovable response")
            return candidate.strip()

    async def _call_supabase_function(self, prompt: str) -> str:
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
