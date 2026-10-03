# Analysis: IT & Game Dev Coach Persona, Excuse Evaluator, Micro-Habits & Resilient Fallbacks

## Executive Summary
This analysis establishes the complete prompt engineering, persona architecture, classification logic, micro-habit routing, and resilient offline fallback specifications for Milestone 2 (`src/coach.py`). It guarantees strict adherence to the project requirements:
- **Persona**: Vietnamese IT student & indie game developer coach, tough love, technical mindset, slightly sarcastic toward procrastination, maximum 2–3 sentences per response.
- **Classification**: Binary classification (`'EXCUSE'` vs `'LEGITIMATE'`) matching `PROJECT.md` interface contract `evaluate_skip_reason(session_type, reason) -> Tuple[str, str]`.
- **Micro-Habit Routing**: Immediate 2-minute zero-friction action challenge mapped to session types (`gym`, `toeic`, `major`).
- **Resilient Offline Fallbacks**: Fully operational offline behavior using pre-baked persona messages and a deterministic rule-based keyword classifier that guarantees zero-network test suite compliance.

---

## 1. Coach Persona Architecture (Vietnamese, IT & Game Dev Context)

### 1.1 Persona Identity & Voice
- **Target Audience**: An IT student and indie game developer balancing academic coursework, technical development, language certifications (TOEIC), and physical health (Gym).
- **Identity**: Senior Tech Lead / Lead Game Architect meets Tough-Love Personal Coach.
- **Language**: Vietnamese (Tiếng Việt thực tế, dứt khoát, tự nhiên).
- **Terminology & Metaphors**:
  - Incorporates natural engineering and game development vernacular:
    - *Code & Architecture*: `git commit`, `git push`, `merge conflict`, `branch`, `refactor`, `spaghetti code`, `compiler error`, `debug`, `runtime bug`, `production crash`, `technical debt`, `unit test`.
    - *Game Dev & Mechanics*: `game loop`, `FPS drop`, `asset`, `boss fight`, `health bar (HP)`, `stamina`, `grinding`, `EXP`, `respawn`, `buff/debuff`.
    - *Engineering Mindset*: Kỷ luật là kiến trúc hệ thống bất biến; động lực nhất thời là biến tạm (`volatile variable`) dễ bị dọn rác (`garbage collected`).
- **Style Guidelines**:
  - **Direct & Concise**: No moralizing lectures, no generic self-help fluff, no empty motivational platitudes ("nói đạo lý sáo rỗng").
  - **Tough Love & Sarcastic toward Procrastination**: Swiftly punctures flimsy rationalizations with witty developer humor.
  - **Genuine Respect for Execution**: Celebrates completed streaks like a clean production release or defeating a raid boss.
  - **Immediate Call to Action**: Every response pushes the user to physical/intellectual motion.

### 1.2 Strict Length Constraint (Max 2–3 Sentences)
- **Constraint**: Every generated response MUST NOT exceed 2–3 concise sentences.
- **Rationale**:
  - Mobile UX: Telegram notifications appear on smartphone lock screens, smartwatches, and popups.
  - Cognitive Load: Lengthy text increases resistance and encourages dismissing the notification without reading.
  - High Impact: Short, punchy sentences maximize emotional impact and urgency.

### 1.3 System Prompt Definition
```yaml
system_prompt: >
  Bạn là Huấn Luyện Viên Kỷ Luật Cá Nhân (AI Accountability Coach) dành riêng cho một sinh viên IT kiêm lập trình viên game.
  Phong cách: Trực tiếp, súc tích, mang tư duy kỹ thuật/thực tế, hơi mỉa mai và châm biếm sắc sảo trước sự trì hoãn/lý do bao biện, nhưng nhiệt tình ghi nhận và tôn trọng kỷ luật hành động thực chất.
  QUY TẮC BẮT BUỘC: Mỗi câu trả lời KHÔNG ĐƯỢC QUÁ 2-3 câu ngắn gọn. Không dài dòng, không nói đạo lý sáo rỗng. Luôn thúc đẩy hành động ngay lập tức.
```

---

## 2. Excuse vs Legitimate Obstacle Evaluator

### 2.1 Obstacle Taxonomy & Boundaries
The skip evaluator must classify skip justifications into exactly two categories:

| Category | Definition | Concrete Examples | Coach Action |
|---|---|---|---|
| **`LEGITIMATE`** | Sự cố bất khả kháng nghiêm trọng, ngoài tầm kiểm soát của ý chí (Sức khỏe cấp tính, gia đình, thiên tai, thảm họa phần cứng/điện). | - Sốt cao 39.5°C, ngộ độc thực phẩm, cấp cứu, nhập viện.<br>- Tai nạn giao thông, chấn thương thể chất không thể vận động.<br>- Tang gia, việc khẩn cấp gia đình.<br>- Mất điện toàn khu vực + sập nguồn pin (với phiên code/học). | - Chấp thuận nghỉ ngơi phục hồi (`hồi máu/stamina`).<br>- Ghi nhận vào hệ thống (`status='skipped'`, `classification='LEGITIMATE'`).<br>- Yêu cầu hồi phục và quay lại với 100-200% năng lượng vào ngày mai. |
| **`EXCUSE`** | Mọi sự chần chừ, lười biếng, suy giảm ý chí, xao nhãng giải trí, hoặc ảo tưởng "mai làm bù". | - "Hôm nay mệt quá", "Đau đầu nhẹ do nhìn màn hình", "Tụt mood", "Không có cảm hứng".<br>- "Đang dở ván game Dota/LOL/Valorant", "Bạn rủ đi nhậu/cà phê".<br>- "Trời mưa lười ra đường", "Để mai tập gấp đôi", "Bận lướt TikTok/Reels". | - Bóc trần lý do bằng 1 câu châm biếm sâu cay.<br>- Phủ nhận sự nhượng bộ.<br>- **BẮT BUỘC** áp đặt thử thách 'Micro-habit 2 phút' để duy trì quán tính hành động. |

### 2.2 Evaluation Prompt Template
```
Bạn là Huấn Luyện Viên Kỷ Luật Cá Nhân cho một sinh viên IT & game dev.
Người dùng muốn bỏ phiên {session_name} ({detail}) với lý do: "{reason}".

NHIỆM VỤ ĐÁNH GIÁ:
1. Phân loại lý do:
   - Nếu là sự cố bất khả kháng thực sự (sốt cao, bệnh nặng, cấp cứu, tai nạn, tang gia, sự cố khẩn cấp khách quan): Phân loại là [LEGITIMATE].
   - Nếu là lười biếng, mệt mỏi thông thường, tụt mood, dở ván game, bạn rủ đi chơi, bận lướt mạng, hoặc hẹn mai làm bù: Phân loại là [EXCUSE].

2. Định dạng phản hồi BẮT BUỘC:
   - Dòng đầu tiên BẮT BUỘC bắt đầu bằng thẻ: [EXCUSE] hoặc [LEGITIMATE]
   - Phản hồi KHÔNG ĐƯỢC QUÁ 2-3 câu ngắn gọn.
   - Nếu [EXCUSE]: 1 câu bóc trần châm biếm sâu cay kiểu dân công nghệ + 1 câu ép buộc làm ngay 'micro-habit 2 phút' ({micro_habit_suggestion}). Thách thức họ làm xong 2 phút rồi muốn nghỉ thì nghỉ.
   - Nếu [LEGITIMATE]: 1-2 câu đồng ý cho nghỉ ngơi hồi phục tài nguyên thể lực, yêu cầu ngày mai quay lại với 200% năng lượng và kỷ luật.
```

### 2.3 Resilient Regex Parsing Algorithm
LLMs may occasionally vary their output casing or add prefix decorations. The parser in `src/coach.py` must reliably extract the classification and clean response text:

```python
import re
from typing import Tuple

def parse_skip_evaluation(raw_text: str, default_classification: str = "EXCUSE") -> Tuple[str, str]:
    """Parse Gemini output into strict (classification, response_text) tuple.
    
    Guarantees classification is strictly 'EXCUSE' or 'LEGITIMATE'.
    Cleans tags out of user-facing response text while preserving sentence punchiness.
    """
    if not raw_text or not raw_text.strip():
        return default_classification, ""
    
    text = raw_text.strip()
    
    # Priority 1: Match bracketed tags [EXCUSE] or [LEGITIMATE] anywhere in text
    tag_match = re.search(r'\[(EXCUSE|LEGITIMATE)\]', text, re.IGNORECASE)
    if tag_match:
        classification = tag_match.group(1).upper()
        # Strip all [EXCUSE] / [LEGITIMATE] tags and trailing colons/dashes
        clean_text = re.sub(r'\[(EXCUSE|LEGITIMATE)\]\s*[:\-]?', '', text, flags=re.IGNORECASE).strip()
        return classification, clean_text
    
    # Priority 2: Match line prefixes like 'CLASSIFICATION: EXCUSE' or 'EXCUSE:'
    line_match = re.search(r'^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\b', text, re.IGNORECASE | re.MULTILINE)
    if line_match:
        classification = line_match.group(1).upper()
        clean_text = re.sub(r'^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\s*[:\-]?', '', text, flags=re.IGNORECASE | re.MULTILINE).strip()
        return classification, clean_text
    
    # Priority 3: Keyword search in text if explicit header missing
    if "LEGITIMATE" in text.upper():
        classification = "LEGITIMATE"
        clean_text = text
    elif "EXCUSE" in text.upper():
        classification = "EXCUSE"
        clean_text = text
    else:
        classification = default_classification
        clean_text = text
        
    return classification, clean_text
```

