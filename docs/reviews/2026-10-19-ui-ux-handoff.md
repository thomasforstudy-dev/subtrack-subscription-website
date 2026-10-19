# SubTrack — Báo cáo Nghiệm thu & Bàn giao Giao diện (UI/UX Handoff)

- **Ngày thực hiện:** `2026-10-19`
- **Nhánh (Branch):** `antigravity/ui-ux` (tách từ `codex/quality-baseline` tại commit `5a8ec43`)
- **Phạm vi (Lane):** Chỉ chỉnh sửa các tệp thuộc làn UI (`app/templates/`, `app/static/`, `docs/design/`, `docs/PROGRESS.md`, `docs/reviews/2026-10-19-ui-ux-handoff.md`). Không chỉnh sửa bất kỳ tệp Python (`app/*.py`), SQL (`database/`), kiểm thử (`tests/`), hoặc triển khai (`deploy/`) nào.

---

## 1. Tổng hợp kết quả theo 7 Phần (Sections 1–7)

### Phần 1: Audit trước khi sửa & Trang chủ (Landing Page)
- **Tệp cập nhật:** `app/templates/landing.html`, `app/static/landing.css`, `app/static/landing.js`
- **Những gì đã hoàn thiện:**
  - Chụp ảnh hiện trạng trước khi sửa (`docs/design/audit-before-*.png`) để làm mốc đối chiếu.
  - Hoàn thiện câu chuyện cuộn 7 chương (Chương 1–7) với đầy đủ nhãn tiếng Việt rõ ràng và chuyển đổi ngôn ngữ `VI / EN` tức thì (`[data-lang-toggle]`).
  - Bổ sung khối minh họa **Đọc hóa đơn (OCR) & Kỳ sao kê thẻ tín dụng** tại Chương 6 kèm nhãn rõ ràng `"DEMO — Dữ liệu minh họa"`.
  - Cập nhật nội dung trung thực theo phát hiện `R7` của Codex: ngày gia hạn là **ngày dự kiến**, SubTrack không tự hủy gói cước bên ngoài, và tính năng gửi email tự động hàng ngày đang trong giai đoạn hoàn thiện ở nhánh Backend.
  - Bổ sung 3 hộp thoại `<dialog>` (**Quyền riêng tư**, **Điều khoản**, **Giới thiệu**) có áp dụng `overscroll-behavior: contain` để chặn cuộn nền bên dưới.
  - Chỉ hiển thị liên kết liên hệ hợp lệ (`MESSENGER_URL` / `ZALO_URL`), ẩn hoàn toàn liên kết trống hoặc placeholder.

### Phần 2: Tài khoản & Xác thực (Accounts)
- **Tệp cập nhật:** `app/templates/auth/register.html`, `app/templates/auth/login.html`, `app/templates/auth/_social.html`, `app/templates/auth/forgot.html`, `app/templates/auth/reset.html`, `app/templates/auth/verify.html`
- **Những gì đã hoàn thiện:**
  - Thiết lập chuẩn `autocomplete` (`username`, `email`, `new-password`, `current-password`), `autocapitalize="none"`, `spellcheck="false"`, và nút **Hiện / Ẩn mật khẩu** (`[data-toggle-password]`).
  - Tương thích kép (dual-compatibility) giữa nhánh hiện tại (`codex/quality-baseline`) và nhánh `claude/accounts`: sử dụng `{% if csrf_token is defined %}` để tự động chèn `csrf_token`, trường `username`, `identifier`, `POST /logout`, và `/forgot-password` ngay khi nhánh của Claude được gộp vào mà vẫn vượt qua 100% bài kiểm thử hiện tại.
  - Ẩn hoàn toàn nút OAuth khi `providers` rỗng (không hiển thị nút chết).
  - Bổ sung thanh nhắc xác thực email (`verify-banner`) trên `app/templates/base.html` khi `current_user.email_verified is defined and not current_user.email_verified`.

