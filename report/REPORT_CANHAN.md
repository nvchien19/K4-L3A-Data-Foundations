# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Nguyễn Văn Chiến
**Mã sinh viên:** 2A202602926
**Nhóm:** L3A-01
**Ngày:** 2026-09-19

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, chiến lược, câu hỏi đánh giá, demo) nộp chung trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

**Chiến lược cá nhân:** `SentenceChunker(max_sentences_per_chunk=2)` — chi tiết trong `REPORT_NHOM.md`.

> Ghi chú: các số liệu phần 4 và 5 được tạo bằng **mock embedder** (mặc định, không cần API key) nên là số thực đo được trên máy, có thể lặp lại.

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Hai vector embeddings gần như cùng hướng, tức hai văn bản "kể về cùng một chủ đề" — embedding mã hoá ý nghĩa, không phải ký tự.

**Ví dụ có độ tương tự CAO:**
- Câu A: "Tuition fee is paid at the beginning of each semester."
- Câu B: "Students must pay their tuition twice a year, at the start of Fall and Spring semesters."
- Tại sao tương đồng: cùng chủ thể (học phí), cùng sự kiện (đóng học phí theo học kỳ) → embedding gần cùng hướng dù từ dùng khác nhau.

**Ví dụ có độ tương tự THẤP:**
- Câu A: "Merit-based scholarships are granted for the entire duration of studies."
- Câu B: "All first-year students are required to reside in the VinUni dormitory."
- Tại sao khác: học bổng so với nội trú — hai chủ đề khác nhau, vector gần như trực giao.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Cosine chỉ xét **góc giữa hai vector**; text embedding thường chuẩn hoá độ dài nên ý nghĩa nằm ở hướng. Euclid bị ảnh hưởng bởi độ dài vector (văn bản dài thường có chuẩn lớn hơn) → không ổn định, trong khi cosine bất biến với độ dài.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Số chunk = ⌈(10 000 − 50) / (500 − 50)⌉ = ⌈9950 / 450⌉ = ⌈22.11⌉ = **23 chunks**.
> Kiểm chứng với `FixedSizeChunker(500, 50)`: step = 450, các vị trí bắt đầu lần lượt 0, 450, …, 9 500 → 23 chunk.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Số chunk tăng: ⌈(10 000 − 100)/(500 − 100)⌉ = ⌈9900/400⌉ = ⌈24.75⌉ = **25 chunks**. Overlap lớn hơn bảo toàn nội dung ở ranh giới cắt (tránh mất nửa ý câu/bảng) nhưng đánh đổi bằng trùng lặp lưu trữ và tăng nhẹ số chunk.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách lập trình các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Dùng regex `(?<=[.!?])\s+` để tách sau đúng dấu chấm than/hỏi/chấm (look-behind) rồi `strip()` từng câu, lọc câu rỗng, và nhóm thành từng nhóm `max_sentences_per_chunk` câu nối bằng dấu cách. Edge case: tài liệu rỗng trả `[]`; `max_sentences_per_chunk` được ép ≥ 1.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Base case: văn bản đã ≤ `chunk_size` (giữ nguyên). Nếu chưa, thử separator đầu tiên theo thứ tự `["\n\n", "\n", ". ", " ", ""]`; nếu separator không tồn tại thì bỏ qua xuống separator tiếp theo; phần nào vẫn > `chunk_size` thì đệ quy với danh sách separator còn lại; cuối cùng **merge các phần** sao cho tổng buffer + separator + phần kế ≤ `chunk_size`. Khi rơi hết separator (chạm `""`), cắt cứng từng khối `chunk_size`.

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> `add_documents` gọi `_make_record` để nhúng `doc.content` bằng `embedding_fn` và lưu dict `{id, content, metadata, embedding}` vào `self._store`; tự gắn `doc_id` vào metadata nếu thiếu. `search` gọi `_search_records`: nhúng query, tính **tích vô hướng (dot product)** giữa vector query và từng embedding, sắp xếp giảm dần và cắt `top_k`, trả về kèm `score`.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> `search_with_filter` **lọc trước, tìm sau**: quét `self._store` giữ lại bản ghi khớp toàn bộ `metadata_filter` rồi mới chạy similarity trên tập thu hẹp (nhờ đó filter thu nhỏ chi phí và ngăn kết quả sai đối tượng). `delete_document` dùng list-comprehension loại mọi bản ghi có `metadata["doc_id"] == doc_id`, trả `True` nếu kích thước giảm.

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> `answer` ba bước RAG: (1) `store.search(question, top_k)`; (2) nếu rỗng trả lời "No relevant information…", ngược lại đánh số context `[1]..[k]` và ghép prompt; (3) prompt yêu cầu LLM **chỉ dùng context**, **trích dẫn số `[n]`** và nói rõ nếu không tìm được, rồi gọi `llm_fn(prompt)`. Thiết kế này ép câu trả lời bám ngữ cảnh (grounded) và truy vết được nguồn.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