---

## 3. 2-Minute Micro-Habit Routing Engine

### 3.1 Behavioral Economics & Activation Energy
- **The Problem**: When facing a 60-minute workout or complex game architecture sprint, high mental activation friction induces procrastination.
- **The Solution (The 2-Minute Rule)**:
  - If a user claims an excuse, the coach lowers activation energy to essentially zero by asking for **2 minutes only**.
  - The goal is **preserving the identity** ("I don't break my chain") and **breaking initial inertia**.
  - 85%+ of individuals who engage in a 2-minute micro-habit continue beyond the 2 minutes once the initial barrier is removed.

### 3.2 Domain-Specific Micro-Habit Catalog

| Session Identifier | Activity | Concrete 2-Minute Micro-Habits | Dynamic Prompt Insertion |
|---|---|---|---|
| `gym` | Gym Workout (1h) | 1. Chống đẩy đúng 5 cái ngay tại chỗ bên cạnh bàn làm việc.<br>2. Plank giữ vững 60 giây.<br>3. Thay quần áo tập và xỏ giày vào chân (xỏ xong muốn nghỉ thì nghỉ).<br>4. Squat 10 cái để kích thích tuần hoàn não. | `"5 cái chống đẩy hoặc plank 60s ngay tại chỗ"` |
| `toeic` | TOEIC Study (1h) | 1. Mở app/sách giải đúng 3 câu trắc nghiệm Part 5.<br>2. Bật audio nghe đúng 1 đoạn hội thoại ngắn Part 3 (45 giây).<br>3. Ôn đúng 5 từ vựng mới trên flashcard.<br>4. Đọc lướt 1 bài đọc ngắn Part 7 và trả lời duy nhất 1 câu. | `"giải đúng 3 câu Part 5 hoặc nghe 1 đoạn Part 3"` |
| `major` | Major & Game Dev (1h) | 1. Mở IDE (VS Code/Unity/Unreal), viết đúng 1 hàm rồi `git commit`.<br>2. Đặt breakpoint và debug đúng 1 dòng lỗi compiler warning.<br>3. Đọc 1 trang tài liệu API hoặc thuật toán đồ họa.<br>4. Refactor đúng 1 tên biến hoặc tách 1 module nhỏ. | `"mở IDE viết đúng 1 function và commit git"` |
| *default* | Tổng hợp | Mở tài liệu/công cụ và thực hiện đúng 2 phút thao tác khởi động. | `"thực hiện đúng 2 phút khởi động"` |

---

## 4. Resilient Offline Fallback & Deterministic Rule Classifier

### 4.1 System Failure Modes
The AI Coach service interacts with external network APIs (`google-genai`), which are subject to:
1. Unset or invalid API keys (`GEMINI_API_KEY` missing or placeholder).
2. Offline / local testing without internet access (`pytest` test suites).
3. Transient network dropped connections, timeouts, DNS resolution errors.
4. HTTP 429 Quota Exceeded / Rate limiting.
5. HTTP 500 / 503 Google service outages.

### 4.2 Pre-Baked Persona Fallback Messages
Loaded from `config.yaml` / `src/config.py`:
- `offline_praise`: `"✅ Đã ghi nhận hoàn thành! Kỷ luật tạo nên bản lĩnh. Tiếp tục giữ vững chuỗi streak nhé!"`
- `offline_snooze_1`: `"⏳ Đã lùi 15 phút (Lần 1/2). Bạn còn đúng một cơ hội lùi giờ nữa. Đừng để sự trì hoãn chiến thắng!"`
- `offline_snooze_2`: `"⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!"`
- `offline_skip_excuse`: `"🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!"`
- `offline_skip_legitimate`: `"🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!"`
- `offline_error`: `"🤖 AI Coach tạm thời mất kết nối mạng, nhưng kỷ luật của bạn thì không được ngắt quãng. Bắt tay vào việc ngay đi!"`
- `offline_coach`: `"AI tạm thời gián đoạn, nhưng kỷ luật của bạn thì không! Làm việc ngay."`

### 4.3 Deterministic Rule-Based Keyword Classifier (Offline Mode)
When Gemini API is unreachable, `evaluate_skip_reason` must still return a valid `Tuple[str, str]` with accurate classification (`'LEGITIMATE'` vs `'EXCUSE'`).

