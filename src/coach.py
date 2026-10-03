"""AI Accountability Coach service powered by Google Gemini 2.5 Flash.

Provides two-way interactive coaching, proactive praise generation,
excuse evaluation with 2-minute micro-habit routing, sliding context history,
and resilient zero-network offline fallbacks.
"""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from google import genai
from google.genai import errors, types

from src.config import DEFAULT_FALLBACKS, DEFAULT_PROMPTS, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Micro-habit actions mapped to activity domains
SESSION_MICRO_HABIT_MAP: Dict[str, str] = {
    "gym": "chống đẩy 5 cái hoặc plank 60s tại chỗ",
    "toeic": "giải đúng 3 câu Part 5 hoặc nghe 1 đoạn Part 3",
    "major": "mở IDE viết đúng 1 function và commit git",
}

# Rule-based offline keyword heuristics
LEGITIMATE_KEYWORDS: List[str] = [
    "sốt", "bệnh", "ốm", "cấp cứu", "nhập viện", "bác sĩ", "khám bệnh",
    "tai nạn", "té xe", "ngã", "chấn thương", "gãy", "đau ruột thừa",
    "ngộ độc", "truyền nước", "mất điện", "cháy", "tang", "đám tang",
    "qua đời", "ngập lụt", "bão", "sập nguồn", "bệnh viện",
]

EXCUSE_KEYWORDS: List[str] = [
    "mệt", "lười", "chán", "game", "dota", "lol", "liên quân", "valorant",
    "ngủ", "buồn ngủ", "mai", "bù", "bận", "lướt", "facebook", "tiktok",
    "youtube", "nhậu", "bia", "cafe", "cà phê", "đi chơi", "hẹn hò",
    "mưa", "hết hứng", "tụt mood", "quên", "ngại",
]


def get_micro_habit_for_session(session_type: str) -> str:
    """Returns domain-tailored 2-minute micro-habit challenge for session type."""
    st = (session_type or "").lower()
    for key, suggestion in SESSION_MICRO_HABIT_MAP.items():
        if key in st:
            return suggestion
    return "thực hiện đúng 2 phút hành động khởi động"


