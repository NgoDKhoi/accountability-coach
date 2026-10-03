"""Adversarial and Empirical Stress Test Suite for Milestone 2 (AICoachService).

Empirically challenges:
1. Multi-turn sliding context window invariants over 20, 50, and 100 turns:
   len(coach.context_window) <= history_limit (10).
2. FIFO eviction and leading model turn prevention: payloads sent to Gemini
   must never start with role='model' even when earlier user messages are evicted.
3. Strict alternating role structure (user, model, user, model) across long sessions.
4. Context reset idempotency across empty, partially full, and full deques.
5. Absolute isolation of self._history against non-chat methods (get_congratulation,
   evaluate_skip_reason) under normal, empty, and error conditions.
6. Edge case payloads, custom window sizes (2, 6, 8, 10), flaky network simulations,
   parser attack vectors, and immutability of the context_window property.
"""

from __future__ import annotations

import asyncio
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from google.genai import errors, types

from src.coach import (
    AICoachService,
    classify_skip_reason_offline,
    get_micro_habit_for_session,
    parse_skip_evaluation,
)
from src.config import DEFAULT_FALLBACKS, DEFAULT_PROMPTS, DEFAULT_SYSTEM_PROMPT


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_genai_factory():
    """Returns a factory that creates mocked Gemini response objects."""
    def _create(text: str = "Tập luyện ngay đi!"):
        resp = MagicMock()
        resp.text = text
        candidate = MagicMock()
        candidate.content.parts = [MagicMock(text=text)]
        resp.candidates = [candidate]
        return resp
    return _create