### Phần 3: Thanh điều hướng 6 mục, Tổng quan (`dashboard.html`) & Gói đăng ký (`subscriptions/list.html`, `form.html`)
- **Tệp cập nhật:** `app/templates/base.html`, `app/templates/dashboard.html`, `app/templates/subscriptions/list.html`, `app/templates/subscriptions/form.html`, `app/static/app-ui.js`, `app/static/style.css`
- **Những gì đã hoàn thiện & đối soát hợp đồng Backend (`docs/CONTRACT.md` — `RUNTIME-1`, `RUNTIME-2`, `RUNTIME-3`):**
  - Thanh điều hướng chính gồm 6 mục rõ ràng: **Tổng quan** (`/dashboard`), **Gói đăng ký** (`/subscriptions/`), **Link đã lưu** (`/links/`), **Hóa đơn / Giao dịch**, **Nhắc nhở**, **Cài đặt** (`/settings`) cùng nút mở nhanh trợ lý **Subby** và chuyển ngôn ngữ **VI / EN**.
  - **Trang `/dashboard` (`app/templates/dashboard.html`)**:
    1. *Chi dự kiến toàn tài khoản theo từng loại tiền tệ* — hiển thị trực tiếp `totals` kiểu `Decimal` do máy chủ tính trên toàn bộ gói `active` (không bao giờ cộng `items|float` trên trang phân trang).
    2. *Sắp gia hạn trong 30 ngày tới (`upcoming`)* kèm liên kết mở trang quản lý/hủy (`manage_url`).
    3. *Khoản đến hạn cần kiểm tra trong 60 ngày qua (`expected`)* kèm nút xác nhận `POST` **Đã trả (Paid)** (`outcome=paid`) hoặc **Không thu (Not charged)** (`outcome=skipped`) gửi tới `subscriptions.mark_renewal`.
    4. *Hạn thanh toán thẻ tín dụng* (hiển thị trạng thái Trống trung thực + khu vực xem thử kỳ sao kê thẻ được đánh dấu rõ `"DEMO — Dữ liệu minh họa"` trong `<details>`).
    5. *Chi tiêu thực tế (Actual spending)* liên kết tới khu vực hóa đơn/biên lai.
  - **Trang `/subscriptions/` (`app/templates/subscriptions/list.html`)**:
    - Hiển thị dải **Chi dự kiến toàn tài khoản (`#account-wide-summary`)** lấy dữ liệu `Decimal` từ `/dashboard.json` (tách biệt hoàn toàn khỏi 20 dòng trên trang hiện tại).
    - Thanh công cụ **Tìm kiếm (`q`), Lọc trạng thái (`status`: `active` / `archived` / `all`), Sắp xếp (`sort`: `renewal` / `amount` / `name`)** gửi `GET` lên máy chủ để lọc trên toàn bộ tài khoản.
    - Nút **Khôi phục (Restore)** gửi `POST` tới `subscriptions.restore` cho các gói đã lưu trữ (`status == 'archived'`), và hộp thoại `<dialog>` xác nhận trước khi bấm **Lưu trữ (Archive)**.
    - Phân trang máy chủ đầy đủ (`Page {{ pages.page }} of {{ pages.pages }}`, `← Newer`, `More →`).
  - **Biểu mẫu Tạo/Sửa gói (`app/templates/subscriptions/form.html`)**:
    - Sử dụng đúng `name="lead_days"` (thay cho `remind_days` cũ) và `name="manage_url"` theo `docs/CONTRACT.md`, bảo toàn nguyên vẹn chuỗi `14,7,3` và URL quản lý khi sửa gói.
    - Bảo toàn toàn bộ giá trị người dùng vừa nhập (`form.get(...)` cho `name`, `amount`, `currency`, `cycle`, `next_renewal_at`, `lead_days`, `manage_url`, `notes`) khi máy chủ trả về lỗi xác thực HTTP `400`.

### Phần 4: Quản lý Đường dẫn đã lưu (Pinned Links)
- **Tệp cập nhật:** `app/templates/links/list.html`, `app/templates/links/form.html`, `app/static/link-preview.js`, `app/static/app-ui.js`
- **Những gì đã hoàn thiện:**
  - Hiển thị biểu tượng trang web (`link.favicon_url` với `referrerpolicy="no-referrer"`, `loading="lazy"`, và tự động chuyển về chữ cái đầu tên miền khi ảnh lỗi), viên thuốc tên miền (`domain`), URL đầy đủ, trạng thái ghim (`★ Đã ghim`), thẻ phân loại (`#tag`), và trạng thái lấy tiêu đề tự động.
  - Phát hiện đường dẫn trùng lặp ngay trên trình duyệt khi người dùng dán URL đã có trong danh sách, kèm nút **Mở sửa bản cũ**.
  - Hộp thoại `<dialog>` xác nhận trước khi xóa vĩnh viễn đường dẫn.

### Phần 5: Hóa đơn, Chứng từ OCR & Giao dịch (`_bills_section.html`)
- **Tệp cập nhật:** `app/templates/subscriptions/_bills_section.html`, `app/static/app-ui.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Đánh dấu trung thực `DEMO — Dữ liệu minh họa (Chưa kết nối OCR thật)` trên toàn bộ khu vực hóa đơn, và thu gọn các nút chuyển bước nội bộ vào ngăn `<details>` (`Chế độ xem thử cho nhà phát triển (Dev/QA Preview)`).
  - Khu vực tải tệp hỗ trợ `PNG, JPG, WEBP, PDF` (tối đa 10 MB, 5 trang) và thông báo rõ không hỗ trợ trực tiếp tệp Office (`DOCX/DOC`).
  - Màn hình đối chiếu 2 cột trên máy tính và tự động thu gọn thành **3 Tab** trên điện thoại (`✏️ Trường giao dịch`, `📄 Tài liệu nguồn`, `📝 Markdown`).

### Phần 6: Trợ lý AI Subby — Chat, Giọng nói, Provider & Cloud Fallback
- **Tệp cập nhật:** `app/templates/_subby.html`, `app/static/subby.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Bảo toàn đầy đủ trường `provider` và `fallback` từ phản hồi `POST /subby/ask`.
  - Khi `fallback: true`, hiển thị huy hiệu `☁️ Answered by a cloud model (Fallback)` và thông báo rõ ràng (`[data-cloud-fallback-note]`) rằng câu trả lời được tạo bởi mô hình đám mây dự phòng do mô hình chính đang ngoại tuyến hoặc bận.
  - Phân biệt rõ trạng thái `fake` (môi trường kiểm thử), `not-set-up`, `model-offline`, `rate-limit`, và câu trả lời FAQ dựng sẵn.
  - Hiển thị rõ 4 trạng thái giọng nói (`idle`, `listening`, `thinking`, `speaking`) và thẻ **Xác nhận thao tác** trước mọi hành động ghi dữ liệu.

