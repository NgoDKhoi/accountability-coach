# Personal AI Accountability Coach via Telegram

Hệ thống trợ lý cá nhân ảo kỷ luật cao hoạt động qua **Telegram**, chủ động nhắc nhở lịch trình hàng ngày (Tập Gym, Học TOEIC 7 Parts, Ôn bài chuyên ngành & Game Dev), tương tác thông minh qua **Google Gemini 2.5 Flash**, tích hợp bàn phím nút bấm tương tác nhanh và lưu trữ dữ liệu an toàn tại máy cục bộ (**Atomic JSON Persistence**).

---

## 🌟 Tính Năng Nổi Bật

1. **Nhắc nhở chủ động theo lịch (Proactive Push Notifications):**
   - **Tập Gym (1 tiếng):** Thứ 2, 3, 5 nhắc lúc **17:15** (khung 17:30 - 18:30); Thứ 4, 7 nhắc lúc **16:15** (khung 16:30 - 17:30).
   - **Luyện thi TOEIC (1 tiếng):** Hàng ngày lúc **19:25** (khung 19:30 - 20:30), xoay vòng tự động 7 Parts trong tuần (Part 1 -> Part 7).
   - **Học chuyên ngành & Làm Game (1 tiếng):** Hàng ngày lúc **20:40** (khung 20:45 - 21:45).
   - Múi giờ chuẩn: `Asia/Ho_Chi_Minh` (UTC+7).

2. **Nút bấm tương tác nhanh (Inline Keyboard Buttons):**
   - `[✅ Đã hoàn thành]`: Ghi nhận hoàn thành, cộng dồn streak liên tiếp, AI Coach gửi lời khen ngắn gọn.
   - `[⏳ Xin lùi 15 phút]`: Tự động hẹn giờ nhắc lại sau 15 phút. Giới hạn tối đa 2 lần/phiên với mức độ nhắc nhở đanh thép tăng dần.
   - `[🛑 Hôm nay nghỉ (Có lý do)]`: Bot chuyển sang chế độ chờ lý do. Người dùng gửi tin nhắn giải trình -> AI Coach phân tích:
     - *Nếu viện cớ/trì hoãn*: Bẻ gãy lý do và ép thực hiện "Micro-habit 2 phút" (làm 3 câu hỏi hoặc khởi động 10 phút).
     - *Nếu lý do bất khả kháng (ốm đau, cấp cứu)*: Ghi nhận nghỉ hợp lệ, giữ nguyên chuỗi kỷ luật.

3. **Huấn luyện viên AI thực chiến (Gemini 2.5 Flash):**
   - Giọng điệu: Thẳng thắn, ngắn gọn (tối đa 2–3 câu), tư duy kỹ thuật/thực tế, hài hước châm biếm khi lười, công nhận đúng lúc.
   - Quản lý cửa sổ trượt ngữ cảnh hội thoại (6–10 tin nhắn gần nhất).
   - Có cơ chế Fallback ngoại tuyến tự động nếu mất kết nối mạng.

4. **Bảo mật & Lưu trữ an toàn (Low-code Friendly):**
   - **Strict Whitelist**: Chỉ phản hồi đúng `ALLOWED_CHAT_ID` để bảo vệ API key và lịch trình cá nhân.
   - **Atomic JSON Store**: Ghi dữ liệu vào `data/records.json` an toàn qua cơ chế ghi file tạm + replace nguyên tử (`os.replace`), chống hỏng file khi tắt máy đột ngột.

---

## 🚀 Hướng Dẫn Cài Đặt Nhanh (Dành cho Non-Dev / Low-Code)

### Bước 1: Chuẩn bị thông tin Token & Khóa API

1. **Telegram Bot Token:**
   - Mở Telegram, tìm bot `@BotFather`.
   - Gõ `/newbot`, đặt tên bot và username kết thúc bằng `bot`.
   - Sao chép đoạn mã Token (dạng `123456789:ABCdefGHI...`).

2. **Telegram Chat ID của bạn:**
   - Tìm bot `@userinfobot` trên Telegram và nhấn Start.
   - Sao chép dãy số `Id` của bạn (ví dụ: `123456789`).

