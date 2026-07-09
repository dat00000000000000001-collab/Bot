# Bot Telegram tra cứu tài liệu ôn thi

Bot tìm tài liệu/đề thi ngay trong Telegram, có thể tự động báo khi có bài mới.

Nguồn dữ liệu:
- **toanmath.com** — đầy đủ tính năng: mới nhất, tìm kiếm, duyệt theo lớp/loại
- **nganhangdethi.org** — mới nhất, tìm kiếm (không hỗ trợ duyệt theo lớp/loại
  vì trang này dùng widget JS thay vì URL chuyên mục cố định)
- **dethi.violet.vn** — mới nhất và tìm kiếm trong mục "Trung học phổ thông"
  (không có endpoint tìm kiếm riêng nên bot quét vài trang mới nhất để lọc
  theo từ khóa, có thể chậm hơn 1-2 giây so với 2 nguồn kia)

Đã kiểm tra `tailieuonthi.edu.vn` và `unimap.vn` nhưng **chưa thêm vào**:
`unimap.vn` chặn truy cập tự động qua robots.txt nên không scrape được;
`tailieuonthi.edu.vn` có thể thêm sau nếu bạn cần, chỉ chưa được đưa vào bản này.

## 1. Tạo bot Telegram (miễn phí, 2 phút)

1. Mở Telegram, tìm **@BotFather**
2. Gửi lệnh `/newbot`, đặt tên và username cho bot (username phải kết thúc bằng `bot`)
3. BotFather trả về một **token**, dạng: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   → giữ lại, đây là `BOT_TOKEN`

## 2. Deploy lên Railway (khuyên dùng, dễ nhất)

1. Đăng ký tại https://railway.app (dùng GitHub để đăng nhập)
2. Đưa 4 file này (`bot.py`, `scraper.py`, `requirements.txt`, `Procfile`) lên
   một repo GitHub mới
3. Trên Railway: **New Project → Deploy from GitHub repo** → chọn repo vừa tạo
4. Vào tab **Variables**, thêm biến:
   - `BOT_TOKEN` = token lấy từ BotFather
   - (tùy chọn) `CHECK_INTERVAL_SECONDS` = 1800 (mặc định 30 phút/lần check bài mới)
5. Railway tự nhận diện `Procfile` và chạy `worker: python bot.py`
6. Mở Telegram, tìm bot của bạn, gửi `/start`

## 2b. Deploy lên Render (thay thế)

1. Đăng ký tại https://render.com
2. **New → Background Worker** → connect GitHub repo
3. Build Command: `pip install -r requirements.txt`
   Start Command: `python bot.py`
4. Thêm Environment Variable `BOT_TOKEN` như trên
5. Deploy

> Lưu ý: gói free của Render có thể "ngủ" hoặc reset ổ đĩa khi redeploy —
> nếu vậy, danh sách subscriber/lịch sử bài đã thấy (`subscribers.json`,
> `seen_urls.json`) có thể bị mất. Railway free tier ổn định hơn cho việc
> chạy 24/7 kiểu này.

## 3. Cách dùng trong Telegram

- `/moinhat 5` — 5 tài liệu mới nhất
- `/timkiem oxyz` — tìm theo từ khóa
- `/lop 12` — xem các loại tài liệu có cho lớp 12
- `/theolop 12 "Đề HSG" 5` — 5 đề HSG Toán 12 mới nhất
- `/subscribe` — bật thông báo tự động khi có bài mới
- `/unsubscribe` — tắt thông báo

## 4. Giới hạn cần biết

- Bot lấy dữ liệu bằng cách đọc HTML công khai của toanmath.com (không có API
  chính thức) — nếu trang đổi giao diện, hàm `_extract_articles` trong
  `scraper.py` có thể cần chỉnh lại.
- Tính năng tìm kiếm dùng cả endpoint tìm kiếm của trang lẫn quét thêm vài
  chuyên mục gần đây — không đảm bảo tìm ra 100% bài cũ, phù hợp nhất với
  tài liệu mới đăng gần đây.
- Chỉ để tra cứu link, không tự giải bài.
