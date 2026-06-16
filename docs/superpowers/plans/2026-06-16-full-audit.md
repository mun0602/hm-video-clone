# Full Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thực hiện full audit (Security + Code Quality + Performance + Dependencies) trên project `hm-video-clone`, output là báo cáo markdown `docs/audit/2026-06-16-full-audit.md` với findings được verify và severity ranking.

**Architecture:** Coordinator scan project → fan-out 4 specialized agents (Backend Security, Frontend Security + Perf, Dependencies, Code Quality) chạy song song → per-agent self-verify (Read lại file:line) → adversarial verify cho Critical (3/3 votes) và High (2/3 votes) findings → synthesis agent dedup + sort + viết markdown report.

**Tech Stack:** Read/Grep/Glob tools (LLM-based static analysis), JSON intermediate files, Markdown output. **KHÔNG** cài thêm tool nào (no npm audit, bandit, semgrep, eslint runtime) — đây là static analysis only.

**Lưu ý:** Project không phải git repo, nên "commit" = save state file (JSON intermediate hoặc update report). KHÔNG dùng `git commit` ở bất kỳ step nào.

---

## File Structure

| Path | Loại | Responsibility |
|---|---|---|
| `docs/superpowers/specs/2026-06-16-full-audit-design.md` | Input (đã có) | Spec đã duyệt |
| `docs/superpowers/plans/2026-06-16-full-audit.md` | Input (file này) | Implementation plan |
| `docs/audit/2026-06-16-full-audit.md` | Output (cuối) | Báo cáo audit |
| `.remember/tmp/audit-2026-06-16/scope-map.md` | Intermediate | Scope mapping cho 4 agents |
| `.remember/tmp/audit-2026-06-16/findings-backend-security.json` | Intermediate | Findings Agent 1 |
| `.remember/tmp/audit-2026-06-16/findings-frontend-security-perf.json` | Intermediate | Findings Agent 2 |
| `.remember/tmp/audit-2026-06-16/findings-deps.json` | Intermediate | Findings Agent 3 |
| `.remember/tmp/audit-2026-06-16/findings-code-quality.json` | Intermediate | Findings Agent 4 |
| `.remember/tmp/audit-2026-06-16/verification-log.md` | Intermediate | Log adversarial verify results |
| `.remember/tmp/audit-2026-06-16/synthesis-decisions.md` | Intermediate | Dedup decisions, severity justifications |

Tất cả file intermediate ở `.remember/tmp/` — KHÔNG commit lên repo (Mun ca sẽ review và xóa khi cần).

---

## Task 1: Coordinator scan & scope mapping

**Files:**
- Create: `.remember/tmp/audit-2026-06-16/scope-map.md`

- [ ] **Step 1: Đếm files theo category**

Dùng Glob:
- `backend/**/*.py` → đếm tổng + list
- `frontend/src/**/*.{js,jsx,ts,tsx}` → đếm tổng + list
- `frontend/public/**` → đếm
- `frontend/*.{json,js,ts,config-overrides.js,nginx.conf}` → đếm
- `backend/*.{txt,cfg,toml,env,example}` → đếm
- `frontend/Dockerfile.dev`, `frontend/docker-compose.dev.yml` → đọc

- [ ] **Step 2: Đọc configs quan trọng để lấy context**

Đọc song song:
- [frontend/.env](frontend/.env) và [frontend/.env.example](frontend/.env.example)
- [backend/.env](backend/.env) và [backend/.env.example](backend/.env.example)
- [frontend/nginx.conf](frontend/nginx.conf)
- [frontend/Dockerfile.dev](frontend/Dockerfile.dev)
- [frontend/config-overrides.js](frontend/config-overrides.js)
- [frontend/.babelrc](frontend/.babelrc)
- [frontend/.dockerignore](frontend/.dockerignore)
- [backend/config.py](backend/config.py)

- [ ] **Step 3: Build scope map**

Tạo file `.remember/tmp/audit-2026-06-16/scope-map.md` với format:

