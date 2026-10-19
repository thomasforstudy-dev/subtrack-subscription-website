# Kho skill tham khảo

Đã tải toàn bộ repo [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills).
Đây là kho lưu trữ để đọc và chọn skill, chưa cài hay kích hoạt trong Codex, Claude Code hoặc Antigravity.

- Nguồn: `agentic-awesome-skills/`
- Skill gốc: `agentic-awesome-skills/skills/<skill-id>/SKILL.md`
- Danh mục đầy đủ: `agentic-awesome-skills/CATALOG.md`
- Phiên bản package: `19.10.1`
- Commit đã tải: `369d1ca5fb0196f64e225e1fb464a72a09509f1e`
- Ngày tải: 19/10/2026.

Repo nguồn được bỏ qua bởi Git của SubTrack để không đưa hàng nghìn file thư viện lên repo ứng dụng. File hướng dẫn này và danh sách gợi ý vẫn có thể lưu cùng dự án.

`pytest.ini` ở gốc SubTrack giới hạn test mặc định vào `tests/` và bỏ qua `skill-library/`, tránh chạy nhầm test của thư viện tham khảo.

## Gợi ý theo nhu cầu

Các mô tả dưới đây được đối chiếu với nội dung skill ở commit trên. Đây là gợi ý để lựa chọn, không phải xác nhận rằng mọi hướng dẫn đều tương thích với môi trường của bạn. Đọc skill trước khi sử dụng; không tự chạy các ví dụ hay cài thêm dependency.

### UI/UX và frontend

| Skill | Khi nên dùng |
|---|---|
| [ui-ux-designer](agentic-awesome-skills/skills/ui-ux-designer/SKILL.md) | Thiết kế luồng người dùng, wireframe, hệ thống giao diện. |
| [ui-ux-pro-max](agentic-awesome-skills/skills/ui-ux-pro-max/SKILL.md) | Tham khảo màu sắc, font, bố cục và nguyên tắc UX. |
| [ux-audit](agentic-awesome-skills/skills/ux-audit/SKILL.md) | Kiểm tra trang đang có để tìm điểm khó sử dụng. |
| [ui-a11y](agentic-awesome-skills/skills/ui-a11y/SKILL.md) | Kiểm tra bàn phím, nhãn biểu mẫu, tương phản và khả năng tiếp cận. |
| [frontend-design](agentic-awesome-skills/skills/frontend-design/SKILL.md) | Xây giao diện theo thương hiệu và framework hiện có. |
| [frontend-security-coder](agentic-awesome-skills/skills/frontend-security-coder/SKILL.md) | Rà soát XSS, dữ liệu đầu vào và cách hiển thị nội dung người dùng. |

Với SubTrack: ưu tiên `frontend-design`, `ux-audit`, `ui-a11y`. Giữ Jinja, CSS thuần và JavaScript hiện có; giữ thiết kế trong `DESIGN.md`. Không đưa React, Next.js hay Tailwind vào dự án nếu chủ dự án chưa đồng ý.

### Python

| Skill | Khi nên dùng |
|---|---|
| [python-patterns](agentic-awesome-skills/skills/python-patterns/SKILL.md) | Tổ chức Python và cân nhắc cách triển khai phù hợp. |
| [python-pro](agentic-awesome-skills/skills/python-pro/SKILL.md) | Viết, đọc và review Python; có nội dung về Flask và thư viện ML. |
| [python-testing-patterns](agentic-awesome-skills/skills/python-testing-patterns/SKILL.md) | Viết pytest, fixtures, mock và kiểm tra hồi quy. |
| [python-performance-optimization](agentic-awesome-skills/skills/python-performance-optimization/SKILL.md) | Đo CPU/bộ nhớ và tìm nguyên nhân code chậm trước khi tối ưu. |
| [systematic-debugging](agentic-awesome-skills/skills/systematic-debugging/SKILL.md) | Tái hiện lỗi, kiểm tra bằng chứng và tìm nguyên nhân. |

Với SubTrack: bắt đầu bằng `python-pro`, `python-testing-patterns`, `systematic-debugging`. Giữ code dễ hiểu theo `AGENTS.md`, không mặc định chuyển Flask sang FastAPI hoặc thêm kiến trúc phức tạp.

### PyTorch và machine learning

