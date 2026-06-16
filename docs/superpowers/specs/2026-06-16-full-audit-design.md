# Full Audit Design — hm-video-clone

**Ngày:** 2026-06-16
**Trạng thái:** Draft (chờ Mun ca review)
**Project:** hm-video-clone (TikTok clone — React 19 frontend + FastAPI backend)

## Mục đích

Thực hiện full audit (Security + Code quality + Performance + Dependencies) trên toàn bộ project `hm-video-clone`, output là báo cáo markdown có severity ranking để Mun ca quyết định ưu tiên sửa. **Report-only**, không sửa code.

## Scope

### In-scope
- **Backend** [backend/](backend/): FastAPI, SQLAlchemy, R2 storage, models, seed, config
- **Frontend** [frontend/src/](frontend/src/) + configs: React 19, Supabase client, Tailwind, build config
- **Dependencies**: `frontend/package.json`, `package-lock.json`, `backend/requirements*` (nếu tồn tại)
- **Dev config**: `Dockerfile.dev`, `docker-compose.dev.yml`, `nginx.conf`, `.dockerignore`, `.env.example`

### Out-of-scope
- Runtime testing, dynamic analysis (chỉ static)
- Sửa code
- Vendor code trong `node_modules/`, `venv/`
- Database production data
- CI/CD pipeline (chưa phát hiện file trong initial scan)
- Infrastructure bên ngoài Docker

## Approach: Parallel specialized agents

4 specialist agents chạy song song, mỗi agent quét một dimension, output findings JSON. Sau đó synthesis agent tổng hợp thành báo cáo markdown.

### 4 Specialists

| # | Agent | Trọng tâm | Scope files |
|---|---|---|---|
| 1 | Backend Security | SQLi, auth bypass, secrets, CORS, input validation, file upload validation, error handling | `backend/*.py` |
| 2 | Frontend Security + Perf | XSS, Supabase RLS, secret exposure, bundle size, code-splitting, caching | `frontend/src/**`, `frontend/public/**`, configs |
| 3 | Dependencies & Supply Chain | Known CVEs theo version (từ training data của LLM, không cài `npm audit`/`pip-audit` vì static-only), outdated majors, abandoned libs, license | `package.json`, `package-lock.json`, `backend/requirements*` |
| 4 | Code Quality + Performance | Dead code, code smells, N+1 queries, DB indexes, error handling, logging, file size | Cả `backend/` + `frontend/src/` |

## Data Flow

```
1. Coordinator scan project → scope map
2. 4 agents parallel (Read/Grep/Glob) → findings_BE_sec.json, findings_FE_sec.json,
                                          findings_deps.json, findings_quality.json
3. Per-agent self-verify: với mỗi finding có location, Read lại confirm
4. Adversarial verify: High+ findings → spawn verifier, 2/3 votes giữ
5. Synthesis: dedup, sort severity, viết markdown
6. Coordinator: commit report
```

## Severity Rubric

| Severity | Tiêu chí | Ví dụ |
|---|---|---|
| 🔴 Critical | Khai thác được trong prod, mất data, RCE, auth bypass | SQLi, hardcoded secret, CORS `*` + auth |
| 🟠 High | Nghiêm trọng, cần sửa trong sprint tới | CVE high, input validation, XSS stored |
| 🟡 Medium | Chất lượng/performance đáng kể | N+1 query, file lớn >500 dòng, bundle >1MB |
| 🟢 Low | Cải tiến, technical debt nhỏ | Naming, comment, magic number |

## Verification Pipeline (3 lớp)

1. **Self-verify (per agent)**: Mỗi finding có file:line → Read lại confirm
2. **Adversarial verify (sau khi 4 agents xong)**:
   - Critical: 3/3 independent verifier agents phải confirm "real" mới giữ
   - High: 2/3 independent verifier agents confirm "real" mới giữ
   - Medium/Low: chỉ synthesis review (không cần cross-agent)
3. **Synthesis self-review**:
   - File:line tồn tại
   - Severity nhất quán
   - Không duplicate
   - Fix suggestion có ý nghĩa (no placeholders)

## Output

### File chính (commit)
`docs/audit/2026-06-16-full-audit.md`

Cấu trúc:
- Header: ngày, scope, method, tổng findings count
- 🔴 Critical (count, list findings với Location/Issue/Impact/Fix/Effort)
- 🟠 High
- 🟡 Medium
- 🟢 Low
- Bảng tổng hợp theo file
- Top 5 khuyến nghị ưu tiên
- Phụ lục: deduped findings, files đã quét, công cụ

### File intermediate (không commit)
`.remember/tmp/audit-2026-06-16/findings-{BE-sec,FE-sec,deps,quality}.json`

## Workflow Steps

| # | Bước | Thời gian | Output |
|---|---|---|---|
| 1 | Coordinator scan & scope mapping | ~2 phút | Scope map trong context |
| 2 | 4 specialists parallel | ~10-15 phút | 4 findings JSON |
| 3 | Per-agent self-verify | (trong step 2) | Confidence score |
| 4 | Adversarial verify cho High+ | ~5 phút | Verified findings |
| 5 | Synthesis → markdown → commit | ~3 phút | Report + summary |

**Tổng:** ~20-25 phút, ~150-250K tokens

## Acceptance Criteria

- [ ] 100% findings có file:line đã được verify tồn tại
- [ ] 0 placeholder trong report ("TBD", "TODO", "...")
- [ ] Severity áp dụng đúng rubric
- [ ] Mỗi finding có Impact + Fix suggestion
- [ ] Report đọc độc lập, không cần đọc source
- [ ] Synthesis không tự thêm findings mới (chỉ tổng hợp)

## Trade-offs đã chọn

- **Parallel agents > single agent**: Tốn tokens hơn nhưng chuyên sâu hơn, coverage tốt hơn
- **Report-only > fix ngay**: Mun ca muốn review findings trước, đúng best practice (đỡ sửa nhầm)
- **Standard depth > thorough**: Focused, actionable, không bị overwhelm bởi noise
- **Static only > runtime**: Không cần setup server, nhanh, deterministic

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinate file:line | Self-verify layer (Read lại confirm) |
| False positive nghiêm trọng | Adversarial verify cho High+ |
| Bỏ sót edge case | 4 specialists cover 4 dimensions |
| Token cost cao | Parallel chạy 1 lượt, không loop |
| Synthesis thêm findings ảo | Synthesis rule: chỉ tổng hợp, observations → Low only |

## Open Questions

Không có — Mun ca đã trả lời đủ (Full audit, Report-only, Standard, Static only, focus BE+FE).
