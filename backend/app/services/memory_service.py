import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from app.core.config import settings


MEMORY_DIR = os.path.join(settings.DATA_DIR, "memory")


class MemoryService:
    """Manages per-lesson conversation memory, persisting each round as a local JSON file."""

    def __init__(self, ai_service=None):
        self.ai_service = ai_service

    def _lesson_dir(self, lesson_id: str) -> str:
        path = os.path.join(MEMORY_DIR, lesson_id)
        os.makedirs(path, exist_ok=True)
        return path

    def save_round_memory(
        self,
        lesson_id: str,
        stage: int,
        round_num: int,
        agents: List[Dict],
        vote_result: Optional[Dict] = None,
        summary: str = "",
        accumulated_context: str = "",
    ) -> str:
        """Save a single discussion round to a JSON file. Returns the file path."""
        lesson_dir = self._lesson_dir(lesson_id)
        filename = f"round_{stage}_{round_num}.json"
        filepath = os.path.join(lesson_dir, filename)

        data = {
            "lesson_id": lesson_id,
            "stage": stage,
            "round": round_num,
            "timestamp": datetime.utcnow().isoformat(),
            "agents": agents,
            "vote_result": vote_result,
            "summary": summary,
            "accumulated_context": accumulated_context,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"[Memory] Saved round memory: {filepath}")
        return filepath

    def load_memory(self, lesson_id: str) -> List[Dict]:
        """Load all round memory files for a lesson, sorted by stage then round."""
        lesson_dir = self._lesson_dir(lesson_id)
        memories = []

        for filename in sorted(os.listdir(lesson_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(lesson_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                memories.append(data)
            except Exception as e:
                logger.warning(f"[Memory] Failed to load {filepath}: {e}")

        return memories

    def get_accumulated_context(self, lesson_id: str, max_chars: int = 3000) -> str:
        """Build accumulated context string from all previous rounds for injection into prompts."""
        memories = self.load_memory(lesson_id)
        if not memories:
            return ""

        parts = ["【前序讨论记忆】"]
        total_len = 0
        for mem in memories:
            summary = mem.get("summary", "")
            if not summary:
                continue
            entry = f"[阶段{mem['stage']}] {summary}"
            if total_len + len(entry) > max_chars:
                break
            parts.append(entry)
            total_len += len(entry)

        return "\n".join(parts) if len(parts) > 1 else ""

    async def summarize_round(self, conversation_text: str) -> str:
        """Use AI to generate a concise summary of a discussion round."""
        if not self.ai_service:
            return self._fallback_summarize(conversation_text)

        prompt = f"""请用50-100字简要总结以下教研讨论的核心观点和结论：

{conversation_text[:2000]}

只输出总结，不要其他内容。"""

        try:
            summary = await self.ai_service.generate(
                prompt,
                system_message="你是教研讨论记录员，负责精炼总结讨论要点。",
                max_tokens=200,
                temperature=0.3,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"[Memory] AI summarize failed: {e}, using fallback")
            return self._fallback_summarize(conversation_text)

    @staticmethod
    def _fallback_summarize(text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return "；".join(lines[:3])[:200] if lines else ""

    def clear_memory(self, lesson_id: str):
        """Remove all memory files for a lesson."""
        lesson_dir = self._lesson_dir(lesson_id)
        if os.path.exists(lesson_dir):
            for f in os.listdir(lesson_dir):
                os.remove(os.path.join(lesson_dir, f))
            logger.info(f"[Memory] Cleared memory for lesson {lesson_id}")