3. **Google Gemini API Key (Miễn phí):**
   - Truy cập [Google AI Studio](https://aistudio.google.com/) và đăng nhập tài khoản Google.
   - Nhấn **Get API Key** -> **Create API Key** và sao chép mã khóa.

---

### Bước 2: Cấu hình File `.env`

1. Nhân bản file `.env.example` thành `.env`:
   ```bash
   cp .env.example .env
   ```
   *(Trên Windows có thể đổi tên trực tiếp hoặc mở bằng Notepad)*

2. Mở file `.env` và điền 3 thông số vừa lấy:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   GEMINI_API_KEY=AIzaSyD-xxxxxxxxxxxxxxxxxxxx
   ALLOWED_CHAT_ID=123456789
   ```

3. *(Tùy chọn)* Chỉnh sửa lịch giờ hoặc thông điệp tại `config.yaml` mà không cần đụng vào code.

---

### Bước 3: Khởi chạy Bot

Bạn có thể chọn 1 trong 3 cách khởi chạy bên dưới tùy theo sở thích:

#### Cách 1: Sử dụng Docker Compose (Khuyên dùng nhất - Ổn định 24/7)
Chỉ cần máy đã cài đặt Docker Desktop:
```bash
docker compose up -d --build
```
- Để xem nhật ký hoạt động: `docker compose logs -f`
- Để dừng bot: `docker compose down`

#### Cách 2: Chạy 1-Click Script (Không cần cài Docker)
- **Trên Windows**: Nhấp đúp chuột vào file `start.bat` (Script tự động tạo môi trường ảo, tải thư viện và chạy bot).
- **Trên Linux / macOS**: Mở Terminal và gõ:
  ```bash
  chmod +x start.sh
  ./start.sh
  ```

#### Cách 3: Chạy thủ công bằng Python
Yêu cầu Python 3.11+:
```bash
# 1. Tạo và kích hoạt môi trường ảo
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 2. Cài đặt thư viện
pip install -r requirements.txt

# 3. Khởi chạy
python src/main.py
```

---

## 📁 Cấu Trúc Thư Mục

```text
serene-bohr/
├── .env.example              # Mẫu khai báo biến môi trường bí mật
├── config.yaml               # Lịch trình cron, lộ trình TOEIC, mẫu prompt của AI
├── requirements.txt          # Danh sách thư viện Python
├── Dockerfile                # Cấu hình đóng gói container
├── docker-compose.yml        # Triển khai dịch vụ chạy ngầm với volume data/
├── start.bat                 # Script chạy 1-click cho Windows
├── start.sh                  # Script chạy 1-click cho Linux / macOS
├── README.md                 # Tài liệu hướng dẫn sử dụng
├── data/
│   └── records.json          # File lưu lịch sử check-in, streak (tự động tạo)
├── src/
│   ├── __init__.py
│   ├── main.py               # Điểm khởi chạy chính & điều phối vòng đời bot
│   ├── config.py             # Trình nạp và kiểm tra tính hợp lệ cấu hình
│   ├── storage.py            # Engine lưu trữ JSON atomic chống xung đột
│   ├── coach.py              # Dịch vụ Gemini AI Coach & đánh giá lý do
│   ├── scheduler.py          # Bộ lập lịch hẹn giờ APScheduler (Asia/Ho_Chi_Minh)
│   └── bot.py                # Xử lý cập nhật Telegram & nút bấm Inline
└── tests/                    # Bộ kiểm thử tự động toàn diện (Unit, E2E, Adversarial)
```

---

## 🧪 Kiểm Thử Tự Động (Automated Testing)

Toàn bộ hệ thống được bảo vệ bởi bộ kiểm thử tự động 100% offline (không phụ thuộc mạng internet):

```bash
# Chạy toàn bộ test suite
pytest -v

# Chạy riêng 4 tầng E2E
pytest tests/test_e2e_tier*.py -v
```

---

## 📜 Giấy Phép & Đóng Góp
Dự án được thiết kế theo hướng module hóa sạch sẽ, phục vụ mục đích xây dựng tính kỷ luật cá nhân. Bạn hoàn toàn có thể tự do mở rộng và tùy biến!