def parse_skip_evaluation(raw_text: str, default_classification: str = "EXCUSE") -> Tuple[str, str]:
    """Parses Gemini output into strict (classification, clean_text) tuple.

    Guarantees classification is strictly 'EXCUSE' or 'LEGITIMATE'.
    Strips prefix tags ([EXCUSE], [LEGITIMATE], CLASSIFICATION: ...) from response text.
    """
    if not raw_text or not raw_text.strip():
        return default_classification, ""

    text = raw_text.strip()

    # Priority 1: Match bracketed tags [EXCUSE] or [LEGITIMATE]
    tag_match = re.search(r"\[(EXCUSE|LEGITIMATE)\]", text, re.IGNORECASE)
    if tag_match:
        classification = tag_match.group(1).upper()
        clean_text = re.sub(r"\[(EXCUSE|LEGITIMATE)\]\s*[:\-]?", "", text, flags=re.IGNORECASE).strip()
        return classification, clean_text

    # Priority 2: Match line prefixes (e.g. 'CLASSIFICATION: EXCUSE' or 'LEGITIMATE:')
    line_match = re.search(
        r"^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\b",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if line_match:
        classification = line_match.group(1).upper()
        clean_text = re.sub(
            r"^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\s*[:\-]?",
            "",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        ).strip()
        return classification, clean_text

    # Priority 3: Case-insensitive presence check
    if "LEGITIMATE" in text.upper():
        clean_text = re.sub(r"\bLEGITIMATE\b\s*[:\-]?", "", text, flags=re.IGNORECASE).strip()
        return "LEGITIMATE", clean_text
    elif "EXCUSE" in text.upper():
        clean_text = re.sub(r"\bEXCUSE\b\s*[:\-]?", "", text, flags=re.IGNORECASE).strip()
        return "EXCUSE", clean_text

    return default_classification, text


def classify_skip_reason_offline(
    session_type: str,
    reason: str,
    fallbacks: Optional[Dict[str, str]] = None,
) -> Tuple[str, str]:
    """Deterministic local rule-based classifier when offline or Gemini API is unreachable."""
    if fallbacks is None:
        fallbacks = {}

    clean_reason = (reason or "").strip().lower()

    # Legitimate medical emergency or force majeure
    if any(kw in clean_reason for kw in LEGITIMATE_KEYWORDS):
        msg = fallbacks.get(
            "offline_skip_legitimate",
            "🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!",
        )
        return "LEGITIMATE", msg

    # Everything else defaults to EXCUSE with tailored micro-habit
    st = (session_type or "").lower()
    if "gym" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: chống đẩy 5 cái hoặc plank 60s tại chỗ trước khi nghỉ!"
    elif "toeic" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu giải đúng 3 câu Part 5 trước khi tắt máy!"
    elif "major" in st or "game" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở IDE viết đúng 1 function và commit git trước khi nghỉ!"
    else:
        msg = fallbacks.get(
            "offline_skip_excuse",
            "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!",
        )
    return "EXCUSE", msg


class AICoachService:
    """Two-way interactive AI Accountability Coach powered by Google Gemini 2.5 Flash."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        config: Optional[Union[Dict[str, Any], Any]] = None,
        client: Optional[Any] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.config: Any = config or {}
        self.temperature: float = 0.7
        self.max_output_tokens: int = 256

        self.history_limit: int = 10
        self.prompts: Dict[str, str] = dict(DEFAULT_PROMPTS)
        self.fallbacks: Dict[str, str] = dict(DEFAULT_FALLBACKS)
        self.system_prompt: str = DEFAULT_SYSTEM_PROMPT

        self._extract_config_values(config)

        self._history: deque[types.Content] = deque(maxlen=self.history_limit)

        if client is not None:
            self.client = client
        else:
            self.client = genai.Client(api_key=api_key)

    def _extract_config_values(self, config: Optional[Union[Dict[str, Any], Any]]) -> None:
        if config is None:
            return

        # Handle dataclass instances (e.g. AppConfig)
        if hasattr(config, "context_window_size"):
            self.history_limit = config.context_window_size
        if hasattr(config, "prompts") and isinstance(config.prompts, dict):
            self.prompts.update(config.prompts)
        if hasattr(config, "fallbacks") and isinstance(config.fallbacks, dict):
            self.fallbacks.update(config.fallbacks)
        if hasattr(config, "system_prompt") and config.system_prompt:
            self.system_prompt = config.system_prompt

        # Handle dictionary configuration
        if isinstance(config, dict):
            app_section = config.get("app") if isinstance(config.get("app"), dict) else {}
            ai_coach_section = config.get("ai_coach") if isinstance(config.get("ai_coach"), dict) else {}

            if "context_window_size" in config:
                self.history_limit = config["context_window_size"]
            elif "history_limit" in config:
                self.history_limit = config["history_limit"]
            elif "context_window_size" in app_section:
                self.history_limit = app_section["context_window_size"]
            elif "history_limit" in app_section:
                self.history_limit = app_section["history_limit"]

            if "prompts" in config and isinstance(config["prompts"], dict):
                self.prompts.update(config["prompts"])
            if "prompts" in ai_coach_section and isinstance(ai_coach_section["prompts"], dict):
                self.prompts.update(ai_coach_section["prompts"])

            if "fallbacks" in config and isinstance(config["fallbacks"], dict):
                self.fallbacks.update(config["fallbacks"])
            if "fallbacks" in ai_coach_section and isinstance(ai_coach_section["fallbacks"], dict):
                self.fallbacks.update(ai_coach_section["fallbacks"])

            if "system_prompt" in config and config["system_prompt"]:
                self.system_prompt = config["system_prompt"]
            elif "system_prompt" in ai_coach_section and ai_coach_section["system_prompt"]:
                self.system_prompt = ai_coach_section["system_prompt"]
            elif "system_instruction" in self.prompts:
                self.system_prompt = self.prompts["system_instruction"]

            if "temperature" in ai_coach_section:
                self.temperature = float(ai_coach_section["temperature"])
            if "max_output_tokens" in ai_coach_section:
                self.max_output_tokens = int(ai_coach_section["max_output_tokens"])

    @property
    def context_window(self) -> List[Tuple[str, str]]:
        """Exposes conversation history as (role, text) tuples for contract and test compatibility."""
        result: List[Tuple[str, str]] = []
        for c in self._history:
            text = ""
            if c.parts and hasattr(c.parts[0], "text") and c.parts[0].text is not None:
                text = c.parts[0].text
            result.append((c.role, text))
        return result

    def _get_sanitized_history_contents(self) -> List[types.Content]:
        """Returns a sanitized snapshot of history starting strictly with 'user'.

        If deque FIFO eviction dropped a user message and left a leading 'model'
        message, the orphaned 'model' message is discarded from the API payload.
        """
        contents = list(self._history)
        while contents and contents[0].role == "model":
            contents.pop(0)
        return contents

    async def get_congratulation(self, session_type: str, streak: int) -> str:
        """Generates concise discipline praise acknowledging current streak."""
        session_name_map = {
            "gym": "Gym",
            "toeic": "TOEIC",
            "major": "Chuyên ngành & Game Dev",
        }
        s_name = session_name_map.get(session_type.lower(), session_type)
        template = (
            self.prompts.get("completion_praise")
            or self.prompts.get("congratulation")
            or DEFAULT_PROMPTS["completion_praise"]
        )

        if "{streak}" in template or "{session_name}" in template:
            prompt = template.format(session_name=s_name, detail=session_type, streak=streak)
        else:
            prompt = f"{template}\nPhiên: {s_name} ({session_type}). Streak: {streak} ngày liên tiếp."

        gen_config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            http_options=types.HttpOptions(timeout=15000),
        )

        try:
            resp = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                ),
                timeout=15.0,
            )
            text = resp.text.strip() if resp and resp.text else ""
            if text:
                return text
            return self.fallbacks.get("offline_praise", DEFAULT_FALLBACKS["offline_praise"])
        except Exception as exc:
            logger.warning("Error getting congratulation via Gemini: %s. Using fallback.", exc)
            return self.fallbacks.get("offline_praise", DEFAULT_FALLBACKS["offline_praise"])

    async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]:
        """Evaluates whether skip reason is legitimate obstacle or procrastination excuse.

        Returns (classification: 'EXCUSE' | 'LEGITIMATE', response_text: str).
        """
        session_name_map = {
            "gym": "Gym",
            "toeic": "TOEIC",
            "major": "Chuyên ngành & Game Dev",
        }
        s_name = session_name_map.get(session_type.lower(), session_type)
        micro_habit = get_micro_habit_for_session(session_type)
        template = (
            self.prompts.get("skip_evaluator")
            or self.prompts.get("excuse_evaluation")
            or DEFAULT_PROMPTS["skip_evaluator"]
        )

        if "{reason}" in template:
            try:
                prompt = template.format(
                    session_name=s_name,
                    detail=session_type,
                    reason=reason,
                    micro_habit_suggestion=micro_habit,
                )
            except (KeyError, IndexError):
                prompt = (
                    f"{template}\nPhiên: {s_name} ({session_type}).\n"
                    f"Lý do: \"{reason}\".\n"
                    f"Gợi ý micro-habit 2 phút nếu là bao biện: {micro_habit}."
                )
        else:
            prompt = (
                f"{template}\nPhiên: {s_name} ({session_type}).\n"
                f"Lý do: \"{reason}\".\n"
                f"Gợi ý micro-habit 2 phút nếu là bao biện: {micro_habit}."
            )

        gen_config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            http_options=types.HttpOptions(timeout=15000),
        )

        try:
            resp = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                ),
                timeout=15.0,
            )
            raw_text = resp.text.strip() if resp and resp.text else ""
            if not raw_text:
                return classify_skip_reason_offline(session_type, reason, self.fallbacks)
            return parse_skip_evaluation(raw_text)
        except Exception as exc:
            logger.warning("Error evaluating skip reason via Gemini: %s. Using offline classifier.", exc)
            return classify_skip_reason_offline(session_type, reason, self.fallbacks)

    async def chat(self, user_message: str) -> str:
        """Reactive two-way conversation with coach maintaining sliding history buffer."""
        msg = (user_message or "").strip()
        if not msg:
            return "Hãy nói cụ thể bạn đang gặp khó khăn gì, tôi sẵn sàng hỗ trợ."

        if len(msg) > 4000:
            msg = msg[:4000]

        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=msg)],
        )
        self._history.append(user_content)
        while self._history and self._history[0].role == "model":
            self._history.popleft()

        contents = self._get_sanitized_history_contents()

        gen_config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            http_options=types.HttpOptions(timeout=15000),
        )

        fallback_text = self.fallbacks.get(
            "offline_coach",
            self.fallbacks.get("offline_error", DEFAULT_FALLBACKS["offline_coach"]),
        )

        try:
            resp = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=gen_config,
                ),
                timeout=15.0,
            )
            reply = resp.text.strip() if resp and resp.text else ""
            if not reply:
                reply = fallback_text
        except Exception as exc:
            logger.warning("Error in coach.chat() via Gemini: %s. Using fallback.", exc)
            reply = fallback_text

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=reply)],
        )
        self._history.append(model_content)
        while self._history and self._history[0].role == "model":
            self._history.popleft()

        return reply

    def clear_context(self) -> None:
        """Clears all sliding conversation history without modifying configuration or client."""
        self._history.clear()
