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

### Phần 3: Thanh điều hướng 6 mục, Tổng quan (Dashboard 5 khối) & Gói đăng ký (Subscriptions)
- **Tệp cập nhật:** `app/templates/base.html`, `app/templates/subscriptions/list.html`, `app/templates/subscriptions/form.html`, `app/static/app-ui.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Thanh điều hướng chính gồm 6 mục rõ ràng: **Tổng quan**, **Gói đăng ký**, **Link đã lưu**, **Hóa đơn / Giao dịch**, **Nhắc nhở**, **Cài đặt** cùng nút mở nhanh trợ lý **Subby** và chuyển ngôn ngữ **VI / EN**.
  - **5 khối Dashboard**:
    1. *Chi dự kiến / tháng theo từng loại tiền tệ* (tính trực tiếp từ `items` thật, tách biệt `VND`, `USD`, ... — không cộng gộp sai lệch giữa các đồng tiền).
    2. *Sắp gia hạn (≤ 14 ngày tới)* kèm số ngày còn lại.
    3. *Cần kiểm tra* (các gói đã qua ngày gia hạn dự kiến).
    4. *Hạn thanh toán thẻ tín dụng* (hiển thị trạng thái Trống trung thực + khu vực xem thử kỳ sao kê thẻ với đầy đủ `Kỳ sao kê`, `Hạn thanh toán`, `Tổng dư nợ`, `Thanh toán tối thiểu`, và ghi rõ `"Chưa có thông tin"` cho trường chưa biết).
    5. *Giao dịch / Hóa đơn gần đây*.
  - Bộ chuyển trạng thái 4 chế độ (`Dữ liệu thật`, `Đang tải`, `Lỗi tải`, `Xem mẫu Demo`) giúp kiểm tra đầy đủ các trạng thái Loading / Empty / Error / Demo mà không trộn dữ liệu giả vào tài khoản thật.
  - Thanh công cụ **Tìm kiếm, Lọc theo chu kỳ, Lọc theo hạn, Sắp xếp** ngay trên bảng gói đăng ký + hộp thoại `<dialog>` xác nhận trước khi bấm **Lưu trữ (Archive)**.

### Phần 4: Quản lý Đường dẫn đã lưu (Pinned Links)
- **Tệp cập nhật:** `app/templates/links/list.html`, `app/templates/links/form.html`, `app/static/link-preview.js`
- **Những gì đã hoàn thiện:**
  - Hiển thị rõ viên thuốc tên miền (`🔗 domain`), URL đầy đủ, trạng thái ghim (`★ Đã ghim`), thẻ phân loại (`#tag`), và trạng thái đang lấy tiêu đề tự động (`Đang tự động lấy tiêu đề trang…` / `Đã tự động điền tiêu đề` / `Không lấy được tiêu đề tự động — bạn có thể tự nhập`).
  - Phát hiện đường dẫn trùng lặp ngay trên trình duyệt khi người dùng dán URL đã có trong danh sách, kèm nút **Mở sửa bản cũ**.
  - Hộp thoại `<dialog>` xác nhận trước khi xóa vĩnh viễn đường dẫn.

