"""Unit tests for AI Accountability Coach service (Milestone 2).

Verifies Google GenAI SDK integration, coach persona, sliding context window,
context reset, excuse vs legitimate obstacle evaluator, micro-habit routing,
and resilient zero-network offline fallbacks.
100% offline, zero-network deterministic testing via injected mocks.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from google.genai import errors, types

from src.coach import (
    AICoachService,
    classify_skip_reason_offline,
    parse_skip_evaluation,
)
from src.config import AppConfig, DEFAULT_FALLBACKS, DEFAULT_PROMPTS, DEFAULT_SYSTEM_PROMPT


# =====================================================================
# Test Fixtures
# =====================================================================

@pytest.fixture
def mock_genai_response_factory():
    """Factory fixture to generate mocked Gemini API response objects."""
    def _create(text: str = "Tập luyện ngay đi, không nói nhiều!"):
        resp = MagicMock()
        resp.text = text
        candidate = MagicMock()
        candidate.content.parts = [MagicMock(text=text)]
        resp.candidates = [candidate]
        return resp
    return _create


@pytest.fixture
def mock_genai_client(mock_genai_response_factory):
    """Fixture providing a mock Google GenAI client with async models namespace."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=mock_genai_response_factory("Phản hồi huấn luyện viên mặc định.")
    )
    return client


@pytest.fixture
def coach_service(mock_genai_client, valid_yaml_dict):
    """Fixture providing an AICoachService instance with injected mock client."""
    return AICoachService(
        api_key="mock-api-key",
        model_name="gemini-2.5-flash",
        config=valid_yaml_dict,
        client=mock_genai_client,
    )


# =====================================================================
# Class 1: TestAICoachInitAndConfig (4 tests)
# =====================================================================

class TestAICoachInitAndConfig:
    """Verifies constructor parameters, defaults, and dependency injection."""

    def test_init_with_defaults(self, mock_genai_client):
        coach = AICoachService(api_key="mock-key", client=mock_genai_client)
        assert coach.model_name == "gemini-2.5-flash"
        assert coach.history_limit == 10
        assert len(coach._history) == 0
        assert coach.client is mock_genai_client

    def test_init_with_custom_model(self, mock_genai_client):
        coach = AICoachService(
            api_key="mock-key",
            model_name="gemini-2.0-flash",
            client=mock_genai_client,
        )
        assert coach.model_name == "gemini-2.0-flash"

    def test_init_with_dict_config_window_size(self, mock_genai_client):
        cfg = {"context_window_size": 6}
        coach = AICoachService(api_key="mock-key", config=cfg, client=mock_genai_client)
        assert coach.history_limit == 6

    def test_init_with_app_config_instance(self, mock_genai_client, valid_yaml_dict):
        coach = AICoachService(
            api_key="mock-key",
            config=valid_yaml_dict,
            client=mock_genai_client,
        )
        assert coach.history_limit == 10
        assert "completion_praise" in coach.prompts


# =====================================================================
# Class 2: TestCongratulationGeneration (5 tests)
# =====================================================================

@pytest.mark.asyncio
class TestCongratulationGeneration:
    """Verifies praise generation across streak counts and session types."""

    async def test_congratulation_gym_streak_1(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "Tốt lắm, buổi tập đầu tiên hoàn thành sạch sẽ!"
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="gym", streak=1)
        assert result == expected_praise
        assert mock_genai_client.aio.models.generate_content.called

        called_args = mock_genai_client.aio.models.generate_content.call_args
        prompt_content = str(called_args.kwargs.get("contents") or called_args[1].get("contents"))
        assert "1" in prompt_content
        assert "Gym" in prompt_content or "gym" in prompt_content

    async def test_congratulation_toeic_streak_7(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "7 ngày liên tục! Giữ vững kỷ luật này để đạt mục tiêu."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="toeic", streak=7)
        assert result == expected_praise

        called_args = mock_genai_client.aio.models.generate_content.call_args
        prompt_content = str(called_args.kwargs.get("contents") or called_args[1].get("contents"))
        assert "7" in prompt_content

    async def test_congratulation_major_streak_100(self, coach_service, mock_genai_client, mock_genai_response_factory):
        expected_praise = "100 ngày commit liên tục! Một cột mốc đáng nể của một kỹ sư."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(expected_praise)

        result = await coach_service.get_congratulation(session_type="major", streak=100)
        assert result == expected_praise

        called_args = mock_genai_client.aio.models.generate_content.call_args
        prompt_content = str(called_args.kwargs.get("contents") or called_args[1].get("contents"))
        assert "100" in prompt_content

    async def test_congratulation_offline_fallback_on_api_error(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=500, response_json={"error": {"message": "Internal error"}}
        )
        result = await coach_service.get_congratulation(session_type="gym", streak=3)
        assert result == coach_service.fallbacks.get("offline_praise")

    async def test_congratulation_does_not_pollute_history(self, coach_service):
        assert len(coach_service._history) == 0
        await coach_service.get_congratulation(session_type="gym", streak=5)
        # History must remain isolated from event-driven praises
        assert len(coach_service._history) == 0


