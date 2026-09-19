from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.agent import KnowledgeBaseAgent
from src.chunking import FixedSizeChunker, RecursiveChunker, SentenceChunker
from src.embeddings import GEMINI_EMBEDDING_MODEL, GeminiEmbedder, _mock_embed
from src.models import Document
from src.store import EmbeddingStore

load_dotenv(override=False)

GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
FREE_TIER_RATE = 100
REQUEST_INTERVAL = 60.0 / (FREE_TIER_RATE * 0.85)

STRATEGIES = {
    "Recursive — chunk_size=300": lambda: RecursiveChunker(chunk_size=300),
    "Sentence — 2 câu/chunk": lambda: SentenceChunker(max_sentences_per_chunk=2),
    "FixedSize — 400, overlap=80": lambda: FixedSizeChunker(chunk_size=400, overlap=80),
}

ESSENTIAL_DOCS = [
    "exams-and-grades.md",
    "course-registration-hub.md",
    "financial-regulations-and-tariff.md",
    "tuition-fee-financial-aids.md",
    "library-access-services.md",
]

EXAMPLE_QUESTIONS = [
    "What is the GPA scale and how is GPA calculated at VinUni?",
    "A course I want to register for in SIS is already full; there is no waitlist. What should I do?",
    "How often does a VinUni student pay tuition, and how much of the listed tuition does the Founding Donor grant cover?",
    "What is the maximum level of financial aid a student can receive at VinUni?",
    "Do library opening hours change during exam or summer periods?",
]


def parse_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fm[key.strip()] = value.strip().strip('"').strip("'")
        body = text[m.end():]
    else:
        body = text
    return fm, body


class CachedEmbedder:
    """Embedding wrapper that persists vectors to disk and paces API calls
    to stay inside the Gemini free-tier quota (100 requests/minute).

    Quota errors are retried with backoff (honouring the server's retryDelay).
    Safe to interrupt: every computed vector is saved incrementally, so the
    next run resumes without re-calling the API.
    """

    def __init__(self, inner, cache_path: Path, interval: float = REQUEST_INTERVAL) -> None:
        self._inner = inner
        self._cache_path = Path(cache_path)
        self._interval = interval
        self._last_call = 0.0
        self._cache: dict[str, list[float]] = {}
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self._cache = {}

    def _save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._cache), encoding="utf-8")
        tmp.replace(self._cache_path)

    def __call__(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self._cache:
            return self._cache[key]
        vector = self._call_remote(text)
        self._cache[key] = vector
        self._save()
        return vector

    def _call_remote(self, text: str) -> list[float]:
        delay = 4.0
        for attempt in range(8):
            wait = max(0.0, self._interval - (time.monotonic() - self._last_call))
            if wait:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                return self._inner(text)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                retry_after = re.search(r"retryDelay[^0-9]*([0-9]+(?:\.[0-9]+)?)", message)
                is_quota = ("RESOURCE_EXHAUSTED" in message or "quota" in message.lower())
                if not is_quota:
                    raise
                sleep_time = float(retry_after.group(1)) if retry_after else delay
                time.sleep(min(sleep_time, 60.0))
                delay = min(delay * 2, 60.0)
        raise RuntimeError(
            "Gemini embedding quota vẫn bị vượt sau nhiều lần thử. "
            "Phần nhúng đã lưu vào .cache/ nên lần chạy sau sẽ tiếp tục từ đó."
        )


def build_embedder(provider: str):
    name, embedder = "mock embeddings fallback", _mock_embed
    if provider == "Gemini":
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            st.warning("Không tìm thấy GEMINI_API_KEY/GOOGLE_API_KEY → rơi xuống mock embedder.")
        else:
            try:
                embedder = GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL))
                name = getattr(embedder, "_backend_name", "gemini")
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Không khởi tạo được Gemini embedder ({exc}) → rơi xuống mock embedder.")
    return name, embedder


@st.cache_resource(show_spinner="Đang nhúng dữ liệu (lần đầu chậm, sẽ lưu cache)…")
def build_store(corpus_dir: str, strategy_key: str, provider: str, doc_files: tuple[str, ...]) -> tuple[EmbeddingStore, str, int, int]:
    chunker = STRATEGIES[strategy_key]()
    name, embedder = build_embedder(provider)
    if provider == "Gemini":
        slug = re.sub(r"[^\w.-]+", "_", f"{provider}_{strategy_key}_{'_'.join(doc_files)}")[:120]
        embedder = CachedEmbedder(embedder, Path(".cache/embeddings") / f"{slug}.json")

    store = EmbeddingStore(collection_name="chat_demo", embedding_fn=embedder)
    doc_count, chunk_count = 0, 0
    for path in sorted(Path(corpus_dir).glob("*.md")):
        if path.name not in doc_files:
            continue
        fm, body = parse_md(path)
        meta = {k: v for k, v in fm.items() if k in
                ("doc_id", "title", "source_url", "retrieved_at", "document_version",
                 "audience", "department", "category", "language")}
        for i, content in enumerate(chunker.chunk(body.strip())):
            store.add_documents([Document(id=f"{fm.get('doc_id', path.stem)}#{i}",
                                          content=content, metadata={**meta, "chunk_index": i})])
            chunk_count += 1
        doc_count += 1
    return store, name, doc_count, chunk_count


