# Full Audit Report — hm-video-clone (Backend)

**Ngày:** 2026-06-16
**Scope:** Backend (`backend/*.py`)
**Method:** Static Analysis (Security, Quality, Performance, Dependencies)
**Tổng findings:** 6

## 🔴 Critical (1)

### 1. Plaintext Password Storage
- **Location:** `backend/main.py` (lines 119, 138)
- **Issue:** Mật khẩu người dùng được lưu trực tiếp dưới dạng plain text thay vì mã hóa (hashing). Cột `hashed_password` đang được gán thẳng bằng giá trị `password` nhận được từ Frontend.
- **Impact:** Nếu Database bị rò rỉ, hacker sẽ có toàn bộ mật khẩu thực tế của người dùng. Gây rủi ro bảo mật cực kỳ nghiêm trọng.
- **Fix:** Sử dụng thư viện `passlib` (với thuật toán `bcrypt`) để băm mật khẩu trước khi lưu vào database, và sử dụng hàm `verify` khi người dùng login.
- **Effort:** Low

## 🟠 High (2)

### 2. Thiếu cơ chế Authentication Middleware (Token Validation)
- **Location:** `backend/main.py` (hàm `execute_rpc`, line 195)
- **Issue:** Các API chức năng như `insert_video`, `toggle_like`, `toggle_follow` đang lấy trực tiếp `user_id` từ payload mà phía Frontend gửi lên.
- **Impact:** Dễ dàng bị khai thác lỗ hổng IDOR (Insecure Direct Object Reference). Hacker có thể sửa payload, gửi `user_id` của người khác để thao tác (like, follow, đăng video) thay cho người đó.
- **Fix:** Triển khai JWT validation middleware (`Depends`). FastAPI phải giải mã JWT token (nhận từ header `Authorization`) để trích xuất `user_id` một cách an toàn thay vì tin tưởng payload client gửi lên.
- **Effort:** Medium

### 3. Thiếu file quản lý Dependencies (`requirements.txt`)
- **Location:** `backend/`
- **Issue:** Không có file `requirements.txt` hoặc `Pipfile` / `pyproject.toml` để quản lý version của các thư viện (FastAPI, SQLAlchemy, ...).
- **Impact:** Không thể theo dõi được các lỗ hổng bảo mật (CVE) từ thư viện cũ. Khi deploy lên production hoặc dev khác setup sẽ gây lỗi "ModuleNotFoundError".
- **Fix:** Chạy lệnh `pip freeze > requirements.txt` để snapshot danh sách thư viện đang sử dụng.
- **Effort:** Low

## 🟡 Medium (2)

### 4. N+1 Queries (Performance Bottleneck)
- **Location:** `backend/main.py` (hàm `execute_rpc`, lines 224-243)
- **Issue:** Trong vòng lặp `for video in videos:` để xuất dữ liệu Feed, backend đang gọi 4 query rời rạc: đếm likes, đếm comments, kiểm tra `is_liked`, kiểm tra `is_followed`. Với limit 10 videos, backend sẽ gọi 40+1 queries!
- **Impact:** Gây nghẽn API cực kỳ nghiêm trọng (Performance degradation) khi hệ thống lớn dần. Tiêu tốn kết nối DB và tài nguyên I/O.
- **Fix:** Sử dụng cơ chế `joinedload`, subqueries hoặc `func.count` kết hợp `GROUP BY` của SQLAlchemy để tổng hợp toàn bộ dữ liệu chỉ bằng 1 hoặc 2 query lớn.
- **Effort:** High

### 5. Cấu hình CORS cứng (Hardcoded)
- **Location:** `backend/main.py` (lines 23-26)
- **Issue:** CORS `allow_origins` đang được hardcode cho `http://localhost:3000`.
- **Impact:** Backend sẽ block request khi đưa Frontend lên môi trường Production (với domain thực tế).
- **Fix:** Đưa danh sách origin vào file `.env` (ví dụ: `CORS_ORIGINS`) và gọi vào `main.py` thông qua `settings.CORS_ORIGINS`.
- **Effort:** Low

## 🟢 Low (1)

### 6. Kiến trúc Monolithic
- **Location:** `backend/main.py`
- **Issue:** Toàn bộ code xử lý API (Auth, Storage, RPC queries) đều nằm chung trong file `main.py` dài gần 500 dòng.
- **Impact:** Khó bảo trì, khó debug và dễ gây Merge Conflict nếu nhiều người cùng làm việc.
- **Fix:** Chia tách code ra thành các thư mục `routers/` (ví dụ: `routers/auth.py`, `routers/storage.py`, `routers/feed.py`) và dùng `APIRouter` để include vào `main.py`.
- **Effort:** Medium

---

## 🔝 Top 3 Khuyến nghị Ưu tiên xử lý ngay:
1. **Fix Plaintext Passwords:** Mã hóa mật khẩu bằng `bcrypt` ngay lập tức để bảo vệ dữ liệu người dùng.
2. **Triển khai JWT / Token Auth:** Lấy `user_id` từ token chuẩn hóa để ngăn chặn lỗ hổng IDOR.
3. **Sửa N+1 Queries:** Tối ưu hóa API trả về Feed Video để tránh Database bị quá tải.