```markdown
# Scope Map — hm-video-clone audit 2026-06-16

## Tổng quan
- Backend: <N> Python files
- Frontend src: <N> JS/JSX/TS files
- Configs: <N> files
- Dependencies: <N> packages (FE) / <N> packages (BE)

## Backend files (cho Agent 1)
<list file paths>

## Frontend src files (cho Agent 2)
<list file paths>

## Deps files (cho Agent 3)
- frontend/package.json
- frontend/package-lock.json
- backend/requirements.txt (nếu có)
- backend/requirements*.txt (nếu có)

## Code quality scope (cho Agent 4)
- Toàn bộ backend/*.py
- Toàn bộ frontend/src/**

## Env vars detected
<list biến môi trường từ .env files, KHÔNG ghi giá trị — chỉ key names>

## Tech stack detected
- Backend: <liệt kê từ imports/deps>
- Frontend: <liệt kê từ package.json>
```

- [ ] **Step 4: Save scope map**

Output: file `.remember/tmp/audit-2026-06-16/scope-map.md` đã được tạo. Verify bằng cách đọc lại file.

---

## Task 2: Dispatch 4 specialist agents (parallel)

**Files:**
- Create: `.remember/tmp/audit-2026-06-16/findings-backend-security.json`
- Create: `.remember/tmp/audit-2026-06-16/findings-frontend-security-perf.json`
- Create: `.remember/tmp/audit-2026-06-16/findings-deps.json`
- Create: `.remember/tmp/audit-2026-06-16/findings-code-quality.json`

- [ ] **Step 1: Dispatch 4 agents song song**

Mỗi agent được invoke với prompt cụ thể + scope map từ Task 1. Tất cả 4 agent PHẢI chạy song song (1 message, 4 Agent tool calls).

**Agent 1 prompt template (Backend Security):**
```
You are auditing the FastAPI backend in /Users/mun/Documents/code/hm-video-clone/backend/.

Read scope map first: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/scope-map.md

Tìm các vấn đề bảo mật trong các file Python backend:
- SQL injection (raw SQL queries, string formatting trong queries)
- Hardcoded secrets, passwords, API keys
- CORS misconfig
- Auth bypass (thiếu check role/permission)
- Input validation (file upload, query params, body)
- File upload validation (extension, content type, size, path traversal)
- Error handling (có leak stack trace, sensitive info)
- Insecure deserialization
- Missing rate limiting
- IDOR (Insecure Direct Object Reference)

Output JSON format (CHÍNH XÁC):
{
  "agent": "backend-security",
  "findings": [
    {
      "id": "F-BE-SEC-001",
      "severity": "critical|high|medium|low",
      "title": "...",
      "category": "security",
      "location": "file:line",
      "issue": "...",
      "code_snippet": "..." (optional, max 10 lines),
      "impact": "...",
      "fix_suggestion": "...",
      "effort": "S|M|L",
      "confidence": "high|medium|low"
    }
  ]
}

Quy tắc:
- Mỗi finding có location cụ thể. SAU KHI ghi finding, BẮT BUỘC Read lại file:line để confirm.
- Nếu không tìm thấy pattern đã mô tả khi re-read → BỎ finding đó, không output.
- Nếu không có finding nào → return {"agent":"backend-security","findings":[]}
- Đặt ID tuần tự F-BE-SEC-001, F-BE-SEC-002, ...

Save to: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/findings-backend-security.json
```