| Skill | Khi nên dùng |
|---|---|
| [ml-engineer](agentic-awesome-skills/skills/ml-engineer/SKILL.md) | Skill sát PyTorch nhất trong nhóm gợi ý: PyTorch 2.x, training, inference, model serving. |
| [data-scientist](agentic-awesome-skills/skills/data-scientist/SKILL.md) | Phân tích dữ liệu, thống kê và đánh giá mô hình. |
| [llm-fine-tuning](agentic-awesome-skills/skills/llm-fine-tuning/SKILL.md) | Nhu cầu nâng cao: LoRA/QLoRA và huấn luyện LLM với Hugging Face. |

Ưu tiên `ml-engineer` cùng `python-testing-patterns` cho dự án PyTorch. Các skill này không cài PyTorch/CUDA hay cung cấp GPU. SubTrack hiện chưa cần bổ sung ML; chỉ dùng nhóm này cho nhiệm vụ ML được yêu cầu riêng.

### Backend và API

| Skill | Khi nên dùng |
|---|---|
| [api-design-principles](agentic-awesome-skills/skills/api-design-principles/SKILL.md) | Thiết kế endpoint, cấu trúc request/response và mã lỗi. |
| [backend-security-coder](agentic-awesome-skills/skills/backend-security-coder/SKILL.md) | Kiểm tra xác thực, phân quyền, validation và bảo mật API. |
| [python-pro](agentic-awesome-skills/skills/python-pro/SKILL.md) | Triển khai backend Python phù hợp stack đang có. |

Không ưu tiên `backend-dev-guidelines` cho SubTrack: skill đó tập trung Node.js/Express/TypeScript, khác Flask của dự án.

### SQL và cơ sở dữ liệu

| Skill | Khi nên dùng |
|---|---|
| [sql-pro](agentic-awesome-skills/skills/sql-pro/SKILL.md) | Viết và review truy vấn, JOIN, CTE, tổng hợp dữ liệu. |
| [database-design](agentic-awesome-skills/skills/database-design/SKILL.md) | Thiết kế bảng, quan hệ và chỉ mục. |
| [sql-optimization-patterns](agentic-awesome-skills/skills/sql-optimization-patterns/SKILL.md) | Phân tích truy vấn chậm và kiểm chứng tối ưu bằng dữ liệu phù hợp. |

Các skill SQL không dành riêng cho SQL Server. Khi dùng trong SubTrack, yêu cầu AI áp dụng T-SQL, SQLAlchemy và pyodbc; ví dụ PostgreSQL/SQLite phải được điều chỉnh và kiểm tra. Giữ lọc `user_id`, truy vấn có tham số, không DROP/TRUNCATE hoặc đổi hệ quản trị.

## Bộ ưu tiên cho SubTrack

Chọn theo nhiệm vụ, không cần nạp cả nhóm cùng lúc:

1. Sửa lỗi: `systematic-debugging` + `python-testing-patterns`.
2. Giao diện: `frontend-design` + `ux-audit` + `ui-a11y`.
3. Backend: `python-pro` + `backend-security-coder`.
4. Database: `sql-pro` + `database-design`; thêm `sql-optimization-patterns` khi có truy vấn chậm.

Danh sách máy đọc được nằm trong `recommended-skills.json`; nó chỉ là danh sách tham khảo, không phải manifest tự cài đặt.

## Dùng ngay mà chưa cần cài

Trong Codex, Claude Code hoặc Antigravity mở tại thư mục SubTrack, yêu cầu AI đọc đường dẫn tương đối của skill. Ví dụ:

> Đọc AGENTS.md, DESIGN.md và skill-library/agentic-awesome-skills/skills/ux-audit/SKILL.md. Dùng hướng dẫn phù hợp để đánh giá UX trang dashboard. Giữ Flask/Jinja/CSS thuần. Chỉ báo cáo phát hiện và đề xuất, chưa sửa code.

Với PyTorch, dùng thư mục dự án ML tương ứng và cung cấp đường dẫn tuyệt đối đến `skill-library/agentic-awesome-skills/skills/ml-engineer/SKILL.md` trong SubTrack.

Khi đã chọn được skill muốn dùng thường xuyên, có thể cài riêng vào thư mục skill của từng ứng dụng. Chưa thực hiện bước đó trong lần tải này.