@pytest.fixture
def mock_genai_client(mock_genai_factory):
    """Fixture returning a mock GenAI client with async models namespace."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=mock_genai_factory("Coach phản hồi kỷ luật.")
    )
    return client


@pytest.fixture
def standard_coach(mock_genai_client, valid_yaml_dict):
    """Returns an AICoachService instance with default history_limit=10."""
    return AICoachService(
        api_key="adversarial-test-key",
        model_name="gemini-2.5-flash",
        config=valid_yaml_dict,
        client=mock_genai_client,
    )


# =====================================================================
# Test Class 1: Multi-Turn Sliding Context Window Stress (20, 50, 100 turns)
# =====================================================================

@pytest.mark.asyncio
class TestMultiTurnSlidingWindowInvariants:
    """Empirical challenge of multi-turn chat invariants over large turn counts."""

    @pytest.mark.parametrize("total_turns", [20, 50, 100])
    async def test_multiturn_chat_sliding_window_invariants(
        self, total_turns: int, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Stress-tests multi-turn chat over 20, 50, and 100 turns.

        Verifies:
        - len(coach.context_window) <= 10 holds at every single turn.
        - len(coach._history) <= 10 holds at every single turn.
        - Once history fills (turn >= 5), length is exactly 10 after each turn.
        - Payloads passed to generate_content strictly start with role='user'.
        - Payloads passed to generate_content strictly alternate roles.
        - coach.context_window strictly alternates roles (user, model, user, model).
        - FIFO eviction correctly purges old turns and preserves the latest turns.
        """
        history_limit = standard_coach.history_limit
        assert history_limit == 10

        for turn_idx in range(total_turns):
            user_msg = f"User turn {turn_idx}: tập luyện thế nào?"
            expected_reply = f"Coach turn {turn_idx}: kỷ luật là sức mạnh!"
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(expected_reply)

            # Execute chat turn
            reply = await standard_coach.chat(user_msg)
            assert reply == expected_reply

            # 1. Invariant: length bounds
            current_window = standard_coach.context_window
            assert len(current_window) <= history_limit, (
                f"Turn {turn_idx}: context_window length {len(current_window)} exceeded {history_limit}"
            )
            assert len(standard_coach._history) <= history_limit

            # Expected length: min(2 * (turn_idx + 1), history_limit)
            expected_len = min(2 * (turn_idx + 1), history_limit)
            assert len(current_window) == expected_len, (
                f"Turn {turn_idx}: expected window len {expected_len}, got {len(current_window)}"
            )

            # 2. Invariant: inspect payload passed to Gemini client
            call_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
            payload_contents = call_kwargs.get("contents")
            assert isinstance(payload_contents, list), "Payload contents must be a list"
            assert len(payload_contents) > 0, "Payload contents must not be empty"

            # Must start strictly with role='user'
            assert payload_contents[0].role == "user", (
                f"Turn {turn_idx}: Gemini payload MUST start with role 'user', got '{payload_contents[0].role}'"
            )

            # Must end with role='user' because model has not replied yet
            assert payload_contents[-1].role == "user", (
                f"Turn {turn_idx}: Gemini payload MUST end with role 'user' (current turn user prompt)"
            )

            # Must strictly alternate roles in request payload
            for i in range(len(payload_contents) - 1):
                assert payload_contents[i].role != payload_contents[i + 1].role, (
                    f"Turn {turn_idx}: consecutive identical roles at index {i} in request payload: "
                    f"{payload_contents[i].role} followed by {payload_contents[i + 1].role}"
                )

            # 3. Invariant: context_window role structure
            for i, (role, text) in enumerate(current_window):
                expected_role = "user" if i % 2 == 0 else "model"
                assert role == expected_role, (
                    f"Turn {turn_idx}: context_window[{i}] role was '{role}', expected '{expected_role}'"
                )

            # 4. Invariant: latest message is in window
            assert current_window[-1][1] == expected_reply
            assert current_window[-2][1] == user_msg

            # 5. Invariant: oldest message verified against FIFO eviction
            if turn_idx >= 5:
                # 10 messages = 5 user + 5 model turns
                # Oldest user message should be from turn (turn_idx - 4)
                oldest_turn_num = turn_idx - 4
                oldest_user_text = current_window[0][1]
                assert f"User turn {oldest_turn_num}:" in oldest_user_text, (
                    f"Turn {turn_idx}: expected oldest message to be from turn {oldest_turn_num}, got: {oldest_user_text}"
                )
                # Messages older than (turn_idx - 4) MUST NOT be present
                if oldest_turn_num > 0:
                    evicted_turn_num = oldest_turn_num - 1
                    for _, msg_text in current_window:
                        assert f"User turn {evicted_turn_num}:" not in msg_text

    async def test_fifo_eviction_boundary_exact_step_inspection(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Micro-steps through turns 4, 5, 6, 7 to observe the exact deque eviction boundary."""
        for t in range(5):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"R{t}")
            await standard_coach.chat(f"U{t}")

        # At turn 4 (5th turn): history has exactly 10 items: U0, R0, U1, R1, U2, R2, U3, R3, U4, R4
        assert len(standard_coach.context_window) == 10
        assert standard_coach.context_window[0] == ("user", "U0")
        assert standard_coach.context_window[-1] == ("model", "R4")

        # Now execute turn 5 (6th turn: U5, R5)
        # Adding U5 to maxlen=10 deque evicts U0! Leftmost becomes R0 (model).
        # Internal sanitation must pop R0 immediately.
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory("R5")
        await standard_coach.chat("U5")

        # After U5 & R5:
        # History must contain: U1, R1, U2, R2, U3, R3, U4, R4, U5, R5 (10 items)
        assert len(standard_coach.context_window) == 10
        assert standard_coach.context_window[0] == ("user", "U1")
        assert standard_coach.context_window[1] == ("model", "R1")
        assert standard_coach.context_window[-2] == ("user", "U5")
        assert standard_coach.context_window[-1] == ("model", "R5")

        # Verify payload sent to Gemini during turn 5 did NOT contain R0 or start with model
        call_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        sent_contents = call_kwargs["contents"]
        assert sent_contents[0].role == "user"
        assert sent_contents[0].parts[0].text == "U1"
        assert len(sent_contents) == 9  # [U1, R1, U2, R2, U3, R3, U4, R4, U5]


# =====================================================================
# Test Class 2: Context Reset Idempotency (Task 3)
# =====================================================================

@pytest.mark.asyncio
class TestContextResetIdempotency:
    """Empirically tests clear_context() idempotency and stability across all states."""

    async def test_clear_context_idempotent_on_brand_new_instance(self, standard_coach):
        """Calling clear_context() on empty history repeatedly must never fail."""
        assert len(standard_coach._history) == 0
        assert len(standard_coach.context_window) == 0

        for _ in range(10):
            standard_coach.clear_context()
            assert len(standard_coach._history) == 0
            assert len(standard_coach.context_window) == 0

    async def test_clear_context_idempotent_on_partially_full_deque(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Tests clearing deques with 2, 4, 6 messages, repeated multiple times."""
        for turns_to_fill in [1, 2, 3]:
            for t in range(turns_to_fill):
                mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"Ans {t}")
                await standard_coach.chat(f"Question {t}")

            assert len(standard_coach.context_window) == turns_to_fill * 2

            # Repeated clearing
            standard_coach.clear_context()
            assert len(standard_coach.context_window) == 0
            standard_coach.clear_context()
            assert len(standard_coach.context_window) == 0
            standard_coach.clear_context()
            assert len(standard_coach.context_window) == 0

    async def test_clear_context_idempotent_on_full_deque(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Tests clearing a saturated deque (10 messages) repeatedly."""
        for t in range(10):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"Ans {t}")
            await standard_coach.chat(f"Question {t}")

        assert len(standard_coach.context_window) == 10

        # Repeated clearing
        for _ in range(5):
            standard_coach.clear_context()
            assert len(standard_coach._history) == 0
            assert len(standard_coach.context_window) == 0

    async def test_chat_resumes_cleanly_after_reset(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Verifies new conversation after clear_context() starts from scratch."""
        # Run 10 turns
        for t in range(10):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"OldAns {t}")
            await standard_coach.chat(f"OldQ {t}")

        standard_coach.clear_context()

        # New conversation
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory("FreshAns")
        reply = await standard_coach.chat("FreshQ")
        assert reply == "FreshAns"

        assert len(standard_coach.context_window) == 2
        assert standard_coach.context_window[0] == ("user", "FreshQ")
        assert standard_coach.context_window[1] == ("model", "FreshAns")

        # Payload sent to API must only contain FreshQ
        call_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]
        assert len(contents) == 1
        assert contents[0].role == "user"
        assert contents[0].parts[0].text == "FreshQ"