**Agent 2 prompt template (Frontend Security + Perf):**
```
You are auditing the React frontend in /Users/mun/Documents/code/hm-video-clone/frontend/src/.

Read scope map first: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/scope-map.md

Tìm:
SECURITY:
- XSS (dangerouslySetInnerHTML, unescaped user input trong render)
- Supabase RLS (có check quyền ở client không, hay chỉ tin tưởng backend)
- Secrets trong code (API keys hardcoded)
- Insecure localStorage usage (lưu token ở localStorage thay vì httpOnly cookie)
- CSRF protection
- Open redirect (window.location từ user input)

PERFORMANCE:
- Bundle size concerns (import toàn bộ lib thay vì tree-shake)
- Thiếu lazy loading / code splitting (React.lazy, dynamic import)
- Unnecessary re-renders (missing memo, useCallback, useMemo)
- Large dependencies không dùng đến
- Image/video không có lazy loading

Output JSON format:
{
  "agent": "frontend-security-perf",
  "findings": [
    {
      "id": "F-FE-001",
      "severity": "critical|high|medium|low",
      "title": "...",
      "category": "security|performance",
      "location": "file:line",
      "issue": "...",
      "code_snippet": "..." (optional, max 10 lines),
      "impact": "...",
      "fix_suggestion": "...",
      "effort": "S|M|L",
      "confidence": "high|medium|low"
    }
  ]
}

Quy tắc tương tự Agent 1: self-verify bằng Read, bỏ finding nếu không confirm được.
ID: F-FE-001, F-FE-002, ...

Save to: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/findings-frontend-security-perf.json
```

**Agent 3 prompt template (Dependencies):**
```
You are auditing dependencies in /Users/mun/Documents/code/hm-video-clone/.

Read scope map first: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/scope-map.md

Đọc:
- frontend/package.json
- frontend/package-lock.json (tìm resolved versions)
- backend/requirements.txt (nếu tồn tại)
- backend/requirements*.txt (nếu có)

Tìm:
- Packages có KNOWN CVE (từ training data của bạn — KHÔNG chạy npm audit, static only)
- Outdated majors (e.g., major version mới hơn đã release stable)
- Abandoned libs (không update >2 năm, theo training data)
- License conflicts (GPL trong commercial, missing license)
- Duplicate functionality (2 libs làm cùng việc)

Lưu ý: Bạn có thể không nhớ hết CVE. Chỉ flag findings bạn CONFIDENT. Nếu không chắc → skip.

Output JSON format:
{
  "agent": "dependencies",
  "findings": [
    {
      "id": "F-DEP-001",
      "severity": "critical|high|medium|low",
      "title": "...",
      "category": "dependency",
      "package_name": "...",
      "current_version": "...",
      "fixed_version": "..." (nếu applicable),
      "issue": "...",
      "impact": "...",
      "fix_suggestion": "...",
      "effort": "S|M|L",
      "confidence": "high|medium|low"
    }
  ]
}

ID: F-DEP-001, F-DEP-002, ...

Save to: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/findings-deps.json
```

**Agent 4 prompt template (Code Quality + Perf):**
```
You are auditing code quality and performance in /Users/mun/Documents/code/hm-video-clone/.

Read scope map first: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/scope-map.md

Tìm:
CODE QUALITY:
- Dead code (functions không được gọi, unused imports, commented-out code blocks >5 lines)
- Code smells (file >500 dòng, function >100 dòng, deep nesting >4 levels)
- Inconsistent error handling (try/except trong file này nhưng không có ở file khác tương tự)
- Magic numbers, hardcoded strings lặp lại
- Logging: print() thay vì logger, hoặc logger không consistent
- Naming: snake_case vs camelCase không nhất quán
- Type hints missing

PERFORMANCE:
- N+1 queries (loop gọi DB mà có thể dùng joinedload/eager load)
- Thiếu DB indexes (query thường xuyên filter/sort mà không có index trên column đó — check models.py)
- Synchronous I/O trong async context (FastAPI)
- Không cache kết quả tốn kém

Output JSON format:
{
  "agent": "code-quality",
  "findings": [
    {
      "id": "F-CQ-001",
      "severity": "critical|high|medium|low",
      "title": "...",
      "category": "quality|performance",
      "location": "file:line",
      "issue": "...",
      "code_snippet": "..." (optional, max 10 lines),
      "impact": "...",
      "fix_suggestion": "...",
      "effort": "S|M|L",
      "confidence": "high|medium|low"
    }
  ]
}

ID: F-CQ-001, F-CQ-002, ...

Save to: /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/findings-code-quality.json
```

