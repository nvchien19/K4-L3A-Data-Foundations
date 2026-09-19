# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** L3A-01 (đặt tên theo nhóm)
**Thành viên:**
1. Nguyễn Hồ Nam — 2A202602788 — Chiến lược: RecursiveChunker
2. Nguyễn Văn Chiến — 2A202602926 — Chiến lược: SentenceChunker
3. Vũ Văn Hà — 2A202602589 — Chiến lược: Custom section-based chunker
4. Nguyễn Cảnh Duy — 2A202602815 — Chiến lược: FixedSizeChunker (tinh chỉnh)

**Ngày:** 2026-09-19

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

> **Ghi chú hợp nhất:** toàn bộ số liệu run dưới đây được tạo bằng **mock embedder (mặc định của lab, `EMBEDDING_PROVIDER=mock`)** — deterministic, không cần API key, đúng như lệnh chạy trong `README.md`. Mock embedder băm (hash) toàn chuỗi nên **không mang ý nghĩa ngữ nghĩa**; điều này được phân tích rõ ở Mục 3 và là bài học chính của nhóm. Kết quả có thể lặp lại được bằng script trong repo.

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Dịch vụ & quy định đại học — **VinUniversity** (mảng học vụ cho sinh viên: đăng ký học phần, thi & điểm, học phí – học bổng – tài trợ tài chính, thư viện, ký túc xá, tư vấn học thuật, chuẩn mực sinh viên).

**Tại sao nhóm chọn chủ đề này?**
> Nhóm cần chủ đề quy định/dịch vụ đại học theo `K4_VARIANT.md`, và VinUni là trường có cổng chính sách công khai (`policy.vinuni.edu.vn`) lưu sẵn phiên bản & ngày hiệu lực của từng văn bản — rất thuận lợi để gán metadata `document_version`. Bộ tài liệu cũng có nhiều mảng khác nhau (học phí, thư viện, ký túc xá…) nên dễ thiết kế 5 câu hỏi đánh giá đa dạng và dễ minh hoạ lọc metadata theo `audience`/`department`/`category`.

### Danh sách tài liệu (Data Inventory)