### Kết Quả Kiểm Thử (Test Results)

```
> .\.venv\Scripts\python.exe -m pytest tests/ -v
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: ...K4-L3A-Data-Foundations
collected 42 items

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED   [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists  PASSED [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED        [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED   [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED [ 31%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED         [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED [ 36%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED        [ 45%]
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further  PASSED [ 50%]
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED  [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED [ 55%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED [ 62%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED   [ 64%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED  [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED [ 71%]
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED [ 74%]
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED [ 76%]
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED [ 78%]
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED [ 81%]
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED [ 83%]
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED [ 85%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED [ 93%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED [ 97%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED [100%]

============================= 42 passed in 0.12s ==============================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

5 cặp câu lấy ngữ cảnh từ corpus; gọi `compute_similarity(embed(a), embed(b))` với mock embedder.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Tuition fee is paid at the beginning of each semester. | Students must pay their tuition twice a year, at the start of Fall and Spring semesters. | cao | 0.1661 | Không |
| 2 | Exams may take the form of written tests or oral assessments. | Examination format is decided by the instructor and listed in the course syllabus. | cao | −0.1152 | Không |
| 3 | The library has opening hours that change during exam periods. | Library opening hours are subject to change during the summer break. | cao | 0.0435 | Không |
| 4 | Merit-based scholarships are granted for the entire duration of studies. | All first-year students are required to reside in the VinUni dormitory. | thấp | −0.0190 | Có |
| 5 | GPA is calculated from grade points divided by credits attempted. | Students can borrow books from the library for a limited period. | thấp | 0.2679 | Không |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Bất ngờ nhất là cặp 5 — hai câu về chủ đề hoàn toàn khác nhưng mock embedder lại cho điểm cao nhất (0.2679), còn cặp 2 gần nghĩa lại âm (−0.1152). Giải thích: mock embedder chỉ **băm toàn chuỗi thành vector giả ngẫu nhiên**, không học từ vựng/ngữ nghĩa nên điểm số không phản ánh ý nghĩa. Điều này cho thấy embeddings thật phải **học từ ngôn ngữ** (như sentence-transformers/Gemini) mới "hiểu", còn mock chỉ dùng cho kiểm thử kỹ thuật.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy 5 câu hỏi đánh giá của nhóm trên `EmbeddingStore` với chiến lược cá nhân `SentenceChunker(max_sentences_per_chunk=2)` (621 chunks trên 10 tài liệu), mock embedder.

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | What is the GPA scale and how is GPA calculated at VinUni? | academic-regulations: điều kiện full-time student (≥ 80% khối lượng, ~12 tín chỉ/kỳ) | 0.3843 | Không | Không trả lời đúng — context không chứa "Grade System" |
| 2 | A course I want to register for in SIS is already full; there is no waitlist. What should I do? | student-code-of-conduct: kỷ luật — Warning tự hết hiệu lực sau 6 tháng, tạm đình chỉ | 0.3563 | Không | Không trả lời đúng — không nhắc tới waitlist/Registrar |
| 3 | How often does a VinUni student pay tuition, and how much of the listed tuition does the Founding Donor grant cover? | academic-regulations: thời lượng buổi học 50/75 phút | 0.4445 | Có (chunk `financial-regulations-and-tariff` liên quan ở rank 3) | Trả lời được một phần (35%/2030, đóng 2 lần/năm) nhờ chunk rank 3 — nhưng không nằm ở top-1 |
| 4 | What is the maximum level of financial aid a student can receive at VinUni? | financial-regulations: phí quá hạn thiết bị thư viện 10.000 VND/ngày, bị chặn mượn | 0.3437 | Không | Không trả lời đúng — chunk về tiền phạt thư viện, không phải mức hỗ trợ |
| 5 | Do library opening hours change during exam or summer periods? | academic-regulations: các lý do vắng mặt được chấp nhận (hội nghị, thi đấu, đại diện trường) | 0.4091 | Không | Không trả lời đúng — không có giờ mở thư viện |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 1 / 5

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Recursive (300) giữ phân cấp mục và tạo chunk nhỏ hơn, lý tưởng cho văn bản quy định nhiều tầng; từ Hà: giữ **tiêu đề mục trong chunk** khiến việc truy vết "câu trả lời lấy từ đâu" rõ ràng hơn hẳn. Bài học chung: thứ hạng retrieval hiện tại còn phụ thuộc rất nhiều vào backend nhúng (mock ≈ nhiễu), nên so sánh chiến lược chỉ có nghĩa khi cả nhóm chạy cùng một embedder ngữ nghĩa.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 9 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 4 / 10 *(1/5 câu có chunk liên quan trong top-3 — mock embedder)* |
| **Tổng phần cá nhân** | **53 / 60** |