- [ ] **Step 2: Verify 4 JSON files đã được tạo**

Sau khi 4 agents hoàn thành, check:
```bash
ls -la /Users/mun/Documents/code/hm-video-clone/.remember/tmp/audit-2026-06-16/findings-*.json
```

Expected: 4 files, mỗi file có format JSON hợp lệ với `findings` array.

Nếu thiếu file → dispatch lại agent tương ứng. Nếu file rỗng (0 findings) → OK, tiếp tục.

- [ ] **Step 3: Sanity check findings count**

Đọc 4 file JSON, đếm tổng findings. Nếu >100 → có thể có false positive, ghi nhận để verify kỹ hơn ở Task 3.

---

## Task 3: Per-agent self-verify (catch hallucinated locations)

**Files:**
- Modify: 4 findings JSON files (xoá findings có location không tồn tại)

- [ ] **Step 1: Verify Agent 1 (Backend Security)**

Đọc `.remember/tmp/audit-2026-06-16/findings-backend-security.json`. Với mỗi finding:
1. Parse `location` → tách file và line number
2. Read file đó, jump đến line đó (dùng offset/limit)
3. Nếu pattern trong `issue` không match nội dung file tại line đó → BỎ finding, ghi log "F-BE-SEC-XXX removed: location mismatch"
4. Nếu match → giữ

- [ ] **Step 2: Verify Agent 2 (Frontend Security + Perf)**

Tương tự Step 1 cho file `findings-frontend-security-perf.json`.

- [ ] **Step 3: Verify Agent 3 (Dependencies)**

Với mỗi finding trong `findings-deps.json`:
1. Đọc `package.json` hoặc `package-lock.json`
2. Confirm `current_version` thực sự tồn tại trong deps
3. Nếu không → bỏ finding

Lưu ý: Agent 3 không có file:line location, chỉ có package_name. Verify dựa trên package metadata.

- [ ] **Step 4: Verify Agent 4 (Code Quality)**

Tương tự Step 1 cho file `findings-code-quality.json`.

- [ ] **Step 5: Log removed findings**

Tạo/ghi file `.remember/tmp/audit-2026-06-16/verification-log.md`:

```markdown
# Self-verify log — Audit 2026-06-16

## Agent 1 (Backend Security)
- Input: <N> findings
- Removed (location mismatch): <list ID>
- Kept: <N> findings

## Agent 2 (Frontend Security + Perf)
- Input: <N> findings
- Removed: <list ID>
- Kept: <N> findings

## Agent 3 (Dependencies)
- Input: <N> findings
- Removed (package not in deps): <list ID>
- Kept: <N> findings

## Agent 4 (Code Quality)
- Input: <N> findings
- Removed: <list ID>
- Kept: <N> findings

## Tổng
- Input: <N>
- Removed: <N>
- Kept: <N>
```

- [ ] **Step 6: Save updated JSONs**

Ghi đè 4 file JSON với findings đã được filter (đã loại bỏ các location mismatch).

---

## Task 4: Adversarial verify cho Critical & High findings

**Files:**
- Modify: `.remember/tmp/audit-2026-06-16/verification-log.md` (append)

- [ ] **Step 1: Lấy danh sách Critical & High findings**

Đọc 4 file JSON, collect tất cả findings có `severity` = "critical" hoặc "high". Ghi nhận ID list.

- [ ] **Step 2: Spawn 1 verifier agent per Critical finding**

Với MỖI Critical finding, dispatch 1 verifier agent với prompt:
```
You are an adversarial verifier. Your job is to REFUTE the following finding.
Default to REFUTED=true if you find ANY evidence against it.

Finding to verify:
{json của finding}

Project: /Users/mun/Documents/code/hm-video-clone/

Read the code at the location mentioned. Try to find:
- Is the issue actually exploitable in production?
- Is there mitigation elsewhere that the original finding missed?
- Is the severity actually lower than claimed?

Output:
{
  "finding_id": "...",
  "verdict": "real|refuted",
  "evidence": "...",
  "suggested_severity": "critical|high|medium|low|null"
}
```