# =====================================================================
# Class 3: TestExcuseEvaluation (7 tests)
# =====================================================================

@pytest.mark.asyncio
class TestExcuseEvaluation:
    """Verifies classification of excuses vs legitimate obstacles and micro-habits."""

    async def test_evaluate_obvious_lazy_excuse(self, coach_service, mock_genai_client, mock_genai_response_factory):
        raw_output = "[EXCUSE] Đừng viện cớ chơi game nữa. Mở IDE lên viết đúng 1 hàm rồi commit ngay!"
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(raw_output)

        classification, text = await coach_service.evaluate_skip_reason("major", "Đang dở ván Dota với bạn")
        assert classification == "EXCUSE"
        assert "[EXCUSE]" not in text
        assert "viết đúng 1 hàm" in text

    async def test_evaluate_legitimate_medical_emergency(self, coach_service, mock_genai_client, mock_genai_response_factory):
        raw_output = "[LEGITIMATE] Đã ghi nhận sốt cao. Hãy nghỉ ngơi, ngày mai hồi phục tài nguyên rồi tiếp tục."
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(raw_output)

        classification, text = await coach_service.evaluate_skip_reason("gym", "Sốt cao 39.5 độ phải nằm truyền nước")
        assert classification == "LEGITIMATE"
        assert "[LEGITIMATE]" not in text
        assert "nghỉ ngơi" in text

    async def test_evaluate_parser_tolerates_varied_casing_and_prefixes(self):
        c1, t1 = parse_skip_evaluation("[excuse] Lười quá thì hít đất 5 cái đi.")
        assert c1 == "EXCUSE"
        assert "[excuse]" not in t1.lower()

        c2, t2 = parse_skip_evaluation("CLASSIFICATION: LEGITIMATE\nĐã duyệt nghỉ cấp cứu.")
        assert c2 == "LEGITIMATE"
        assert "CLASSIFICATION" not in t2

    async def test_evaluate_gym_micro_habit_injection(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("gym", "Lười quá trời mưa")
        assert classification == "EXCUSE"
        assert "chống đẩy" in text or "plank" in text or "micro-habit" in text

    async def test_evaluate_toeic_micro_habit_injection(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("toeic", "Buồn ngủ mai học bù")
        assert classification == "EXCUSE"
        assert "Part 5" in text or "câu" in text or "micro-habit" in text

    async def test_evaluate_major_micro_habit_injection(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        classification, text = await coach_service.evaluate_skip_reason("major", "Chán không muốn code")
        assert classification == "EXCUSE"
        assert "IDE" in text or "function" in text or "commit" in text or "micro-habit" in text

    async def test_evaluate_offline_legitimate_emergency(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=429, response_json={"error": {"message": "Quota exceeded"}}
        )
        classification, text = await coach_service.evaluate_skip_reason("gym", "Gia đình có tang khẩn cấp")
        assert classification == "LEGITIMATE"
        assert len(text) > 0


# =====================================================================
# Class 4: TestSlidingConversationHistory (6 tests)
# =====================================================================

@pytest.mark.asyncio
class TestSlidingConversationHistory:
    """Verifies rolling buffer deque(maxlen=10), FIFO trimming, and turn invariants."""

    async def test_chat_single_turn_adds_to_history(self, coach_service, mock_genai_client, mock_genai_response_factory):
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory("Bắt đầu bài tập nào!")
        reply = await coach_service.chat("Chào coach")

        assert reply == "Bắt đầu bài tập nào!"
        assert len(coach_service._history) == 2
        assert coach_service._history[0].role == "user"
        assert coach_service._history[1].role == "model"

    async def test_chat_multiturn_order_preserved(self, coach_service, mock_genai_client, mock_genai_response_factory):
        for i in range(3):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Trả lời {i}")
            await coach_service.chat(f"Tin nhắn {i}")

        assert len(coach_service._history) == 6
        roles = [msg.role for msg in coach_service._history]
        assert roles == ["user", "model", "user", "model", "user", "model"]

    async def test_chat_history_trimmed_at_maxlen_10(self, coach_service, mock_genai_client, mock_genai_response_factory):
        for i in range(7):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Trả lời {i}")
            await coach_service.chat(f"Tin nhắn {i}")

        assert len(coach_service._history) <= 10
        first_user_text = coach_service._history[0].parts[0].text
        assert "Tin nhắn 0" not in first_user_text

    async def test_chat_request_payload_always_starts_with_user(self, coach_service, mock_genai_client, mock_genai_response_factory):
        """Verifies Gemini multi-turn requirement: first content item must have role='user'."""
        for i in range(7):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"Resp {i}")
            await coach_service.chat(f"Msg {i}")

            called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
            contents = called_kwargs.get("contents")
            assert isinstance(contents, list)
            assert contents[0].role == "user", "Conversation payload sent to Gemini MUST start with role 'user'!"

    async def test_chat_fallback_recorded_in_history_maintains_alternating_turns(self, coach_service, mock_genai_client):
        await coach_service.chat("Tin nhắn 1")
        mock_genai_client.aio.models.generate_content.side_effect = ConnectionError("Disconnected")
        reply = await coach_service.chat("Tin nhắn 2")

        assert (
            reply == coach_service.fallbacks.get("offline_coach")
            or reply == coach_service.fallbacks.get("offline_error")
            or "mất kết nối" in reply
            or "kỷ luật" in reply
        )
        assert len(coach_service._history) == 4
        assert coach_service._history[-1].role == "model"

    async def test_chat_empty_or_whitespace_message_handling(self, coach_service):
        reply = await coach_service.chat("   ")
        assert isinstance(reply, str)
        assert len(reply) > 0


# =====================================================================
# Class 5: TestContextReset (3 tests)
# =====================================================================

@pytest.mark.asyncio
class TestContextReset:
    """Verifies clear_context() behavior and state isolation."""

    async def test_clear_context_empties_populated_history(self, coach_service, mock_genai_client, mock_genai_response_factory):
        for i in range(3):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory(f"R {i}")
            await coach_service.chat(f"M {i}")

        assert len(coach_service._history) == 6
        coach_service.clear_context()
        assert len(coach_service._history) == 0

    async def test_clear_context_idempotent_on_empty(self, coach_service):
        assert len(coach_service._history) == 0
        coach_service.clear_context()
        coach_service.clear_context()
        assert len(coach_service._history) == 0

    async def test_chat_after_clear_context_starts_fresh(self, coach_service, mock_genai_client, mock_genai_response_factory):
        await coach_service.chat("Cũ 1")
        coach_service.clear_context()

        mock_genai_client.aio.models.generate_content.return_value = mock_genai_response_factory("Mới 1")
        await coach_service.chat("Mới 1")

        assert len(coach_service._history) == 2
        assert coach_service._history[0].parts[0].text == "Mới 1"


# =====================================================================
# Class 6: TestOfflineFallbacksAndExceptions (5 tests)
# =====================================================================

@pytest.mark.asyncio
class TestOfflineFallbacksAndExceptions:
    """Verifies graceful degradation across API and network errors."""

    async def test_fallback_on_api_timeout(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
        res = await coach_service.chat("Alo?")
        assert (
            res == coach_service.fallbacks.get("offline_coach")
            or res == coach_service.fallbacks.get("offline_error")
            or "mất kết nối" in res
            or "kỷ luật" in res
        )

    async def test_fallback_on_rate_limit_429(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=429, response_json={"error": {"message": "Resource exhausted"}}
        )
        res = await coach_service.chat("Alo?")
        assert (
            res == coach_service.fallbacks.get("offline_coach")
            or res == coach_service.fallbacks.get("offline_error")
            or "kỷ luật" in res
        )

    async def test_fallback_on_server_error_500(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
            code=500, response_json={"error": {"message": "Server error"}}
        )
        res = await coach_service.chat("Alo?")
        assert (
            res == coach_service.fallbacks.get("offline_coach")
            or res == coach_service.fallbacks.get("offline_error")
            or "kỷ luật" in res
        )

    async def test_fallback_on_connection_error(self, coach_service, mock_genai_client):
        mock_genai_client.aio.models.generate_content.side_effect = ConnectionError("Network unreachable")
        res = await coach_service.chat("Alo?")
        assert (
            res == coach_service.fallbacks.get("offline_coach")
            or res == coach_service.fallbacks.get("offline_error")
            or "mất kết nối" in res
            or "kỷ luật" in res
        )

    async def test_fallback_on_empty_candidates_none_text(self, coach_service, mock_genai_client):
        empty_resp = MagicMock()
        empty_resp.text = None
        empty_resp.candidates = []
        mock_genai_client.aio.models.generate_content.return_value = empty_resp

        res = await coach_service.chat("Alo?")
        assert res is not None
        assert len(res) > 0


# =====================================================================
# Class 7: TestPromptConstructionAndSafeguards (2 tests)
# =====================================================================

@pytest.mark.asyncio
class TestPromptConstructionAndSafeguards:
    """Verifies prompt generation configuration and token safeguards."""

    async def test_config_system_instruction_passed(self, coach_service, mock_genai_client):
        await coach_service.chat("Test system prompt")
        called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        cfg = called_kwargs.get("config")
        assert cfg is not None
        sys_inst = cfg.system_instruction
        assert "Huấn Luyện Viên" in sys_inst or "kỷ luật" in sys_inst.lower()

    async def test_generation_parameters_temperature_and_tokens(self, coach_service, mock_genai_client):
        await coach_service.chat("Test params")
        called_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        cfg = called_kwargs.get("config")
        assert cfg.temperature == 0.7
        assert cfg.max_output_tokens == 256