Nguồn chính thức công khai, lấy ngày 2026-09-19 bằng script `scripts/fetch_public_pages.py`, đã làm sạch nội dung (bỏ menu/footer, giữ nguyên điều khoản, con số, mốc thời gian).

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự (body) | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Academic Regulations for Full-Time Undergraduate Programs | https://policy.vinuni.edu.vn/all-policies/academic-regulations-for-full-time-undergraduate-programs/ | 2026-09-19 / VU_HT03.EN | 67 970 | audience=student, department=registrar, category=academic, language=en |
| 2 | Class Schedule & Course Registration | https://registrar.vinuni.edu.vn/academics/class-schedule-course-registration/ | 2026-09-19 / not-stated | 3 485 | audience=student, department=registrar, category=registration |
| 3 | Exams & Grades | https://registrar.vinuni.edu.vn/academics/exams-grades/ | 2026-09-19 / not-stated | 1 562 | audience=student, department=registrar, category=grading |
| 4 | Financial Regulations and Tariff (for student) | https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff-for-student-2/ | 2026-09-19 / VUNI_TS03_Student | 36 008 | audience=student, department=finance, category=tuition |
| 5 | Library Access & Services Policy | https://policy.vinuni.edu.vn/all-policies/library-policies-for-users/ | 2026-09-19 / POL-LLR-001-V4.0 | 7 261 | audience=all, department=library, category=library |
| 6 | Residential Life Guideline | https://policy.vinuni.edu.vn/all-policies/residential-life-guideline/ | 2026-09-19 / GDL-SAM-008-V5.0 | 15 392 | audience=student, department=student-affairs, category=residential |
| 7 | Guidelines on Student Academic Accommodation | https://policy.vinuni.edu.vn/all-policies/guidelines-on-student-academic-accomodation/ | 2026-09-19 / GDL-SAM-010-V1.0 | 11 183 | audience=student, department=student-affairs, category=academic-support |
| 8 | Student Advising Framework | https://policy.vinuni.edu.vn/all-policies/student-advising-framework/ | 2026-09-19 / FW-SAM-001-V2.0 | 17 153 | audience=student, department=student-affairs, category=advising |
| 9 | Student Code of Conduct | https://policy.vinuni.edu.vn/all-policies/student-affairs-regulations-code-of-conduct/ | 2026-09-19 / VU_CTSV02.EN | 16 925 | audience=all, department=student-affairs, category=conduct |
| 10 | Tuition Fee and Financial Aids (AY 2024-2025) | https://admissions.vinuni.edu.vn/tuition-fee-and-financial-support/ | 2026-09-19 / 2024-2025 | 5 271 | audience=student, department=admissions, category=tuition |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.
- [x] Khai báo đủ trong `data/vinuni-services/sources.csv`, khớp 1-1 với file.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| doc_id | string | `course-registration-hub` | Định danh ổn định cho `delete_document()` và truy vết chunk |
| title | string | `Class Schedule & Course Registration` | Nhãn hiển thị cho kết quả search |
| source_url | string | `https://registrar.vinuni.edu.vn/...` | Truy vết nguồn của câu trả lời (grounding) |
| retrieved_at | date | `2026-09-19` | Kiểm tra độ mới của dữ liệu |
| document_version | string | `VU_HT03.EN`, `not-stated` | Xác định phiên bản hiệu lực của quy định |
| audience | string | `student` / `all` | **Lọc theo đối tượng**, yêu cầu bắt buộc của K4_L3A |
| department | string | `registrar`, `finance`, `library` | Lọc theo đơn vị ban hành chính sách |
| category | string | `tuition`, `grading`, `registration`, `library` | Nhóm câu hỏi đánh giá theo mảng dịch vụ |
| language | string | `en` | Đảm bảo dùng đúng ngôn ngữ khi trả lời |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> 4 thành viên thử **4 chiến lược khác nhau** trên cùng bộ tài liệu; kết quả tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare(chunk_size=200)` trên 3 tài liệu đại diện:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| Academic Regulations (67 970 ký tự) | FixedSizeChunker (`fixed_size`) | 453 | 199.9 | Không tốt — cắt ngang câu |
| | SentenceChunker (`by_sentences`) | 158 | 429.2 | Giữ trọn câu nhưng chunk dài, gộp nhiều ý |
| | RecursiveChunker (`recursive`) | 457 | 147.4 | Tốt hơn — tôn trọng ngắt dòng/mục |
| Course Registration (3 485 ký tự) | FixedSizeChunker (`fixed_size`) | 23 | 199.3 | Cắt ngang danh sách bước đăng ký |
| | SentenceChunker (`by_sentences`) | 15 | 231.1 | Giữ trọn câu, ít chunk |
| | RecursiveChunker (`recursive`) | 21 | 165.0 | Tách theo mục tốt |
| Exams & Grades (1 562 ký tự) | FixedSizeChunker (`fixed_size`) | 11 | 187.5 | Tài liệu ngắn → ít bị cắt khúc |
| | SentenceChunker (`by_sentences`) | 4 | 389.5 | Chunk rất dài (cả mục "Grade System") |
| | RecursiveChunker (`recursive`) | 10 | 155.2 | Phân cấp rõ hơn |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (nhóm có 4 người nên có 4 khối).

**Thành viên 1 — Nguyễn Hồ Nam (2A202602788)**
- **Loại chiến lược:** RecursiveChunker, `chunk_size=300`
- **Mô tả & lý do chọn cho chủ đề này:** Corpus là văn bản quy định có phân cấp mục rõ (`.` phiên bản, danh sách, bảng). Recursive cố tách theo `\n\n` → `\n` → `. ` → `" "` nên giữ tính phân cấp tốt hơn FixedSize; cỡ 300 ký tự đủ ngắn để search chính xác mà vẫn giữ được trọn một ý/một điều khoản.
- **Code snippet:**
```python
from src.chunking import RecursiveChunker
chunker = RecursiveChunker(chunk_size=300)
chunks = chunker.chunk(doc.content)
```

**Thành viên 2 — Nguyễn Văn Chiến (2A202602926)**
- **Loại chiến lược:** SentenceChunker, `max_sentences_per_chunk=2`
- **Mô tả & lý do chọn:** Văn bản quy định viết câu dài và mỗi câu thường mang một điều khoản/điều kiện độc lập. Gom tối đa 2 câu giúp chunk đủ ngắn để truy xuất và không nuốt mất nội dung giữa câu (khác với FixedSize hay chunk 3 câu của baseline).
- **Code snippet:**
```python
from src.chunking import SentenceChunker
chunker = SentenceChunker(max_sentences_per_chunk=2)
chunks = chunker.chunk(doc.content)
```

**Thành viên 3 — Vũ Văn Hà (2A202602589)**
- **Loại chiến lược:** Custom — chia theo **mục/tiêu đề (section-based chunker)** ✅ *đáp ứng yêu cầu K4_VARIANT (ít nhất 1 thành viên thử chunking theo heading/section)*
- **Mô tả & lý do chọn:** Văn bản của trường vốn có tiêu đề mục (ví dụ "I. PURPOSES", "1.1. Opening hours", "GPA Calculation") nhưng khi clean, crawler **mất dấu `#` Markdown**. Vì vậy custom chunker nhận diện tiêu đề mục theo hình thức: số La Mã / số thứ tự (`1.1.`), dòng in hoa ngắn ("IN-SEMESTER"), hoặc dòng tiêu đề Title-case ngắn; giữ tiêu đề kèm thân mục, gộp mục quá nhỏ vào mục trước, và chunk nào vẫn quá dài thì **dự phòng bằng RecursiveChunker(600)**.
- **Code snippet:**
```python
class CustomSectionChunker:
    """Chia theo mục (section) của văn bản quy định."""
    _HEADER = re.compile(r"^([IVXLA]+\.\s|\d+(\.\d+)*\.\s|(?=.{2,60}$)[A-Z])")

    def __init__(self, max_size=600, min_merge=180):
        self.max_size = max_size
        self.min_merge = min_merge
        self._fallback = RecursiveChunker(chunk_size=max_size)

    def chunk(self, text):
        sections = []                     # (title, body_lines)
        cur_title, cur = None, []
        for line in text.splitlines():
            if line.strip() and self._is_header(line.strip()) and cur:
                sections.append((cur_title, "\n".join(cur)))
                cur_title, cur = line.strip(), []
            else:
                cur_title = cur_title or "(opening)"
                cur.append(line.rstrip())
        if cur:
            sections.append((cur_title, "\n".join(cur)))

        merged, chunks = [], []
        for title, body in sections:
            if len(body) < self.min_merge and merged:
                merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + body)
            else:
                merged.append((title, body))
        for title, body in merged:
            usable = f"{title}\n{body}" if title != "(opening)" else body
            if len(usable) <= self.max_size:
                chunks.append(usable)
            else:
                chunks += [p for p in self._fallback.chunk(usable) if p]
        return chunks

    @staticmethod
    def _is_header(line):
        if not line or len(line) > 80:
            return False
        if re.match(r"^[IVXLA]+\.\s", line) or re.match(r"^\d+(\.\d+)*\.\s", line):
            return True
        if line.isupper() and len(line.split()) <= 8:
            return True
        if re.match(r"^[A-Z][A-Za-z ]{2,60}$", line) and len(line.split()) <= 7:
            return True
        return False
```

