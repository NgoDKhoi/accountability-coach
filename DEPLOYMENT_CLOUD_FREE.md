# Hướng Dẫn Triển Khai Bot Chạy 24/24 Hoàn Toàn Miễn Phí (Cloud Free Tier)

Tài liệu này hướng dẫn chi tiết cách đưa **Personal AI Accountability Coach** lên máy chủ đám mây (Cloud) để bot hoạt động liên tục 24/7, tự động gửi thông báo đúng giờ và phản hồi tin nhắn Telegram mà bạn không cần phải mở máy tính cá nhân.

---

## Phần 1: Cách Lấy Secret iCal URL Từ Google Calendar

Để bot đọc được lịch trình cá nhân của bạn từ Google Calendar:

1. Mở [Google Calendar](https://calendar.google.com/) trên trình duyệt máy tính.
2. Ở cột bên trái, nhìn vào danh sách **"Lịch của tôi" (My calendars)**.
3. Di chuột vào tên lịch bạn muốn tích hợp, bấm vào dấu **3 chấm (`⋮`)** -> Chọn **"Cài đặt và chia sẻ" (Settings and sharing)**.
4. Cuộn chuột xuống phần **"Tích hợp lịch" (Integrate calendar)**.
5. Tìm mục có tên **"Địa chỉ bí mật ở định dạng iCal" (Secret address in iCal format)**.
   > ⚠️ *Lưu ý: Dùng "Địa chỉ bí mật" (Secret address), KHÔNG dùng "Địa chỉ công khai" để bảo mật thông tin cá nhân của bạn.*
6. Bấm nút **Sao chép** đường link (link có dạng: `https://calendar.google.com/calendar/ical/<email>/private-<token>/basic.ics`).
7. Dán link này vào file `.env`:
   ```bash
   GOOGLE_CALENDAR_ICAL_URL=https://calendar.google.com/calendar/ical/your_email/private-xyz/basic.ics
   ```

---

## Phần 2: Lựa Chọn Nền Tảng Cloud Miễn Phí Tốt Nhất

Dưới đây là 3 lựa chọn nền tảng Cloud miễn phí, ổn định và không bị chặn Telegram:

| Nền tảng | Chi phí | Ưu điểm | Đánh giá độ khó |
| :--- | :--- | :--- | :--- |
| **Render.com** *(Khuyên dùng)* | Miễn phí (750h/tháng) | Kết nối trực tiếp GitHub, tự động build Docker, giao diện web trực quan | ⭐ Dễ nhất (5 phút) |
| **Koyeb.com** | Miễn phí (Eco Nano 24/7) | Chạy 24/7 ổn định, hỗ trợ Dockerfile sẵn có | ⭐⭐ Dễ (5 phút) |
| **Oracle Cloud Always Free** | Miễn phí trọn đời | VPS Linux riêng, tài nguyên mạnh, kiểm soát 100% | ⭐⭐⭐ Trung bình |

---

## Cách 1: Triển Khai Lên Render.com (Khuyên Dùng)

Render là dịch vụ Cloud hiện đại, hỗ trợ deploy ứng dụng Python/Docker trực tiếp từ kho lưu trữ GitHub của bạn.

### Bước 1: Đăng ký tài khoản
1. Truy cập [Render.com](https://render.com/) và bấm **Sign Up** (đăng nhập nhanh bằng tài khoản GitHub của bạn).

### Bước 2: Tạo Background Worker (hoặc Web Service)
1. Trên giao diện Dashboard của Render, bấm nút **New +** ở góc trên bên phải -> Chọn **Background Worker** (hoặc Web Service).
2. Chọn kho lưu trữ GitHub chứa dự án của bạn (`accountability-coach`).
3. Điền các thông tin:
   * **Name:** `accountability-coach` (hoặc tên tuỳ ý).
   * **Region:** `Singapore` (để độ trễ về Việt Nam thấp nhất).
   * **Language / Environment:** Chọn **Docker** (Render sẽ tự động dùng file `Dockerfile` đã có sẵn trong project).
   * **Branch:** `main`.
   * **Instance Type:** Chọn gói **Free**.

### Bước 3: Cấu hình Biến Môi Trường (Environment Variables)
Cuộn xuống phần **Environment Variables**, bấm **Add Environment Variable** và thêm các biến từ file `.env` của bạn:
* `TELEGRAM_BOT_TOKEN` = `Token lấy từ @BotFather`
* `GEMINI_API_KEY` = `API Key lấy từ Google AI Studio`
* `ALLOWED_CHAT_ID` = `Chat ID Telegram của bạn (ví dụ: 123456789)`
* `GOOGLE_CALENDAR_ICAL_URL` = `Đường link Secret iCal của bạn (nếu có)`
* `TZ` = `Asia/Ho_Chi_Minh`

### Bước 4: Deploy
* Bấm **Create Background Worker**.
* Render sẽ tự động kéo code từ GitHub, build Docker container và khởi động bot.
* Xem tab **Logs**: Khi thấy dòng `[INFO] main: Bot application active. Listening for updates from Telegram...` nghĩa là bot đã online 24/7!

---

## Cách 2: Triển Khai Lên Koyeb.com

1. Đăng ký tài khoản tại [Koyeb.com](https://www.koyeb.com/) (đăng nhập bằng GitHub).
2. Bấm **Create Service** -> Chọn **GitHub**.
3. Chọn repo `accountability-coach`.
4. Trong phần **Builder**, chọn **Dockerfile**.
5. Trong phần **Environment variables**, thêm các biến:
   * `TELEGRAM_BOT_TOKEN`
   * `GEMINI_API_KEY`
   * `ALLOWED_CHAT_ID`
   * `GOOGLE_CALENDAR_ICAL_URL`
   * `TZ` = `Asia/Ho_Chi_Minh`
6. Chọn gói **Free (Eco Nano)** -> Bấm **Deploy**.
7. Bot sẽ chạy ngầm 24/7 hoàn toàn miễn phí.

---

## Cách 3: Triển Khai Trên Oracle Cloud Free Tier (VPS Linux Trọn Đời)

Nếu bạn có tài khoản Oracle Cloud (cung cấp VPS Ubuntu miễn phí trọn đời):

1. Tạo máy ảo (Compute Instance) Ubuntu 22.04 / 24.04 Always Free.
2. SSH vào VPS:
   ```bash
   ssh ubuntu@<IP_CỦA_BẠN>
   ```
3. Cài đặt Docker & Docker Compose:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker $USER
   ```
4. Clone repo về VPS:
   ```bash
   git clone https://github.com/NgoDKhoi/accountability-coach.git
   cd accountability-coach
   ```
5. Tạo và cấu hình file `.env`:
   ```bash
   cp .env.example .env
   nano .env
   # Điền TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ALLOWED_CHAT_ID, GOOGLE_CALENDAR_ICAL_URL
   ```
6. Khởi chạy bot dưới nền (Background):
   ```bash
   docker compose up -d
   ```
7. Kiểm tra log bot:
   ```bash
   docker compose logs -f
   ```

---

## Lưu Ý Quan Trọng Khi Chạy Trên Cloud

1. **Không bị chặn mạng:** Các server Cloud ở nước ngoài (Singapore, US) kết nối trực tiếp với server Telegram cực nhanh, không bao giờ bị dính lỗi `Timed out` như mạng nội địa ở Việt Nam.
2. **Dữ liệu Streak (`records.json`):** 
   * Trên Render/Koyeb: Dữ liệu được ghi vào container. Nếu container khởi động lại ở gói Free có thể dữ liệu sẽ reset về chuỗi mới.
   * Để lưu dữ liệu vĩnh viễn trên VPS/Server riêng (như Oracle Cloud), file `docker-compose.yml` đã được mount volume `./data:/app/data`, dữ liệu streak sẽ luôn an toàn tuyệt đối.