### Phần 5: Hóa đơn, Chứng từ OCR & Giao dịch (`_bills_section.html`)
- **Tệp cập nhật:** `app/templates/subscriptions/_bills_section.html`, `app/static/app-ui.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Khu vực tải tệp hỗ trợ `PNG, JPG, WEBP, PDF` (tối đa 10 MB, 5 trang) và thông báo rõ không hỗ trợ trực tiếp tệp Office (`DOCX/DOC`).
  - Thanh tiến trình 4 bước (`1. Tải tệp lên` → `2. Đọc chứng từ (OCR)` → `3. AI đề xuất trường` → `4. Chờ bạn duyệt`) kèm trạng thái báo lỗi & nút **Thử lại**.
  - Màn hình đối chiếu 2 cột trên máy tính (trái: tài liệu gốc từng trang; phải: biểu mẫu các trường giao dịch có thể chỉnh sửa + chế độ xem Markdown) và tự động thu gọn thành **3 Tab** trên điện thoại (`✏️ Trường giao dịch`, `📄 Tài liệu nguồn`, `📝 Markdown`).
  - Cảnh báo chất lượng OCR rõ ràng khi trang bị cắt góc (`Trang 2 bị cắt nhẹ ở mép dưới`), để trống trung thực các trường không rõ (`Chưa xác định`) và làm nổi bật đoạn nguồn tương ứng khi người dùng bấm vào từng ô nhập liệu.

### Phần 6: Trợ lý AI Subby — Chat, Giọng nói & Xác nhận thao tác
- **Tệp cập nhật:** `app/templates/_subby.html`, `app/static/subby.js`, `app/static/style.css`
- **Những gì đã hoàn thiện:**
  - Hiển thị rõ 4 trạng thái giọng nói: **Sẵn sàng** (`idle`), **Đang nghe…** (`listening`), **Đang suy nghĩ…** (`thinking`), **Đang đọc câu trả lời…** (`speaking`) kèm nút **Dừng đọc**.
  - Tự động ẩn nút Micro hoặc hiển thị chú thích lịch sự khi trình duyệt không hỗ trợ Web Speech API.
  - Mọi câu trả lời có đề xuất thao tác thêm/sửa/lưu trữ đều kèm thẻ **Xác nhận thao tác** (`Chờ bạn xác nhận` / `Bỏ qua`) — tuyệt đối không tự ý ghi dữ liệu khi người dùng chưa xác nhận.
  - Giữ cơ chế chỉ hiển thị nút liên hệ chủ web qua Messenger/Zalo khi `.env` cấu hình URL thật.

### Phần 7: Nhắc nhở, Cài đặt, Gmail OAuth Prep, PWA Install & Xuất dữ liệu
- **Tệp cập nhật:** `app/templates/subscriptions/_settings_section.html`, `app/static/favicon.svg`, `app/static/icon-192.svg`, `app/static/manifest.webmanifest`
- **Những gì đã hoàn thiện:**
  - Bộ nhận diện tạm thời (`favicon.svg`, `icon-192.svg`, badge `"Logo tạm"`) và `manifest.webmanifest` hợp lệ cho cài đặt PWA.
  - Phân biệt rõ ràng: **Đăng nhập bằng Google KHÔNG cấp quyền đọc hộp thư Gmail**; khu vực kết nối Gmail đọc hóa đơn hiển thị trạng thái chờ OAuth riêng.
  - Hướng dẫn cài ứng dụng lên màn hình chính (Chrome/Edge & Safari iOS) và xem trước huy hiệu Chrome Extension (đánh dấu rõ `"Chưa phát hành"`).
  - Xuất dữ liệu gói đăng ký hiện có ra tệp `.JSON` hoặc `.CSV` ngay trên trình duyệt.

---

## 2. Kiểm tra Đa màn hình & Ảnh chụp Trước / Sau (`docs/design/`)

Đã kiểm tra bằng Microsoft Edge Headless trên cơ sở dữ liệu SQLite tạm thời:
- **Điện thoại (`390×844`):** `ui-after-landing-phone.png`, `ui-after-register-phone.png`, `ui-after-login-phone.png`, `ui-after-dashboard-phone.png`, `ui-after-links-phone.png`
- **Laptop (`1440×900`):** `ui-after-landing-laptop.png`, `ui-after-dashboard-laptop.png`, `ui-after-links-laptop.png`
- **Desktop (`1920×1080`):** `ui-after-landing-desktop.png`, `ui-after-dashboard-desktop.png`
- **Màn hình thấp (`1366×680`):** `ui-after-dashboard-lowscreen.png`
- **Ảnh hiện trạng trước khi sửa:** `audit-before-landing-phone.png`, `audit-before-landing-laptop.png`, `audit-before-landing-desktop.png`, `audit-before-register-phone.png`, `audit-before-login-phone.png`

---

## 3. Kết quả Chạy Kiểm thử Tự động (`pytest`)

```text
.\.venv\Scripts\python.exe -m pytest -q --basetemp=instance/pytest-ag-verify
68 passed, 4 xfailed in 7.08s
```

---

## 4. Yêu cầu Bàn giao cho Nhánh Backend (Claude / Codex)

Các mục đã được ghi nhận vào mục `## Requests` trong `docs/PROGRESS.md`:
1. **Gộp nhánh `claude/accounts`:** Toàn bộ template trong `app/templates/auth/` và `app/templates/base.html` đã hỗ trợ sẵn `csrf_token()`, `username`, `identifier`, `POST /logout`, `/forgot-password`, `/reset-password/<token>`, `/verify-email/<token>`, và `POST /resend-verification`.
2. **Khôi phục gói đã lưu trữ (Restore Archived Subscriptions):** Truyền thêm `archived_items` vào `subscriptions/list.html` và mở route `POST /subscriptions/<id>/restore`.
3. **API Hóa đơn OCR & Kỳ sao kê thẻ:** Kết nối `#bill-review-form` với endpoint tải tệp (`POST /bills/upload`) và lưu giao dịch đã duyệt (`POST /bills/<id>/confirm`), cùng bảng dữ liệu cho `#credit-cards`.
4. **OAuth Gmail đọc hóa đơn:** Thêm route kết nối/ngắt kết nối OAuth riêng (`/settings/gmail/connect`, `/settings/gmail/disconnect`) tách biệt với đăng nhập Google.