**Thành viên 4 — Nguyễn Cảnh Duy (2A202602815)**
- **Loại chiến lược:** FixedSizeChunker tinh chỉnh, `chunk_size=400`, `overlap=80`
- **Mô tả & lý do chọn:** FixedSize đơn giản, ổn định và nhanh nhất; chọn chunk lớn hơn (400) vì quy định viết dày câu có liên kết chặt; overlap 80 (20%) nhằm giảm rủi ro mất nội dung ở ranh giới cắt — phù hợp để so sánh "có overlap" với các chiến lược khác.
- **Code snippet:**
```python
from src.chunking import FixedSizeChunker
chunker = FixedSizeChunker(chunk_size=400, overlap=80)
chunks = chunker.chunk(doc.content)
```

### So Sánh Giữa Các Thành Viên

Số chunk toàn corpus (10 tài liệu):

| Thành viên | Chiến lược (Strategy) | Số chunk/corpus | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|----------|
| Nguyễn Hồ Nam | Recursive 300 | 795 | 0 | Giữ phân cấp mục; chunk nhỏ (~150-300) → tăng cơ hội trúng ý | Nhiều chunk; mock embedder không nhận nghĩa nên không so được |
| Nguyễn Văn Chiến | Sentence 2 câu | 621 | 1 | Mỗi chunk trọn ý (điều khoản); trúng 1/5 câu (Q3) | Chunk dài hơn khi sai dấu câu; phụ thuộc chất lượng tách câu |
| Vũ Văn Hà | Custom section 600 | 431 | 0 | Ít chunk nhất, giữ tiêu đề mục → context rõ ràng | Nhận diện tiêu đề theo heuristic có thể lệch; phụ thuộc format văn bản |
| Nguyễn Cảnh Duy | Fixed 400/80 | 572 | 0 | Đơn giản, nhanh, dễ tái lập | Cắt ngang câu/mục vẫn xảy ra dù có overlap |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> Về **thiết kế**, chiến lược custom section của Hà và Recursive của Nam phù hợp nhất với văn bản quy định (phân cấp mục, điều khoản trọn ý). Tuy nhiên khi chạy với **mock embedder**, điểm truy xuất gần như ngẫu nhiên (chỉ Chiến trúng 1/5 nhờ chunk ngắn trùng từ khoá) nên **chưa thể kết luận chiến lược nào "tốt nhất" chỉ từ số liệu/10**; nhóm kết luận rằng tập chunk nào gọn và có ngữ cảnh mục sẽ có lợi thế khi nâng cấp lên embedder ngữ nghĩa thật.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> Đúng 5 câu hỏi, đa dạng, kiểm chứng được; Q5 cần lọc `category=library`, Q2 minh hoạ lọc `audience=student`. Đây là bộ câu hỏi chung cho mọi thành viên.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | What is the GPA scale and how is GPA calculated at VinUni? | VinUni dùng thang điểm chữ trên thang 4.0: A=4.0 … F=0.0; ký hiệu đặc biệt W (withdrawn), I (incomplete), T (transfer, không tính GPA), P/F. GPA = tổng (số tín chỉ × hệ điểm) / tổng tín chỉ đã đăng ký, **loại trừ P/F và Transfer**. | `exams-and-grades.md` — mục "Grade System" & "GPA Calculation" |
| 2 | A course I want to register for in SIS is already full; there is no waitlist. What should I do? | SIS hiện **không có chức năng waitlist**; một số khóa giới hạn chỗ ngồi. Sinh viên nên kiểm tra SIS thường xuyên để bắt chỗ trống; trong vài ngày đầu kỳ được Add/Drop; nếu đủ prerequisite nhưng bị chặn thì liên hệ **Registrar’s Office**. | `course-registration-hub.md` — mục "Course Capacity & Waitlist" |
| 3 | How often does a VinUni student pay tuition, and how much of the listed tuition does the Founding Donor grant cover? | Học phí đóng **2 lần/năm** vào đầu mỗi học kỳ chính (Fall & Spring). **Educational Development Grant** từ Nhà sáng lập giảm **35%** học phí niêm yết cho sinh viên nhập học **đến năm 2030**, áp dụng trọn chương trình; tích lũy cùng học bổng khác nhưng **không quá 100%** học phí niêm yết. | `financial-regulations-and-tariff.md` — mục scholarship/financial aid (35%, sinh viên đến 2030) và `tuition-fee-financial-aids.md` — mục "I. TUITION FEE" |
| 4 | What is the maximum level of financial aid a student can receive at VinUni? | Có thể nộp nhiều loại học bổng/tài trợ nhưng **tổng không vượt quá 100% học phí**. Học bổng toàn phần (Full Ride) = 100% học phí **+ 34.965.000 VND/năm** sinh hoạt. Mức financial aid xét theo hoàn cảnh gia đình từ 40% đến **100%**. | `tuition-fee-financial-aids.md` — mục "II. SCHOLARSHIPS AND FINANCIAL AIDS" |
| 5 | Do library opening hours change during exam or summer periods? | Có — giờ mở cửa **thay đổi trong kỳ thi, ngày lễ và hè**, niêm yết tại lối vào chính và website. Cửa chính: trong kỳ **8:00–21:00** (T2–CN), kỳ thi/hè **9:00–17:00**; không gian học **24/7** mở 24/7; lối vào tầng 2: 8:30–17:30 (thứ bảy làm việc; CN & ngày lễ đóng). | `library-access-services.md` — mục "1.1. Opening hours" |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0). Số liệu = mock embedder, xem ghi chú đầu báo cáo.

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | GPA scale / GPA calculation | — (không chiến lược nào trúng) | Không | Chunk top-1 của cả nhóm rơi vào tài liệu khác (financial / library / conduct) |
| 2 | Course full, no waitlist | — | Không | Top-1 thường là `student-code-of-conduct` — bị **loại khi lọc `audience=student`** |
| 3 | Tuition frequency & 35% grant | Nguyễn Văn Chiến (SentenceChunker) | Có (rank 3) | Chiến trúng `financial-regulations-and-tariff` ở vị trí 3 → **1/2 điểm** |
| 4 | Max level of financial aid | — | Không | Không chiến lược nào trúng tài liệu `tuition-fee-financial-aids` |
| 5 | Library opening hours | — | Không | Chỉ khi lọc `category=library` mới thu hẹp đúng tài liệu (xem bên dưới) |

