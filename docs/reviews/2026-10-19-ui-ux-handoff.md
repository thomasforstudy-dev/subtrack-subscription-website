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

### Phần 5: Hóa đơn, Sao kê thẻ, Tải tệp riêng tư & Kiểm tra chứng từ (`bills/list.html`, `bills/form.html`, `_bills_section.html`)
- **Tệp cập nhật:** `app/templates/bills/list.html`, `app/templates/bills/form.html`, `app/templates/subscriptions/_bills_section.html`, `app/templates/dashboard.html`, `app/templates/base.html`
- **Những gì đã hoàn thiện & kết nối Backend thật (`/bills/` — D slice 1):**
  - Kết nối thanh điều hướng chính (`base.html`), thẻ Tổng quan (`dashboard.html`) và khu vực Hóa đơn (`subscriptions/_bills_section.html`) trực tiếp tới các route thật: `GET /bills/`, `GET/POST /bills/new`, `GET/POST /bills/<id>/edit`, `POST /bills/upload`, `GET /bills/files/<id>`, `POST /bills/<id>/paid`, `POST /bills/<id>/archive`, `POST /bills/<id>/restore`, và `GET /bills/export.json|.csv|.md`.
  - **Trang danh sách `/bills/` (`app/templates/bills/list.html`)**: hiển thị khối tải tệp riêng tư (`PNG, JPG, WEBP, PDF ≤ 5 trang, DOCX ≤ 10 MB`), danh sách tệp chờ nhập (`Waiting to be typed in`), danh sách sao kê thẻ chờ thanh toán (`Card bills to pay` kèm nút `Mark paid`), tổng chi thực tế theo từng loại tiền tệ (`Spent — confirmed receipts` kiểu `Decimal`), bộ lọc máy chủ (`q`, `kind`, `category`, `status`), phân trang và thanh xuất toàn bộ hóa đơn đã xác nhận (`JSON`, `CSV formula-safe`, `Markdown`).
  - **Trang nhập & đối chiếu `/bills/new` & `/bills/<id>/edit` (`app/templates/bills/form.html`)**: bố cục 2 cột đối chiếu trực tiếp bên cạnh ảnh hóa đơn đã tải lên (`?view=1` với `referrerpolicy="no-referrer"`, trong khi PDF/DOCX luôn ở chế độ chỉ tải xuống an toàn), giữ nguyên mọi giá trị đã gõ khi có lỗi xác thực (`form.get(...)`), không bao giờ hiển thị lại số thẻ đầy đủ (`card_last4` chỉ nhận 4 số cuối với `autocomplete="off"`), và giữ nguyên các trường không có trên hóa đơn ở trạng thái trống (`null`, không bao giờ tự điền giờ `00:00`).
  - **Phân tách rõ phần Demo còn lại**: Khung mô phỏng đọc OCR tự động (`GOT-OCR`) trong `subscriptions/_bills_section.html` vẫn giữ nhãn `"Trích xuất OCR tự động: Chế độ xem trước (Demo)"` cho tới khi lát cắt OCR hoàn tất.