# =====================================================================
# Test Class 3: History Isolation Against Non-Chat Methods (Task 4)
# =====================================================================

@pytest.mark.asyncio
class TestHistoryIsolationAgainstNonChatMethods:
    """Verifies get_congratulation and evaluate_skip_reason never pollute self._history."""

    async def test_get_congratulation_never_pollutes_history(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Repeatedly invokes get_congratulation across streaks and session types."""
        # 1. On empty history
        assert len(standard_coach._history) == 0
        for s_type in ["gym", "toeic", "major", "unknown"]:
            for streak in [1, 5, 21, 100]:
                mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(
                    f"Praise for {s_type} {streak}"
                )
                res = await standard_coach.get_congratulation(s_type, streak)
                assert len(res) > 0
                assert len(standard_coach._history) == 0
                assert len(standard_coach.context_window) == 0

        # 2. On populated history (6 messages)
        for t in range(3):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"A{t}")
            await standard_coach.chat(f"Q{t}")

        assert len(standard_coach.context_window) == 6
        snapshot_before = list(standard_coach.context_window)

        for streak in [2, 10, 50]:
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory("Praise")
            await standard_coach.get_congratulation("gym", streak)

            assert standard_coach.context_window == snapshot_before
            assert len(standard_coach._history) == 6

    async def test_evaluate_skip_reason_never_pollutes_history(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Repeatedly invokes evaluate_skip_reason across excuse and legitimate cases."""
        # 1. On empty history
        assert len(standard_coach._history) == 0
        reasons = [
            ("[EXCUSE] Làm việc đi!", "Mệt quá muốn chơi game"),
            ("[LEGITIMATE] Đã duyệt.", "Sốt 40 độ cấp cứu"),
            ("[EXCUSE] Hít đất 5 cái", "Mai học bù"),
        ]
        for tag, reason_text in reasons:
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(tag)
            c, t = await standard_coach.evaluate_skip_reason("gym", reason_text)
            assert c in ("EXCUSE", "LEGITIMATE")
            assert len(standard_coach._history) == 0
            assert len(standard_coach.context_window) == 0

        # 2. On populated history (10 messages)
        for turn in range(5):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"A{turn}")
            await standard_coach.chat(f"Q{turn}")

        assert len(standard_coach.context_window) == 10
        snapshot_before = list(standard_coach.context_window)

        for tag, reason_text in reasons:
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(tag)
            await standard_coach.evaluate_skip_reason("toeic", reason_text)

            assert standard_coach.context_window == snapshot_before
            assert len(standard_coach._history) == 10

    async def test_non_chat_methods_on_api_errors_do_not_pollute_history(
        self, standard_coach, mock_genai_client
    ):
        """Verifies that API timeouts, 500s, 429s in praise/evaluator do NOT pollute history."""
        # Populate with 4 messages
        mock_genai_client.aio.models.generate_content.return_value = MagicMock(text="Chat OK")
        await standard_coach.chat("Hi")
        await standard_coach.chat("Ready")
        assert len(standard_coach.context_window) == 4
        snapshot = list(standard_coach.context_window)

        # Inject various errors into praise
        for err in [
            asyncio.TimeoutError(),
            errors.APIError(code=500, response_json={}),
            errors.APIError(code=429, response_json={}),
            ConnectionResetError(),
        ]:
            mock_genai_client.aio.models.generate_content.side_effect = err
            praise = await standard_coach.get_congratulation("gym", 5)
            assert len(praise) > 0
            assert standard_coach.context_window == snapshot

            eval_res = await standard_coach.evaluate_skip_reason("gym", "Lười quá")
            assert eval_res[0] == "EXCUSE"
            assert standard_coach.context_window == snapshot