### Phần 7: Cài đặt lưu trên Máy chủ (`settings.html`), Gmail OAuth Prep, PWA Install & Xuất dữ liệu an toàn
- **Tệp cập nhật:** `app/templates/settings.html`, `app/templates/subscriptions/_settings_section.html`, `app/static/favicon.svg`, `app/static/icon-192.svg`, `app/static/manifest.webmanifest`, `app/static/app-ui.js`
- **Những gì đã hoàn thiện:**
  - Tạo trang `/settings` (`app/templates/settings.html`) gửi biểu mẫu `POST /settings` có `csrf_token`, lưu bền vững trên máy chủ các trường `timezone` (`datalist#zones`), `reminders_enabled`, `reminder_hour` (`0–23`), và `channels` (`email`, `browser`, `calendar`).
  - Tách biệt rõ cài đặt lưu trên máy chủ với tùy chọn ngôn ngữ hiển thị cục bộ trên trình duyệt (`localStorage`).
  - Xuất dữ liệu `.JSON` / `.CSV` ghi rõ phạm vi **các dòng đang hiển thị trên trang hiện tại** và làm sạch toàn bộ ô CSV chống lỗi **CSV Formula Injection** (`=`, `+`, `-`, `@`, `\t`, `\r`).

---

## 2. Kiểm tra Đa màn hình & Ảnh chụp Trước / Sau (`docs/design/`)

Đã kiểm tra bằng Microsoft Edge Headless trên cơ sở dữ liệu SQLite tạm thời:
- **Điện thoại (`390×844`):** `ui-after-landing-phone.png`, `ui-after-register-phone.png`, `ui-after-login-phone.png`, `ui-after-dashboard-phone.png`, `ui-after-links-phone.png`
- **Laptop (`1440×900`):** `ui-after-landing-laptop.png`, `ui-after-dashboard-laptop.png`, `ui-after-links-laptop.png`
- **Desktop (`1920×1080`):** `ui-after-landing-desktop.png`, `ui-after-dashboard-desktop.png`
- **Màn hình thấp (`1366×680`):** `ui-after-dashboard-lowscreen.png`
- **Ảnh hiện trạng trước khi sửa:** `audit-before-landing-phone.png`, `audit-before-landing-laptop.png`, `audit-before-landing-desktop.png`, `audit-before-register-phone.png`, `audit-before-login-phone.png`

---

## 3. Kết quả Chạy Kiểm thử Tự động (`pytest` & `probe-routes.py`)

1. **Trên nhánh `antigravity/ui-ux` (baseline):**
```text
.\.venv\Scripts\python.exe -m pytest -q
68 passed, 4 xfailed in 6.78s
```

2. **Trên bản kết hợp (Combined Overlay: Backend `c33f88d` của Claude + `app/templates/` & `app/static/` của Antigravity):**
```text
.\.venv\Scripts\python.exe -m pytest -q
184 passed in 25.81s
```
- `probe-routes.py`: Tất cả các trang (`/dashboard`, `/subscriptions/`, `/settings`, `/links/`, `/subscriptions/new`) trả về `200`, `edit_controls` có đủ `lead_days` và `manage_url`, và `edit_result` bảo toàn nguyên vẹn `lead_days: "14,7,3"` cùng `manage_url: "https://example.test/manage"`.

---

## 4. Yêu cầu Bàn giao Còn lại cho Nhánh Backend (Claude / Codex)

1. **API Hóa đơn OCR & Kỳ sao kê thẻ (Tương lai):** Kết nối `#bill-review-form` với endpoint tải tệp (`POST /bills/upload`) và lưu giao dịch đã duyệt (`POST /bills/<id>/confirm`), cùng bảng dữ liệu cho `#credit-cards`.
2. **OAuth Gmail đọc hóa đơn (Tương lai):** Thêm route kết nối/ngắt kết nối OAuth riêng (`/settings/gmail/connect`, `/settings/gmail/disconnect`) tách biệt với đăng nhập Google.
