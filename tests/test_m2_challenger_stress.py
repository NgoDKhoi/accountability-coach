"""Empirical stress-testing harness for Milestone 2 AICoachService.

Conducted by teamwork_preview_challenger (Challenger 2).
Empirically stress-tests:
1. Regex tag parsing (parse_skip_evaluation) across varied LLM outputs.
2. Session micro-habit routing (get_micro_habit_for_session).
3. Offline keyword classifier across boundary inputs, emergencies vs excuses.
4. Strict return typing Tuple[str, str] and value invariants ('EXCUSE' | 'LEGITIMATE').
5. Resilience of evaluate_skip_reason under hostile inputs and mock model behaviors.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock
import pytest
from google.genai import errors

from src.coach import (
    AICoachService,
    classify_skip_reason_offline,
    get_micro_habit_for_session,
    parse_skip_evaluation,
)
from src.config import DEFAULT_FALLBACKS, DEFAULT_PROMPTS


# =====================================================================
# 1. Stress Tests: parse_skip_evaluation
# =====================================================================

class TestStressParseSkipEvaluation:
    """Empirically stress-tests tag extraction across diverse model outputs."""

    @pytest.mark.parametrize(
        "raw_text, expected_class, expected_subtext",
        [
            # Standard bracketed
            ("[EXCUSE] Đừng lười biếng.", "EXCUSE", "Đừng lười biếng."),
            ("[LEGITIMATE] Nghỉ ngơi đi.", "LEGITIMATE", "Nghỉ ngơi đi."),
            # Mixed / lower casing
            ("[excuse] Hít đất 5 cái đi.", "EXCUSE", "Hít đất 5 cái đi."),
            ("[legitimate] Nghỉ ngơi nhé.", "LEGITIMATE", "Nghỉ ngơi nhé."),
            ("[ExCuSe] Dậy tập ngay.", "EXCUSE", "Dậy tập ngay."),
            ("[LeGiTiMaTe] Đồng ý.", "LEGITIMATE", "Đồng ý."),
            # With colon or hyphen delimiter
            ("[EXCUSE]: Bạn đang viện cớ.", "EXCUSE", "Bạn đang viện cớ."),
            ("[LEGITIMATE] - Hãy nghỉ ngơi.", "LEGITIMATE", "Hãy nghỉ ngơi."),
            ("[EXCUSE] :  Làm bài tập đi.", "EXCUSE", "Làm bài tập đi."),
            # Line prefix without brackets
            ("CLASSIFICATION: EXCUSE\nLười quá.", "EXCUSE", "Lười quá."),
            ("CLASSIFICATION: LEGITIMATE\nĐã duyệt.", "LEGITIMATE", "Đã duyệt."),
            ("classification: excuse: Tập đi.", "EXCUSE", "Tập đi."),
            ("Classification: Legitimate - Nghỉ đi.", "LEGITIMATE", "Nghỉ đi."),
            ("EXCUSE: Tập ngay đi.", "EXCUSE", "Tập ngay đi."),
            ("LEGITIMATE: Được nghỉ.", "LEGITIMATE", "Được nghỉ."),
            ("EXCUSE - Tập ngay.", "EXCUSE", "Tập ngay."),
            ("LEGITIMATE - Đồng ý.", "LEGITIMATE", "Đồng ý."),
            ("EXCUSE\nLười biếng quá.", "EXCUSE", "Lười biếng quá."),
            ("LEGITIMATE\nSốt cao nghỉ đi.", "LEGITIMATE", "Sốt cao nghỉ đi."),
            # Markdown wrapped tags
            ("**[EXCUSE]** Đừng viện cớ nữa.", "EXCUSE", "Đừng viện cớ nữa."),
            ("## [LEGITIMATE]\nNghỉ ngơi hồi phục.", "LEGITIMATE", "Nghỉ ngơi hồi phục."),
            # Fallback inline presence
            ("Tôi đánh giá đây là LEGITIMATE vì bạn ốm.", "LEGITIMATE", "vì bạn ốm."),
            ("Phản hồi: EXCUSE, bạn đang trì hoãn.", "EXCUSE", "bạn đang trì hoãn."),
        ],
    )
    def test_parse_skip_evaluation_varied_formats(
        self, raw_text: str, expected_class: str, expected_subtext: str
    ):
        classification, clean_text = parse_skip_evaluation(raw_text)
        assert classification == expected_class
        assert expected_subtext in clean_text
        assert not clean_text.startswith(f"[{expected_class}]")
        assert not clean_text.startswith(expected_class + ":")

    def test_parse_skip_evaluation_empty_and_whitespace(self):
        c1, t1 = parse_skip_evaluation("")
        assert c1 == "EXCUSE"
        assert t1 == ""

        c2, t2 = parse_skip_evaluation("   \n\t   ")
        assert c2 == "EXCUSE"
        assert t2 == ""

        c3, t3 = parse_skip_evaluation(None)  # type: ignore[arg-type]
        assert c3 == "EXCUSE"
        assert t3 == ""

    def test_parse_skip_evaluation_no_tags_uses_default(self):
        c, t = parse_skip_evaluation("Hôm nay bạn có thể nghỉ một hôm.", default_classification="LEGITIMATE")
        assert c == "LEGITIMATE"
        assert t == "Hôm nay bạn có thể nghỉ một hôm."

        c2, t2 = parse_skip_evaluation("Tập luyện ngay đi!", default_classification="EXCUSE")
        assert c2 == "EXCUSE"
        assert t2 == "Tập luyện ngay đi!"

    def test_parse_skip_evaluation_both_tags_present_bracket_precedence(self):
        # When model explains: "[EXCUSE] Đây không phải là LEGITIMATE lý do"
        c, t = parse_skip_evaluation("[EXCUSE] Đây không phải là một LEGITIMATE lý do.")
        assert c == "EXCUSE"

        c2, t2 = parse_skip_evaluation("[LEGITIMATE] Không phải là EXCUSE đâu.")
        assert c2 == "LEGITIMATE"


# =====================================================================
# 2. Stress Tests: Micro-Habit Routing
# =====================================================================

class TestStressMicroHabitRouting:
    """Empirically verifies 2-minute micro-habit routing across session domains."""

    @pytest.mark.parametrize(
        "session_input, expected_keywords",
        [
            ("gym", ["chống đẩy", "plank"]),
            ("GYM", ["chống đẩy", "plank"]),
            ("Gym Session", ["chống đẩy", "plank"]),
            ("gym_workout_mon", ["chống đẩy", "plank"]),
            ("toeic", ["Part 5", "Part 3"]),
            ("TOEIC", ["Part 5", "Part 3"]),
            ("TOEIC Study Session", ["Part 5", "Part 3"]),
            ("toeic_part_5", ["Part 5", "Part 3"]),
            ("major", ["IDE", "function", "commit"]),
            ("MAJOR", ["IDE", "function", "commit"]),
            ("Major Subject Study & Game Dev", ["IDE", "function", "commit"]),
            ("major_game_engine", ["IDE", "function", "commit"]),
        ],
    )
    def test_micro_habit_domain_routing(self, session_input: str, expected_keywords: List[str]):
        habit = get_micro_habit_for_session(session_input)
        assert isinstance(habit, str)
        assert len(habit) > 0
        for kw in expected_keywords:
            assert kw.lower() in habit.lower()

    @pytest.mark.parametrize("fallback_input", ["", "   ", "cooking", "unknown_session", None])
    def test_micro_habit_unknown_fallback(self, fallback_input: Any):
        habit = get_micro_habit_for_session(fallback_input)
        assert isinstance(habit, str)
        assert "2 phút" in habit or "khởi động" in habit


# =====================================================================
# 3. Stress Tests: classify_skip_reason_offline
# =====================================================================

class TestStressOfflineClassifier:
    """Empirically stress-tests offline keyword classifier boundary and adversarial inputs."""

    @pytest.mark.parametrize(
        "emergency_reason",
        [
            "bị sốt cao 39 độ",
            "nhập viện cấp cứu gấp",
            "tai nạn giao thông té xe gãy tay",
            "gia đình có đám tang",
            "khu trọ bị ngập lụt sau bão",
            "mất điện toàn khu vực không mở được máy tính",
            "bác sĩ yêu cầu nghỉ ngơi sau khám bệnh",
            "ngộ độc thực phẩm nôn mửa phải truyền nước",
            "bị đau ruột thừa cấp",
            "người thân qua đời",
        ],
    )
    def test_offline_emergencies_classified_legitimate(self, emergency_reason: str):
        cls, msg = classify_skip_reason_offline("gym", emergency_reason)
        assert cls == "LEGITIMATE"
        assert len(msg) > 0
        assert "chính đáng" in msg.lower() or "nghỉ ngơi" in msg.lower()

    @pytest.mark.parametrize(
        "excuse_reason",
        [
            "đang dở ván game liên quân với bạn",
            "hôm nay lười quá không muốn làm gì",
            "mệt mỏi tụt mood",
            "buồn ngủ quá để mai bù",
            "bận đi nhậu uống bia",
            "đi cafe hẹn hò với người yêu",
            "lướt tiktok với xem youtube quên giờ",
            "trời mưa ngại ra ngoài",
            "hết hứng học rồi",
            "dota 2 leo rank",
            "bắn valorant khuya",
        ],
    )
    def test_offline_excuses_classified_excuse(self, excuse_reason: str):
        cls, msg = classify_skip_reason_offline("gym", excuse_reason)
        assert cls == "EXCUSE"
        assert "micro-habit" in msg.lower() or "thuyết phục" in msg.lower()

    def test_offline_excuse_routes_micro_habit_by_session(self):
        # Gym excuse
        _, msg_gym = classify_skip_reason_offline("gym", "lười quá")
        assert "chống đẩy" in msg_gym or "plank" in msg_gym

        # TOEIC excuse
        _, msg_toeic = classify_skip_reason_offline("toeic", "buồn ngủ")
        assert "Part 5" in msg_toeic or "câu" in msg_toeic

        # Major excuse
        _, msg_major = classify_skip_reason_offline("major", "chơi game")
        assert "IDE" in msg_major and "function" in msg_major

    def test_offline_boundary_empty_and_whitespace(self):
        # Empty string
        c1, m1 = classify_skip_reason_offline("gym", "")
        assert c1 == "EXCUSE"
        assert len(m1) > 0

        # Whitespace
        c2, m2 = classify_skip_reason_offline("toeic", "     \n\t   ")
        assert c2 == "EXCUSE"
        assert len(m2) > 0

        # None
        c3, m3 = classify_skip_reason_offline("major", None)  # type: ignore[arg-type]
        assert c3 == "EXCUSE"
        assert len(m3) > 0

    def test_offline_extreme_length_inputs(self):
        # 10,000 characters excuse
        huge_excuse = "Lười quá " * 1250
        assert len(huge_excuse) >= 10000
        c_huge, m_huge = classify_skip_reason_offline("gym", huge_excuse)
        assert c_huge == "EXCUSE"
        assert len(m_huge) > 0

        # 10,000 characters emergency
        huge_emerg = ("Cần đi cấp cứu " * 700) + "bệnh viện sốt cao"
        c_emerg, m_emerg = classify_skip_reason_offline("major", huge_emerg)
        assert c_emerg == "LEGITIMATE"
        assert len(m_emerg) > 0

    def test_offline_emergency_priority_over_excuse_words(self):
        # Reason has both "mệt" (excuse) and "sốt" (emergency)
        c, m = classify_skip_reason_offline("gym", "Người mệt lả vì sốt cao 40 độ")
        assert c == "LEGITIMATE"


# =====================================================================
# 4. Stress Tests: Strict Return Typing and Contract Invariants
# =====================================================================

class TestStressStrictReturnTypes:
    """Verifies all skip evaluation methods return strictly Tuple[str, str]."""

    def test_parse_skip_evaluation_return_signature(self):
        test_inputs = [
            "[EXCUSE] test",
            "[LEGITIMATE] test",
            "CLASSIFICATION: EXCUSE\ntest",
            "",
            "   ",
            None,
            "No tags here",
        ]
        for inp in test_inputs:
            ret = parse_skip_evaluation(inp)  # type: ignore[arg-type]
            assert isinstance(ret, tuple), f"Expected tuple for input {inp!r}"
            assert len(ret) == 2
            cls, txt = ret
            assert isinstance(cls, str)
            assert cls in ("EXCUSE", "LEGITIMATE")
            assert isinstance(txt, str)

    def test_classify_skip_reason_offline_return_signature(self):
        sessions = ["gym", "toeic", "major", "unknown", ""]
        reasons = ["sốt", "lười", "", "   ", None, "A" * 5000]
        for s in sessions:
            for r in reasons:
                ret = classify_skip_reason_offline(s, r)  # type: ignore[arg-type]
                assert isinstance(ret, tuple)
                assert len(ret) == 2
                cls, txt = ret
                assert isinstance(cls, str)
                assert cls in ("EXCUSE", "LEGITIMATE")
                assert isinstance(txt, str)


# =====================================================================
# 5. Stress Tests: evaluate_skip_reason under Hostile Scenarios
# =====================================================================

@pytest.mark.asyncio
class TestStressEvaluateSkipReasonHostile:
    """Empirically stress-tests evaluate_skip_reason with mocked API hostility."""

    async def test_evaluate_handles_none_and_empty_gemini_response(self):
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()

        # Model returns empty text
        empty_resp = MagicMock()
        empty_resp.text = ""
        mock_client.aio.models.generate_content = AsyncMock(return_value=empty_resp)

        coach = AICoachService(api_key="mock", client=mock_client)

        # Excuse reason with empty API response -> falls back to offline excuse
        cls1, txt1 = await coach.evaluate_skip_reason("gym", "lười quá")
        assert cls1 == "EXCUSE"
        assert "chống đẩy" in txt1 or "plank" in txt1

        # Legitimate reason with empty API response -> falls back to offline legitimate
        cls2, txt2 = await coach.evaluate_skip_reason("gym", "sốt cao cấp cứu")
        assert cls2 == "LEGITIMATE"

    async def test_evaluate_handles_api_errors_resiliently(self):
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()

        error_scenarios = [
            asyncio.TimeoutError("Timeout after 15s"),
            errors.APIError(code=429, response_json={"error": {"message": "Rate limit exceeded"}}),
            errors.APIError(code=500, response_json={"error": {"message": "Internal server error"}}),
            ConnectionError("Network is down"),
            RuntimeError("Unexpected unhandled runtime failure"),
        ]

        coach = AICoachService(api_key="mock", client=mock_client)

        for err in error_scenarios:
            mock_client.aio.models.generate_content.side_effect = err
            # Must NEVER raise exception out of evaluate_skip_reason
            cls, txt = await coach.evaluate_skip_reason("toeic", "đang chơi game")
            assert cls == "EXCUSE"
            assert isinstance(txt, str)
            assert len(txt) > 0
            assert "Part 5" in txt or "câu" in txt

    async def test_evaluate_handles_adversarial_model_output(self):
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()

        coach = AICoachService(api_key="mock", client=mock_client)

        # Output with lower case bracket and Markdown
        resp1 = MagicMock()
        resp1.text = "**[excuse]** Đi tập ngay, không viện cớ."
        mock_client.aio.models.generate_content = AsyncMock(return_value=resp1)

        c1, t1 = await coach.evaluate_skip_reason("gym", "mệt")
        assert c1 == "EXCUSE"
        assert "[excuse]" not in t1.lower()

        # Output with multi-line prefix
        resp2 = MagicMock()
        resp2.text = "CLASSIFICATION: LEGITIMATE\nĐã xác nhận tình trạng cấp cứu. Nghỉ ngơi mau."
        mock_client.aio.models.generate_content = AsyncMock(return_value=resp2)

        c2, t2 = await coach.evaluate_skip_reason("gym", "cấp cứu")
        assert c2 == "LEGITIMATE"
        assert "CLASSIFICATION" not in t2