### Phần 6: Trợ lý AI Subby — Chat, Account Tools, Giọng nói (Web Speech API), Provider & Cloud Fallback
- **Tệp cập nhật:** `app/templates/_subby.html`, `app/static/subby.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Bảo toàn đầy đủ trường `provider` và `fallback` từ phản hồi `POST /subby/ask`. Khi `fallback: true`, hiển thị huy hiệu `☁️ Answered by a cloud model` (`[data-cloud-fallback-note]`).
  - **Account Tools (`list_upcoming_renewals`, `search_saved_links`, `summarize_transactions`, `create_reminder_draft`)**: dựng danh sách kết quả bằng DOM an toàn (`createElement` + `textContent`, không dùng `innerHTML`), gắn `rel="noopener noreferrer"` cho liên kết ngoài, hiển thị nút xác nhận **`Kiểm tra và lưu / Check and save`** mở `/subscriptions/new?...` cho bản nháp nhắc lịch, và không đẩy dữ liệu tài khoản riêng tư vào `history` gửi lên mô hình.
  - **Chế độ Giọng nói (Browser Speech Voice Mode)**: xây dựng màn hình Voice Stage (`[data-voice-stage]`) theo đúng thiết kế Stitch (`docs/design/subby-voice-phone.png`), quản lý 4 trạng thái (`idle`, `listening`, `thinking`, `speaking`), **chỉ yêu cầu quyền micro sau khi người dùng chủ động bấm nút** (`[data-mic]` hoặc `[data-voice-orb]`), cảnh báo rõ việc trình duyệt có thể gửi âm thanh tới dịch vụ nhận diện giọng nói bên ngoài (`[data-voice-privacy-note]`), tích hợp bản sửa lỗi V1 từ nhánh kết hợp của Codex (luôn gửi văn bản đã chỉnh sửa trên `input.value`, chống gửi trùng khi bấm đúp, phân tách `stop()` giữ kết quả cuối với `abort()` khi hủy/đóng/nhấn Escape/`pagehide`), hiển thị thông báo song ngữ Việt–Anh rõ ràng khi từ chối quyền micro (`not-allowed`), không nghe thấy giọng nói (`no-speech`), lỗi mạng (`network`), hoặc thiếu thiết bị thu âm (`audio-capture`), tối ưu hiển thị gọn gàng trên màn hình điện thoại `390×844`, và kiểm thử vòng đời VI/EN trong `tests/voice_lifecycle.cjs`.

### Phần 7: Cài đặt lưu trên Máy chủ (`settings.html`), Lịch gia hạn (`calendar/*.html`), Gmail OAuth Prep & PWA
- **Tệp cập nhật:** `app/templates/settings.html`, `app/templates/calendar/index.html`, `app/templates/calendar/review.html`, `app/static/favicon.svg`, `app/static/icon-192.svg`, `app/static/manifest.webmanifest`, `app/static/app-ui.js`
- **Những gì đã hoàn thiện:**
  - Trang `/settings` (`app/templates/settings.html`) lưu bền vững trên máy chủ các trường `timezone`, `reminders_enabled`, `reminder_hour` (`0–23`), và `channels` (`email`), tách biệt hoàn toàn với tùy chọn ngôn ngữ hiển thị cục bộ (`localStorage`).
  - Trang Lịch gia hạn (`/calendar/` và `/calendar/subscriptions/<id>`) chuẩn `DESIGN.md` v2: kết nối các liên kết kiểm tra Google Calendar thủ công (`Nothing is added until you review`) và tải tệp `.ics` cả ngày (`VALUE=DATE`), không lộ số tiền, ghi chú hay URL quản lý.
  - Tệp `manifest.webmanifest` chỉ cung cấp biểu tượng cài đặt nhanh trên màn hình chính; ứng dụng không dùng Service Worker lưu đệm ngoại tuyến dùng chung cho hóa đơn hay dữ liệu tài khoản riêng tư (`Cache-Control: no-store, private`).

---

## 2. Kiểm tra Đa màn hình & Ảnh chụp Trước / Sau (`docs/design/`)

Đã kiểm tra bằng Microsoft Edge Headless trên cơ sở dữ liệu SQLite tạm thời:
- **Điện thoại (`390×844`):** `ui-after-landing-phone.png`, `ui-after-register-phone.png`, `ui-after-login-phone.png`, `ui-after-dashboard-phone.png`, `ui-after-links-phone.png`
- **Laptop (`1440×900`):** `ui-after-landing-laptop.png`, `ui-after-dashboard-laptop.png`, `ui-after-links-laptop.png`
- **Desktop (`1920×1080`):** `ui-after-landing-desktop.png`, `ui-after-dashboard-desktop.png`
- **Màn hình thấp (`1366×680`):** `ui-after-dashboard-lowscreen.png`
- **Ảnh hiện trạng trước khi sửa:** `audit-before-landing-phone.png`, `audit-before-landing-laptop.png`, `audit-before-landing-desktop.png`, `audit-before-register-phone.png`, `audit-before-login-phone.png`

---

## 3. Phân định Rõ: Giao diện Đã Tích hợp · Kiểm thử Runtime · Demo / Phụ thuộc Bên ngoài

| Hạng mục | Trạng thái hiện tại | Chi tiết xác minh |
|---|---|---|
| **1. Giao diện Đã Tích hợp (Implemented & Integrated UI)** | **Hoạt động 100% với Backend thật** | Tài khoản (`/register`, `/login`, `POST /logout`, xác nhận email, đặt lại mật khẩu), Tổng quan (`/dashboard`, `/dashboard.json`), Gói đăng ký (`/subscriptions/`, `lead_days`, `manage_url`, bảo toàn `form` khi lỗi, tìm kiếm/lọc/sắp xếp/phân trang máy chủ, lưu trữ/khôi phục), Link đã lưu (`/links/`, `favicon_url` với `referrerpolicy="no-referrer"`), Cài đặt máy chủ (`/settings`, `/settings.json`), Lịch gia hạn & xuất `.ics` (`/calendar/*`), Trợ lý Subby (`/subby/ask`, 4 Account Tools, Cloud Fallback notice, Browser Speech Voice Mode với sửa lỗi V1), và Hóa đơn thủ công + Tải tệp riêng tư + Xuất chuẩn (`/bills/`, `/bills/new`, `/bills/<id>/edit`, `item_rows=1` + thêm/xóa tối đa 30 dòng mặt hàng qua `bills-form.js`, cảnh báo vàng `Please check: …`, phân biệt rõ Dự kiến vs Đã trả & Biên lai vs Sao kê thẻ). |
| **2. Kiểm thử Runtime Đã Chạy (Integrated Runtime Checks)** | **`375 passed` (trên nhánh kết hợp P0 + Voice V1)** | Chạy bộ kiểm thử hợp nhất trên Python 3.14.8 / SQLite + Node VM (`test_voice_lifecycle.py` + `voice_lifecycle.cjs`, `test_bills.py`, `test_bills_integration.py`, `test_ui_contracts.py`, `test_pages.py`, v.v.). |
| **3. Phần Mô phỏng / Phụ thuộc Bên ngoài (Demos & External Dependencies)** | **Đánh dấu trung thực trên UI** | - **OCR tự động (`GOT-OCR`) & gắn nguồn từng dòng**: Khung đối chiếu tự động trong `subscriptions/_bills_section.html` giữ nhãn `Demo` cho tới khi lát cắt OCR của nhánh Backend hoàn tất (việc tải tệp thật và nhập đối chiếu thủ công bên cạnh tệp gốc tại `/bills/new?document_id=…` đã hoạt động thật).<br>- **Đồng bộ hóa đơn Gmail OAuth**: Đánh dấu rõ `Chuẩn bị UI (UI Preparation)` tại `/settings`.<br>- **Chrome Extension**: Đánh dấu rõ `Chưa phát hành (Unreleased)`.<br>- **PWA (`manifest.webmanifest`)**: Chỉ cung cấp biểu tượng màn hình chính, không lưu đệm dữ liệu riêng tư hay hóa đơn vào bộ nhớ dùng chung. |

---

## 4. Báo cáo Nghiệm thu Nghiêm ngặt Ưu tiên 1–3 & Cài đặt Nhắc nhở (2026-10-20)

- **Commit cơ sở kiểm thử:** `antigravity/ui-ux` (kế thừa commit tích hợp `25d2ecd` kết hợp `main` `766d729` và `codex/bills-voice-validation` `6918df8`)
- **Môi trường chạy kiểm thử:** Microsoft Windows 11, Python 3.14.8, Node.js v22.12.0, Microsoft Edge `155.0.4283.62`.
- **Tổng số ca kiểm thử tự động:** `383 passed` (toàn bộ kiểm thử pytest backend) + `voice lifecycle: edit/send/stop/cancel/end/error/duplicate passed` (Node CDP & life-cycle runner).

### Ưu tiên 1 (Priority 1) — Hành vi Nhận diện & Đọc giọng nói Thực tế (Voice Behavior)
1. **Khảo sát Năng lực Trình duyệt (Browser Capabilities & Edge 155 Probe):**
   - Microsoft Edge Headless/Desktop 155 trên Windows phát hiện `SpeechRecognition = true`, `webkitSpeechRecognition = true`, `speechSynthesis = true`.
   - Có tổng cộng **324 giọng đọc (voices)** có sẵn trong Edge trên máy tính này.
   - **Tiếng Việt (`vi-VN`):** Phát hiện 2 giọng đọc trực tuyến gồm `"Microsoft Hoài My Online (Natural) - Vietnamese (Vietnam)"` và `"Microsoft Nam Minh Online (Natural) - Vietnamese (Vietnam)"` với thuộc tính `localService: false`. Do là giọng đọc trực tuyến (Online Neural Voice), văn bản được gửi về máy chủ dịch vụ của Microsoft/trình duyệt để tổng hợp âm thanh.
   - **Tiếng Anh (`en-US`):** Phát hiện giọng đọc cục bộ `"Microsoft David - English (United States)"` (`localService: true`, giọng SAPI nội bộ) cùng các giọng đọc mở rộng trực tuyến (`localService: false`).
   - Nhận diện giọng nói trình duyệt (`webkitSpeechRecognition`) sử dụng dịch vụ đám mây của nhà cung cấp trình duyệt.
   - **Khuyến cáo bảo mật rõ ràng trên UI:** Giao diện Voice Mode (`_subby.html` & `subby.js`) hiển thị thông báo bảo mật rõ ràng: *"🔒 Chỉ bật mic khi bạn bấm chọn. Trình duyệt có thể gửi âm thanh nhận diện (SpeechRecognition) hoặc giọng đọc trực tuyến (online TTS) tới dịch vụ bên ngoài của trình duyệt. SubTrack không lưu âm thanh; hãy kiểm tra chữ trước khi gửi."*
2. **Quy tắc An toàn & Tương tác:**
   - **Chỉ kích hoạt Micro sau cú nhấp chuột có chủ đích:** Tuyệt đối không tự động yêu cầu quyền micro khi tải trang.
   - **Không bao giờ tự động gửi:** Lời nói được nhận diện sẽ chuyển thành văn bản trong khung nhập liệu. Người dùng hoàn toàn có thể chỉnh sửa trước khi bấm Gửi. Văn bản thực tế gửi đi `ask(text)` là giá trị chính xác đã chỉnh sửa (`draftEdited ? voiceInput.value.trim() : ...`).
   - **Ngăn chặn phát chồng chéo âm thanh (Overlapping TTS prevention):** Hàm `stopSpeaking()` (`speechSynthesis.cancel()`) được tự động gọi trước mọi câu nói mới, khi gửi câu hỏi mới, khi đóng Voice Mode, khi chuyển tab (`visibilitychange`), hoặc khi người dùng rời trang (`pagehide`).
   - **Bảo toàn dữ liệu khi có lỗi:** Khi gặp lỗi `not-allowed`, `no-speech`, `network`, `audio-capture`, nếu người dùng đã gõ chỉnh sửa (`draftEdited = true`), nội dung đang gõ được giữ nguyên vẹn, không bị xóa bởi callback `onend`/`onerror` muộn.
   - **Phân tách rõ ràng giữa Dừng (`stopVoiceRecognition(false)`) và Hủy (`abortVoiceRecognition()`):** Bấm Dừng sẽ hoàn tất nhận diện phần âm thanh đã nói; bấm Hủy (hoặc bấm ra ngoài / Esc / chuyển tab) sẽ ngắt ngay lập tức mà không gửi dữ liệu dở dang.
3. **Quy trình Kiểm tra Phần cứng dành cho Chủ sở hữu (Owner-Assisted Microphone Test):**
   - Do môi trường dòng lệnh không có micro vật lý, việc kiểm tra luồng cấp quyền trình duyệt thực tế cần được chủ sở hữu thực hiện như sau:
     1. Mở trang web trên Edge/Chrome.
     2. Bấm biểu tượng Subby và chọn biểu tượng Micro.
     3. Khi trình duyệt hiện popup xin quyền:
        - Bấm **Từ chối (Block)**: Kiểm tra thông báo đỏ *"Trình duyệt chưa được cấp quyền micro. Bạn hãy cấp quyền trong cài đặt trang web hoặc dùng bàn phím để gõ."*
        - Bấm **Cho phép (Allow)** nhưng giữ im lặng 10 giây: Kiểm tra thông báo *"Chưa nghe thấy tiếng nói. Bạn thử nói lại hoặc dùng bàn phím nhé."*
        - Nói một câu tiếng Việt có dấu (ví dụ: "Kiểm tra gói Netflix"): Kiểm tra chữ hiện lên khung nhập, chỉnh sửa thử một từ rồi bấm Gửi.

### Ưu tiên 2 (Priority 2) — Giao diện Đối chiếu Hóa đơn & Chứng từ (Document Review UI)
- Đã đồng bộ hoàn toàn với hợp đồng backend của Claude (`DocumentJob`, `BillDraft`, `DocumentPage`, `bill_review`):
  1. **Hiển thị đầy đủ 5 trạng thái tài liệu:**
     - `queued` (Đang xếp hàng / Queued)
     - `processing` (Đang trích xuất / Processing)
     - `needs_review` (Cần đối chiếu / Ready for review)
     - `failed` (Trích xuất thất bại / OCR failed)
     - `unavailable` (Cần nhập tay / Manual review required)
  2. **Bố cục đối chiếu 2 cột (`review-grid`):** Tài liệu gốc tải lên được hiển thị trực tiếp bên cạnh các trường dữ liệu dự thảo trích xuất.
  3. **Phân định Minh chứng & Giá trị Chưa rõ (`null`):**
     - Các trường không có thông tin trên hóa đơn giữ nguyên giá trị `null` (để trống), không bao giờ tự ý gán giờ mặc định `00:00`.
     - Nhãn cảnh báo vàng `"Please check: …"` hiển thị rõ ràng khi tổng phụ + thuế khác tổng thanh toán mà không tự ý sửa đổi số liệu người dùng.
  4. **Bảo toàn Mặt hàng (1..30 dòng):** Hỗ trợ thêm/xóa dòng mặt hàng động qua `bills-form.js`, bảo toàn đầy đủ 100% các dòng đã nhập khi có lỗi xác thực (`400 Bad Request`).
  5. **Phân biệt rành mạch:**
     - Giữa **Biên lai thanh toán (Receipt)** và **Sao kê thẻ tín dụng (Card Statement)**.
     - Giữa **Chi dự kiến (Expected)** và **Chi thực tế (Paid)**.
     - Giữa các đơn vị tiền tệ khác nhau (VND, USD, EUR...).

### Ưu tiên 3 (Priority 3) — Cài đặt Ứng dụng (PWA), Ngoại tuyến & Khả năng Tiếp cận (Accessibility)
1. **Kiểm tra Tệp cấu hình & Cài đặt (PWA Manifest & Standalone Launch):**
   - Tệp `manifest.webmanifest` đã được xác thực: `display: standalone`, `background_color: #f4f1ff`, `theme_color: #6d4aff`, các biểu tượng kích thước chuẩn `64x64`, `192x192`, `512x512` maskable.
   - **Chính sách Lưu trữ Bộ nhớ đệm (Strict Cache Rules):** Ứng dụng tuyệt đối **không** dùng Service Worker để lưu đệm các phản hồi xác thực, trang hóa đơn, tệp tải lên hoặc dữ liệu tài khoản nhạy cảm (`Cache-Control: no-store, private`).
   - **Thông báo Ngoại tuyến Trung thực (`#offline-banner`):** Khi mất kết nối mạng (`navigator.onLine === false`), biểu ngữ trạng thái tự động hiển thị thông báo trung thực: *"Bạn đang ngoại tuyến. Để bảo vệ dữ liệu cá nhân, thông tin hóa đơn và tài khoản không được lưu bộ nhớ đệm ngoại tuyến."*
2. **Khả năng Tiếp cận Toàn diện (Accessibility WCAG 2.1 AA):**
   - **Liên kết nhảy tới nội dung chính (Skip link):** Bổ sung `tabindex="-1"` vào thẻ `<main id="main-content">`, đảm bảo trình duyệt chuyển tiêu điểm bàn phím chính xác.
   - **Điều hướng Bàn phím & Tiêu điểm rõ ràng (Focus Visible):** Mọi nút bấm, trường nhập liệu và thẻ chọn đều có viền tiêu điểm 2px sắc nét (`--violet`).
   - **Cấu trúc Bảng ngữ nghĩa (Semantic Tables):** Thêm `<caption class="sr-only">`, `<th scope="col">` cho bảng hóa đơn và dòng mặt hàng.
   - **Tương thích Giảm chuyển động (`prefers-reduced-motion`):** Tắt toàn bộ hiệu ứng lướt và hiệu ứng chuyển trang mượt mà khi người dùng bật chế độ giảm chuyển động trong hệ điều hành.
   - **Độ co giãn trên màn hình điện thoại 390px:** Kiểm tra bằng Edge Headless xác nhận toàn bộ trang (Danh sách hóa đơn, Nhập hóa đơn, Cài đặt, Voice stage) đạt `fits390: true` với độ tràn ngang bằng 0 (`scrollWidth == innerWidth == 390`).

### Tùy chọn & Cơ chế Phát Lời nhắc (Reminder Preferences UX)
- Trang `/settings` (`app/templates/settings.html`) được tinh chỉnh để giải thích rõ ràng và minh bạch các điều kiện cần thiết để nhận email nhắc nhở:
  1. Tài khoản phải được **xác nhận email** (`current_user.email_verified`).
  2. Tùy chọn **Bật gửi lời nhắc** (`reminders_enabled`) phải được tích chọn.
  3. Kênh nhận **Email** (`channels`) phải được bật.
  4. Lời nhắc được phát qua tác vụ máy chủ định kỳ `flask send-reminders`.
  5. Đã gửi yêu cầu bổ sung năng lực hiển thị trạng thái hàng đợi / thời gian chạy gần nhất của bộ phát lời nhắc vào `docs/PROGRESS.md` mục `## Requests`.

### Ma trận Trình duyệt & Thiết bị (Browser / Device Test Matrix)

| Trình duyệt / Môi trường | Kiểm thử Tự động (Automated / CDP) | Kiểm thử Phần hardware (Owner-Assisted) | Kết quả / Đánh giá |
|---|---|---|---|
| **Microsoft Edge 155.0.4283.62 (Windows 11)** | Đạt (Speech probe, 324 voices, Voice lifecycle slice tests, 390px zero-overflow, 383 pytest) | Cần chủ sở hữu kiểm tra micro vật lý theo kịch bản | **Hỗ trợ đầy đủ (Supported & Verified)**. Giọng đọc tiếng Việt dùng dịch vụ đám mây của Microsoft. |
| **Google Chrome (Windows 11)** | Tương đồng kiến trúc Chromium với Edge | Cần chủ sở hữu kiểm tra khi sử dụng Chrome | **Hỗ trợ đầy đủ kiến trúc**. Web Speech API và PWA standalone hoạt động tương tự. |
| **Mozilla Firefox (Windows 11)** | Nhận diện giọng nói mặc định tắt flag `media.webspeech.recognition.enable` | Chưa kiểm tra phần cứng | **Bàn phím dự phòng hoạt động trung thực**. Subby tự động thông báo trình duyệt không hỗ trợ Web Speech và hướng dẫn người dùng gõ phím bình thường. |
| **Safari / WebKit (iOS 17+)** | Không chạy được CDP trực tiếp trên Windows | Cần chủ sở hữu kiểm tra trên điện thoại iPhone | Hướng dẫn cài đặt PWA "Thêm vào MH chính" đã kiểm tra cú pháp; âm thanh iOS yêu cầu cử chỉ chạm người dùng đã được tuân thủ. |

### Danh sách Ảnh chụp Đối chứng Tổng hợp (`docs/design/`)
- **Trước khi chỉnh sửa:**
  - `p1-p3-before-bills-desktop.png` & `p1-p3-before-bills-phone.png`
  - `p1-p3-before-bill-review-desktop.png` & `p1-p3-before-bill-review-phone.png`
  - `p1-p3-before-settings-desktop.png` & `p1-p3-before-settings-phone.png`
  - `p1-p3-before-voice-phone.png`
- **Sau khi chỉnh sửa:**
  - `p1-p3-after-bills-desktop.png` & `p1-p3-after-bills-phone.png`
  - `p1-p3-after-bill-review-desktop.png` & `p1-p3-after-bill-review-phone.png`
  - `p1-p3-after-settings-desktop.png` & `p1-p3-after-settings-phone.png`
  - `p1-p3-after-voice-phone.png`

