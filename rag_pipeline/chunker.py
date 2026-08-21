"""Chunker por header Markdown - ver docs/INGESTAO.md, secao 3.

TODO (Data Engineer): implementar chunk_by_markdown_header() para
satisfazer os testes de tests/test_ingestao.py.

Contrato: retornar uma lista de {"section": str, "text": str} - um item por
header "## " do documento, com o texto entre um header e o proximo (ou o
fim do documento). Ignorar secoes vazias.
"""

import re

import numpy as np
from langchain_text_splitters import MarkdownHeaderTextSplitter
from sentence_transformers import SentenceTransformer

from rag_pipeline.models import ExtractedDocument

_TOKEN_LIMIT = 200
_OVERLAP_TOKENS = 40
_SIM_THRESHOLD = 0.75
_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_EMBED_MODEL)
    return _model


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _count_tokens(text: str) -> int:
    return len(_get_model().tokenizer.encode(text))


def _embed(sentences: list[str]) -> np.ndarray:
    return _get_model().encode(sentences, normalize_embeddings=True)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # vectors are already normalized


def _compute_overlap(sentences: list[str], overlap_tokens: int, counts: list[int]) -> list[str]:
    overlap = []
    count = 0
    for sent, tokens in zip(reversed(sentences), reversed(counts)):
        if count + tokens <= overlap_tokens:
            overlap.insert(0, sent)
            count += tokens
        else:
            remaining = overlap_tokens - count
            if remaining > 0:
                token_ids = _get_model().tokenizer.encode(sent)
                partial = _get_model().tokenizer.decode(token_ids[-remaining:], skip_special_tokens=True)
                overlap.insert(0, partial.strip())
            break
    return overlap


def _make_chunk(overlap: list[str], window: list[str], section: str, window_index: int) -> dict:
    return {
        "section": section,
        "text": " ".join(overlap + window).strip(),
        "window_index": window_index,
    }


def _sliding_window(
    text: str,
    section: str,
    token_limit: int = _TOKEN_LIMIT,
    overlap_tokens: int = _OVERLAP_TOKENS,
    sim_threshold: float = _SIM_THRESHOLD,
) -> list[dict]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    token_counts = [_count_tokens(s) for s in sentences]

    chunks = []
    window: list[str] = []
    window_tc: list[int] = []
    window_tokens = 0
    overlap: list[str] = []
    window_index = 0
    i = 0

    while i < len(sentences):
        sent = sentences[i]
        sent_tokens = token_counts[i]

        if window_tokens + sent_tokens <= token_limit:
            window.append(sent)
            window_tc.append(sent_tokens)
            window_tokens += sent_tokens
            i += 1
        else:
            next_sent = sentences[i + 1] if i + 1 < len(sentences) else None

            if next_sent is not None:
                embs = _embed([sent, next_sent])
                sim = _cosine_similarity(embs[0], embs[1])

                if sim < sim_threshold:
                    # Semantic break — close before current sentence
                    if window:
                        chunks.append(_make_chunk(overlap, window, section, window_index))
                        window_index += 1
                        overlap = _compute_overlap(window, overlap_tokens, window_tc)
                        window = []
                        window_tc = []
                        window_tokens = 0
                    # Don't advance i — current sentence opens the next window
                else:
                    # Semantically continuous — extend 10% and close
                    window.append(sent)
                    window_tc.append(sent_tokens)
                    i += 1
                    chunks.append(_make_chunk(overlap, window, section, window_index))
                    window_index += 1
                    overlap = _compute_overlap(window, overlap_tokens, window_tc)
                    window = []
                    window_tc = []
                    window_tokens = 0
            else:
                # Last sentence — add and close
                window.append(sent)
                window_tc.append(sent_tokens)
                i += 1
                chunks.append(_make_chunk(overlap, window, section, window_index))
                window_index += 1
                window = []
                window_tc = []
                window_tokens = 0
                overlap = []

    if window:
        chunks.append(_make_chunk(overlap, window, section, window_index))

    return chunks


def chunk_by_markdown_header(document: ExtractedDocument) -> list[dict]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("##", "section")],
        strip_headers=True,
    )
    sections = splitter.split_text(document.raw_text)
    result = []
    for sec in sections:
        if "section" not in sec.metadata or not sec.page_content.strip():
            continue
        result.extend(_sliding_window(sec.page_content.strip(), sec.metadata["section"]))
    return result