Chạy SONG SONG (multiple Agent tool calls in one message) cho tất cả Critical findings.

- [ ] **Step 3: Spawn 2 verifier agents per High finding, lấy 2/3 votes**

Tương tự Step 2, nhưng:
- Với MỖI High finding, dispatch 2 verifier agents
- Cùng prompt template
- Nếu ≥2/2 (cả 2) verdict "real" → giữ
- Nếu 0/2 hoặc 1/2 verdict "real" → bỏ hoặc hạ severity xuống "medium"

- [ ] **Step 4: Apply verdicts**

Với mỗi finding:
- Nếu bị refute → bỏ khỏi JSON, ghi log "F-XXX removed: refuted by N/M verifiers"
- Nếu verdict "real" + suggested_severity khác với ban đầu → update severity
- Nếu verdict "real" + same severity → giữ nguyên

- [ ] **Step 5: Log adversarial results**

Append vào `.remember/tmp/audit-2026-06-16/verification-log.md`:

```markdown
## Adversarial verify

### Critical findings
- F-XXX: verdict=real (3/3), kept
- F-YYY: verdict=refuted (1/3 real), removed
- ...

### High findings
- F-AAA: verdict=real (2/2), kept
- F-BBB: verdict=refuted (0/2), removed/downgraded
- ...
```

- [ ] **Step 6: Save updated JSONs**

Ghi đè 4 file JSON sau khi đã apply verdicts.

---

## Task 5: Synthesis — dedup, sort, viết markdown report

**Files:**
- Create: `.remember/tmp/audit-2026-06-16/synthesis-decisions.md`
- Create: `docs/audit/2026-06-16-full-audit.md`

- [ ] **Step 1: Collect all kept findings từ 4 JSON files**

Đọc 4 file JSON, build 1 list tổng các findings đã được verify.

- [ ] **Step 2: Dedup**

Với mỗi cặp findings có cùng `location` (file:line) hoặc cùng vấn đề mô tả (semantic match):
- Giữ 1 finding
- Nếu 2 findings có severity khác nhau → lấy severity CAO hơn
- Ghi log dedup decision: "F-XXX merged with F-YYY (same location)"

Ghi log vào `synthesis-decisions.md`:
```markdown
# Synthesis Decisions

## Dedup
- F-XXX merged with F-YYY (location: backend/main.py:23)
- F-AAA merged with F-BBB (location: frontend/src/...)
- ...

## Severity adjustments
- F-XXX: kept (no change)
- F-YYY: high → medium (downgraded after verify)
- ...
```

- [ ] **Step 3: Sort theo severity**

Critical → High → Medium → Low. Trong cùng severity, sort theo file path alphabetical.

- [ ] **Step 4: Build summary stats**

Đếm:
- Tổng findings
- Count per severity
- Count per file (build bảng tổng hợp theo file)

- [ ] **Step 5: Viết markdown report**

Tạo file `docs/audit/2026-06-16-full-audit.md`:

```markdown
# Full Audit Report — hm-video-clone

**Ngày:** 2026-06-16
**Phạm vi:** Backend (FastAPI/SQLAlchemy/R2) + Frontend (React/Supabase)
**Phương pháp:** Static analysis, parallel specialized agents (4) + adversarial verification
**Tổng findings:** <N> (🔴 Critical: <a> | 🟠 High: <b> | 🟡 Medium: <c> | 🟢 Low: <d>)

---

## 🔴 Critical (<a>)

### F-001: <title>
- **Category:** <category>
- **Location:** <file:line>
- **Issue:** <mô tả cụ thể>
- **Impact:** <hậu quả nếu không sửa>
- **Fix suggestion:** <hướng sửa>
- **Effort:** S/M/L
- **Confidence:** high/medium/low

(repeat cho mỗi critical finding)

---

## 🟠 High (<b>)

(repeat format tương tự)

---

## 🟡 Medium (<c>)

(repeat format tương tự)

---

## 🟢 Low (<d>)

(repeat format tương tự)

---

## Bảng tổng hợp theo file

| File | Critical | High | Medium | Low |
|---|---|---|---|---|
| <file> | <n> | <n> | <n> | <n> |
| ... |

---

## Top 5 khuyến nghị ưu tiên

1. [Critical] F-XXX: <title> — <1-line impact>
2. [Critical] F-YYY: <title> — <1-line impact>
3. [High] F-AAA: <title> — <1-line impact>
4. [High] F-BBB: <title> — <1-line impact>
5. [Medium] F-CCC: <title> — <1-line impact>

---

## Phụ lục

### A. Phương pháp
- Static analysis only (no runtime testing)
- 4 parallel specialist agents (Backend Security, Frontend Security + Perf, Dependencies, Code Quality)
- 3-layer verification: per-agent self-verify → adversarial verify cho Critical (3/3 votes) + High (2/2 votes) → synthesis self-review
- KHÔNG cài thêm tools (no npm audit, bandit, eslint runtime)

### B. Files đã quét
<list files theo scope-map>

### C. Findings removed during verification
<reference verification-log.md>
```

- [ ] **Step 6: Self-review report**

Trước khi output cuối, check:
- 100% findings có file:line đã được verify
- 0 placeholder ("TBD", "TODO", "...")
- Severity nhất quán
- Mỗi finding có Impact + Fix suggestion

Nếu có issue → fix inline.

---

## Task 6: Final review & handoff

**Files:**
- Output to user: summary table

- [ ] **Step 1: Đọc lại report cuối**

Đọc `docs/audit/2026-06-16-full-audit.md`. Verify:
- Có tất cả sections (Critical/High/Medium/Low + bảng tổng hợp + top 5)
- Format nhất quán
- Không có broken markdown

- [ ] **Step 2: In summary cho Mun ca**

Output trong conversation:
```
✅ Audit hoàn thành

📄 Báo cáo: docs/audit/2026-06-16-full-audit.md
📊 Tổng findings: <N> (🔴 <a> | 🟠 <b> | 🟡 <c> | 🟢 <d>)

Top 3 critical/high:
1. <F-XXX>: <title> — <file:line>
2. <F-YYY>: <title> — <file:line>
3. <F-AAA>: <title> — <file:line>

📁 Intermediate files (không commit):
- .remember/tmp/audit-2026-06-16/scope-map.md
- .remember/tmp/audit-2026-06-16/findings-*.json
- .remember/tmp/audit-2026-06-16/verification-log.md
- .remember/tmp/audit-2026-06-16/synthesis-decisions.md

Mun ca review report và quyết định findings nào cần fix.
```

- [ ] **Step 3: Cleanup (optional, hỏi Mun ca trước)**

Hỏi Mun ca: "Có muốn xóa intermediate files ở `.remember/tmp/audit-2026-06-16/` không?"
- Nếu có → rm các JSON/log files
- Nếu không → giữ lại để debug/reproduce

---

## Self-Review Checklist (run before claiming done)

- [ ] 6 tasks đều có file outputs cụ thể
- [ ] 0 placeholder trong plan (no TBD, TODO, "fill in later", "similar to Task N")
- [ ] Mỗi step có code/output cụ thể (không chỉ "do this")
- [ ] File paths đều absolute từ project root
- [ ] Agent prompts ở Task 2 có đầy đủ JSON schema, ID format, save path
- [ ] Adversarial verify ở Task 4 có logic rõ ràng (3/3 cho Critical, 2/2 cho High)
- [ ] Synthesis ở Task 5 có dedup logic, sort logic, report template đầy đủ
- [ ] Final report có tất cả sections theo spec