# =====================================================================
# Test Class 4: Network Flakiness and Alternating Role Invariant
# =====================================================================

@pytest.mark.asyncio
class TestNetworkFlakinessAndInvariants:
    """Verifies that intermittent API errors do not corrupt the alternating role sequence."""

    async def test_flaky_network_chat_preserves_role_alternation(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        """Simulates intermittent failures: Turn 0 OK, Turn 1 Timeout, Turn 2 500, Turn 3 OK...

        Because coach.chat() records the fallback response into history on error,
        every turn produces exactly one user turn and one model turn.
        Thus, role alternation must never be broken even during network outages.
        """
        for t in range(20):
            if t % 3 == 1:
                mock_genai_client.aio.models.generate_content.side_effect = asyncio.TimeoutError()
            elif t % 3 == 2:
                mock_genai_client.aio.models.generate_content.side_effect = errors.APIError(
                    code=500, response_json={}
                )
            else:
                mock_genai_client.aio.models.generate_content.side_effect = None
                mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"Reply {t}")

            reply = await standard_coach.chat(f"User message {t}")
            assert len(reply) > 0

            # Window length must remain <= 10
            window = standard_coach.context_window
            assert len(window) <= 10

            # Every entry must strictly alternate user, model
            for idx, (role, text) in enumerate(window):
                expected = "user" if idx % 2 == 0 else "model"
                assert role == expected, (
                    f"Turn {t}, idx {idx}: expected {expected}, got {role}"
                )


# =====================================================================
# Test Class 5: Custom History Limits & Boundary Sizes
# =====================================================================

@pytest.mark.asyncio
class TestCustomContextWindowLimits:
    """Tests various history_limit settings (2, 6, 8, 12)."""

    @pytest.mark.parametrize("limit", [2, 6, 8, 12])
    async def test_custom_window_size_invariants(
        self, limit: int, mock_genai_client, mock_genai_factory, valid_yaml_dict
    ):
        cfg = dict(valid_yaml_dict)
        cfg["context_window_size"] = limit
        coach = AICoachService(
            api_key="mock",
            config=cfg,
            client=mock_genai_client,
        )
        assert coach.history_limit == limit

        for t in range(25):
            mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory(f"Rep {t}")
            await coach.chat(f"Msg {t}")

            window = coach.context_window
            assert len(window) <= limit
            assert len(coach._history) <= limit

            # Request payload must start with user
            call_kwargs = mock_genai_client.aio.models.generate_content.call_args.kwargs
            payload = call_kwargs["contents"]
            assert payload[0].role == "user"
            assert payload[-1].role == "user"


# =====================================================================
# Test Class 6: Context Window Immutability & Defensive Copies
# =====================================================================

class TestContextWindowImmutability:
    """Verifies that callers modifying coach.context_window cannot corrupt internal state."""

    @pytest.mark.asyncio
    async def test_external_mutation_of_context_window_does_not_affect_history(
        self, standard_coach, mock_genai_client, mock_genai_factory
    ):
        mock_genai_client.aio.models.generate_content.return_value = mock_genai_factory("R1")
        await standard_coach.chat("U1")

        window = standard_coach.context_window
        assert len(window) == 2

        # Malicious external append / clear
        window.append(("hacker_role", "malicious_payload"))
        window.clear()

        # Internal state must remain completely unaffected
        window_after = standard_coach.context_window
        assert len(window_after) == 2
        assert window_after[0] == ("user", "U1")
        assert window_after[1] == ("model", "R1")