**Điểm nhóm (mock): 1/10.** Có 0/5 câu đạt điểm 2; 1 câu (Q3) đạt 1 điểm do chunk liên quan ở rank 3 nhưng không ở top-1.

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Có minh hoạ được, đặc biệt với: **(a) Q2** — lọc `audience=student` loại `student-code-of-conduct` (audience=all) khỏi top-5, tập ứng viên sạch hơn; **(b) Q5** — lọc `category=library` thu hẹp top-5 hoàn toàn về tài liệu thư viện. Tuy nhiên **thứ tự điểm trong nhóm còn bị nhiễu do mock embedder** (điểm score không phản ánh mức liên quan), nên filter mới giúp thu hẹp tập, chưa giúp sắp hạng đúng — thứ tự đó cần embedder ngữ nghĩa.

### Phân tích lỗi (failure case) — Bài tập 3.5

- **Câu hỏi lỗi:** Q1 (GPA) — top-1 của Duy là "Financial Regulations" và Hà là "Library functional rooms"; không ai truy xuất được mục "Grade System" của `exams-and-grades.md`.
- **Tại sao:** mock embedder băm toàn chuỗi → vector gần như ngẫu nhiên (các câu về thư viện có thể đạt score cao hơn câu về GPA); ngoài ra bảng thang điểm trong `exams-and-grades.md` bị chunk thành khối ký tự, không có metadata `department=registrar` để hỗ trợ lọc.
- **Đề xuất cải thiện:** (1) chạy với embedder ngữ nghĩa thật (`EMBEDDING_PROVIDER=local` hoặc `gemini` — Xem README); (2) giữ tiêu đề mục trong chunk (chiến lược của Hà) giúp truy vết "Grade System"; (3) bổ sung filter `category=grading` cho câu hỏi điểm.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
1. **Chunking chi phối "ứng viên" của retrieval, nhưng embedder quyết định chất lượng**: cùng corpus, 4 chiến lược cho 431–795 chunk; tập ứng viên khác nhau ngay từ đầu.
2. **Metadata filter hoạt động như kỹ thuật thu hẹp (pre-filtering)**: loại đúng tài liệu sai đối tượng (`audience=student`) hoặc đúng mảng (`category=library`) ngay cả khi embedder còn yếu.
3. **Dữ liệu thật không sạch như lý thuyết**: crawler làm mất dấu `#` Markdown của tiêu đề mục → buộc custom chunker nhận diện tiêu đề bằng hình thức (regex) và chấp nhận tỉ lệ sai nhất định.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng tài liệu nhưng chiến lược khác nhau dẫn tới **tập chunk và độ phân giải khác nhau**: Sentence (2 câu) tạo chunk trọn điều khoản nhưng dài; Recursive 300 tạo chunk nhỏ, nhiều và ngắt theo mục; Custom section giữ nguyên mục nhưng ít chunk; Fixed tinh chỉnh nhanh nhưng vẫn cắt ngang câu. Chính vì vậy, trước khi so sánh "chiến lược nào tốt" cần cố định embedder — nếu cả nhóm chỉ dùng mock embedder thì khác biệt thứ hạng gần như nhiễu.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Nhóm sẽ (1) cài `requirements-local.txt` và chạy thống nhất bằng `LocalEmbedder`/`GeminiEmbedder` thay vì mock để retrieval có nghĩa; (2) viết lại custom chunker để nhận diện nhiều dạng tiêu đề hơn (danh sách `1.1.1`, heading in hoa viết tắt) và gán `category` chuẩn hoá cho từng tài liệu ngay tại bước crawl; (3) tách bảng điểm ("Grade System") thành tài liệu riêng hoặc chunk riêng để truy xuất ổn định hơn.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 9 / 10 |
| Thiết kế chiến lược (Strategy Design) | 12 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 1 / 10 *(mock embedder — cải thiện khi dùng embedder ngữ nghĩa)* |
| Thuyết trình (Demo) | 4 / 5 |
| **Tổng phần nhóm** | **26 / 40** |