def make_llm() -> tuple:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if key:
        try:
            from google import genai

            client = genai.Client(api_key=key)

            def gemini_llm(prompt: str) -> str:
                response = client.models.generate_content(
                    model=GEMINI_CHAT_MODEL,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(temperature=0.2),
                )
                return response.text or ""

            return gemini_llm, f"Gemini ({GEMINI_CHAT_MODEL})"
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Không gọi được Gemini LLM ({exc}); có thể kiểm tra GEMINI_CHAT_MODEL.")

    def mock_llm(prompt: str) -> str:
        chunks = re.findall(r"^\[(\d+)\] (.+)$", prompt, re.MULTILINE)
        preview = "\n".join(f"• [{n}] {text[:120]}…" for n, text in chunks[:3])
        return ("‹DEMO MOCK› Chưa cấu hình GEMINI_API_KEY nên LLM thật không sinh được văn bản. "
                "Đây là ngữ cảnh tốt nhất hệ thống truy xuất được:\n" + (preview or "…(trống)"))

    return mock_llm, "Mock LLM (không có key Gemini)"


def render_results(results: list[dict]) -> None:
    if not results:
        return
    with st.expander(f"Ngữ cảnh truy xuất (top-{len(results)})"):
        for i, r in enumerate(results, 1):
            doc_id = r["metadata"].get("doc_id", "?")
            source = r["metadata"].get("source_url", "")
            audience = r["metadata"].get("audience", "?")
            category = r["metadata"].get("category", "?")
            st.markdown(
                f"**{i}.** `{doc_id}` · score **{r['score']:.4f}** · audience={audience} · category={category}"
            )
            if source:
                st.caption(f"Nguồn: {source}")
            st.write(r["content"][:500])


def main() -> None:
    st.set_page_config(page_title="RAG Chat — Lab 7", page_icon="💬", layout="wide")
    st.title("💬 RAG Chat — Nền Tảng Dữ Liệu & Vector Store")
    st.caption("Hỏi về dịch vụ/quy định trường đại học. Trả lời chỉ dựa trên kho tài liệu đã nhúng (retrieval-augmented generation).")

    corpus_dir = st.sidebar.text_input("Thư mục tài liệu", value="data/vinuni-services")
    strategy_key = st.sidebar.selectbox("Chiến lược chunking", list(STRATEGIES))
    provider = st.sidebar.selectbox("Backend embedding", ["Mock", "Gemini"])
    top_k = st.sidebar.slider("top_k (số đoạn ngữ cảnh)", 1, 8, 3)
    use_filter = st.sidebar.checkbox("Lọc metadata: audience = student", value=False)

    available = sorted(p.name for p in Path(corpus_dir).glob("*.md"))
    default_files = [f for f in ESSENTIAL_DOCS if f in available]
    with st.sidebar.expander("Tài liệu dùng (mặc định 5 tài liệu câu hỏi mẫu)"):
        doc_files = tuple(st.multiselect("Chọn file", available, default=default_files))
    if not doc_files:
        st.sidebar.error("Chọn ít nhất một tài liệu.")
        st.stop()

    if st.sidebar.button("Load lại dữ liệu"):
        build_store.clear()

    try:
        store, embedder_name, doc_count, chunk_count = build_store(
            corpus_dir, strategy_key, provider, doc_files
        )
    except Exception as exc:  # noqa: BLE001
        st.sidebar.error(str(exc))
        st.stop()

    st.sidebar.caption(
        f"NB: **{doc_count}** tài liệu · **{chunk_count}** chunks · embedder: **{embedder_name}**"
    )

    llm_fn, llm_name = make_llm()
    st.sidebar.caption(f"LLM: **{llm_name}**")
    if embedder_name.startswith("mock"):
        st.sidebar.warning("Đang dùng mock embedder → truy xuất không phản ánh đúng ngữ nghĩa.")
    else:
        st.sidebar.caption("Embedding được cache tại `.cache/embeddings/` để tiết kiệm quota Gemini.")

    agent = KnowledgeBaseAgent(store=store, llm_fn=llm_fn)

    st.sidebar.divider()
    st.sidebar.markdown("### Câu hỏi mẫu")
    for q in EXAMPLE_QUESTIONS:
        if st.sidebar.button(q[:56], key=q):
            st.session_state["pending"] = q

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant":
                render_results(msg.get("results", []))

    if prompt := st.chat_input("Nhập câu hỏi…"):
        st.session_state["pending"] = prompt

    if pending := st.session_state.pop("pending", None):
        st.session_state["messages"].append({"role": "user", "content": pending})

        with st.chat_message("assistant"):
            if not use_filter:
                results = store.search(pending, top_k=top_k)
            else:
                results = store.search_with_filter(pending, top_k=top_k, metadata_filter={"audience": "student"})

            if not results:
                answer = "No relevant information found in the knowledge base."
                msg = {"role": "assistant", "content": answer, "results": []}
            else:
                answer = agent.answer(pending, top_k=top_k)
                msg = {"role": "assistant", "content": answer, "results": results}
            st.session_state["messages"].append(msg)
            st.write(answer)
            render_results(results)
        st.rerun()


if __name__ == "__main__":
    main()