# =====================================================================
# Test Class 7: Skip Reason Parsing & Offline Keyword Robustness
# =====================================================================

class TestSkipReasonParsingAdversarial:
    """Stress-tests parser and offline classifier against ambiguous, tagged, and adversarial inputs."""

    @pytest.mark.parametrize(
        "raw_text, expected_class, expected_substring",
        [
            ("[EXCUSE] Đi ngủ mai làm bù", "EXCUSE", "Đi ngủ mai làm bù"),
            ("[LEGITIMATE] Bị ngã xe gãy tay", "LEGITIMATE", "Bị ngã xe gãy tay"),
            ("CLASSIFICATION: EXCUSE - Đang chơi Dota", "EXCUSE", "Đang chơi Dota"),
            ("CLASSIFICATION: LEGITIMATE\nĐi viện khám bệnh", "LEGITIMATE", "Đi viện khám bệnh"),
            ("Lý do này là LEGITIMATE vì bác sĩ yêu cầu nằm viện", "LEGITIMATE", "bác sĩ yêu cầu nằm viện"),
            ("Hoàn toàn là EXCUSE vì lười biếng", "EXCUSE", "lười biếng"),
            ("[excuse] viết thường vẫn nhận diện", "EXCUSE", "viết thường"),
            ("[legitimate] viết thường hợp lệ", "LEGITIMATE", "viết thường"),
            ("", "EXCUSE", ""),
            ("   ", "EXCUSE", ""),
            ("Không có tag nào hết, chỉ là lời nói suông", "EXCUSE", "Không có tag nào hết"),
        ],
    )
    def test_parse_skip_evaluation_variations(
        self, raw_text: str, expected_class: str, expected_substring: str
    ):
        classification, clean_text = parse_skip_evaluation(raw_text)
        assert classification == expected_class
        assert expected_substring in clean_text
        # Prefix tags must be cleaned
        assert "[EXCUSE]" not in clean_text
        assert "[LEGITIMATE]" not in clean_text

    @pytest.mark.parametrize(
        "reason, expected_class",
        [
            ("Sốt cao 39 độ", "LEGITIMATE"),
            ("bị tai nạn giao thông té xe", "LEGITIMATE"),
            ("Cấp cứu bệnh viện Bạch Mai", "LEGITIMATE"),
            ("Gia đình có đám tang", "LEGITIMATE"),
            ("Nhà mất điện sập nguồn cả khu", "LEGITIMATE"),
            ("Bị ngộ độc thực phẩm", "LEGITIMATE"),
            ("Lười quá không muốn làm", "EXCUSE"),
            ("Đang chơi game Dota với bạn bè", "EXCUSE"),
            ("Buồn ngủ để mai làm bù", "EXCUSE"),
            ("Trời mưa hết hứng tập", "EXCUSE"),
            ("Hẹn hò đi uống cafe", "EXCUSE"),
            ("Lướt tiktok quên giờ", "EXCUSE"),
        ],
    )
    def test_offline_keyword_classifier(self, reason: str, expected_class: str):
        c, msg = classify_skip_reason_offline("gym", reason)
        assert c == expected_class
        assert len(msg) > 0


# =====================================================================
# Test Class 8: Micro-Habit Tailoring Completeness
# =====================================================================

class TestMicroHabitTailoring:
    """Verifies that all session types map to appropriate domain micro-habits."""

    @pytest.mark.parametrize(
        "session_type, expected_fragment",
        [
            ("gym", "chống đẩy"),
            ("GYM", "plank"),
            ("toeic", "Part 5"),
            ("TOEIC_READING", "Part 5"),
            ("major", "IDE"),
            ("MAJOR_DEV", "function"),
            ("major_game_dev", "IDE"),
            ("random_session", "2 phút"),
        ],
    )
    def test_micro_habit_session_mapping(self, session_type: str, expected_fragment: str):
        habit = get_micro_habit_for_session(session_type)
        assert expected_fragment.lower() in habit.lower()