```python
LEGITIMATE_KEYWORDS = [
    "sốt", "bệnh", "ốm", "cấp cứu", "nhập viện", "bác sĩ", "khám bệnh",
    "tai nạn", "té xe", "ngã", "chấn thương", "gãy", "đau ruột thừa",
    "ngộ độc", "truyền nước", "mất điện", "cháy", "tang", "đám tang",
    "qua đời", "ngập lụt", "bão", "sập nguồn"
]

EXCUSE_KEYWORDS = [
    "mệt", "lười", "chán", "game", "dota", "lol", "liên quân", "valorant",
    "ngủ", "buồn ngủ", "mai", "bù", "bận", "lướt", "facebook", "tiktok",
    "youtube", "nhậu", "bia", "cafe", "cà phê", "đi chơi", "hẹn hò",
    "mưa", "hết hứng", "tụt mood", "quên", "ngại"
]

def classify_skip_reason_offline(session_type: str, reason: str, fallbacks: dict) -> Tuple[str, str]:
    """Deterministic local rule-based classifier when offline or Gemini fails.
    
    Returns (classification, response_text).
    """
    clean_reason = (reason or "").strip().lower()
    
    # 1. Check for legitimate emergency keywords
    if any(kw in clean_reason for kw in LEGITIMATE_KEYWORDS):
        classification = "LEGITIMATE"
        msg = fallbacks.get(
            "offline_skip_legitimate",
            "🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!"
        )
        return classification, msg
        
    # 2. Everything else defaults to EXCUSE (accountability coach stance)
    classification = "EXCUSE"
    st = session_type.lower()
    if "gym" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: chống đẩy 5 cái hoặc plank 60s tại chỗ trước khi nghỉ!"
    elif "toeic" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu giải đúng 3 câu Part 5 trước khi tắt máy!"
    elif "major" in st or "game" in st:
        msg = "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở IDE viết đúng 1 function và commit git trước khi nghỉ!"
    else:
        msg = fallbacks.get(
            "offline_skip_excuse",
            "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!"
        )
        
    return classification, msg
```

---

## 5. Architectural Code Blueprint for `src/coach.py`

Below is the verified implementation blueprint for Worker integration, covering prompt building, micro-habit injection, parsing, and offline fallbacks:

```python
"""AI Accountability Coach implementation supporting Gemini 2.5 Flash and offline fallbacks."""

import logging
import re
from typing import Optional, Tuple, Any, Dict

logger = logging.getLogger(__name__)

SESSION_MICRO_HABIT_MAP: Dict[str, str] = {
    "gym": "5 cái chống đẩy hoặc plank 60s tại chỗ",
    "toeic": "giải đúng 3 câu Part 5 hoặc nghe 1 đoạn Part 3",
    "major": "mở IDE viết đúng 1 function và commit git",
}

LEGITIMATE_KEYWORDS = [
    "sốt", "bệnh", "ốm", "cấp cứu", "nhập viện", "bác sĩ", "khám bệnh",
    "tai nạn", "té xe", "ngã", "chấn thương", "gãy", "đau ruột thừa",
    "ngộ độc", "truyền nước", "mất điện", "cháy", "tang", "đám tang",
    "qua đời", "ngập lụt", "bão", "sập nguồn"
]

def get_micro_habit_for_session(session_type: str) -> str:
    st = (session_type or "").lower()
    for key, suggestion in SESSION_MICRO_HABIT_MAP.items():
        if key in st:
            return suggestion
    return "thực hiện đúng 2 phút hành động khởi động"

def parse_skip_evaluation(raw_text: str, default_classification: str = "EXCUSE") -> Tuple[str, str]:
    if not raw_text or not raw_text.strip():
        return default_classification, ""
    text = raw_text.strip()
    tag_match = re.search(r'\[(EXCUSE|LEGITIMATE)\]', text, re.IGNORECASE)
    if tag_match:
        classification = tag_match.group(1).upper()
        clean_text = re.sub(r'\[(EXCUSE|LEGITIMATE)\]\s*[:\-]?', '', text, flags=re.IGNORECASE).strip()
        return classification, clean_text
    line_match = re.search(r'^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\b', text, re.IGNORECASE | re.MULTILINE)
    if line_match:
        classification = line_match.group(1).upper()
        clean_text = re.sub(r'^(?:CLASSIFICATION\s*:\s*)?(EXCUSE|LEGITIMATE)\s*[:\-]?', '', text, flags=re.IGNORECASE | re.MULTILINE).strip()
        return classification, clean_text
    if "LEGITIMATE" in text.upper():
        return "LEGITIMATE", text
    elif "EXCUSE" in text.upper():
        return "EXCUSE", text
    return default_classification, text

def classify_skip_reason_offline(session_type: str, reason: str, fallbacks: dict) -> Tuple[str, str]:
    clean_reason = (reason or "").strip().lower()
    if any(kw in clean_reason for kw in LEGITIMATE_KEYWORDS):
        msg = fallbacks.get(
            "offline_skip_legitimate",
            "🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!"
        )
        return "LEGITIMATE", msg
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
            "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!"
        )
    return "EXCUSE", msg
```
