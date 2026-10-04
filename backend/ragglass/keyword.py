"""A replaceable, local BM25 retriever over the selected documents' stored chunks."""

import math
import re
import unicodedata
from collections import Counter

K1 = 1.2
B = 0.75
TOKENIZER = "nfkc-latin-identifiers-han-1-2grams-v1"
STOP_WORDS = frozenset(
    "a an and are as at be by do does for from how in is it of on or that the this to was "
    "what when where which who with".split()
)
TERMS = re.compile(r"[a-z0-9]+(?:[-_./][a-z0-9]+)*|[\u3400-\u4dbf\u4e00-\u9fff]+")


def tokenize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(str.maketrans("‐‑–−", "----"))
    tokens = []
    for match in TERMS.finditer(text):
        term = match.group()
        if "\u3400" <= term[0] <= "\u9fff":
            tokens.extend(term)
            tokens.extend(term[i : i + 2] for i in range(len(term) - 1))
        else:
            if term not in STOP_WORDS:
                tokens.append(term)
            # Keep the complete identifier and its components; never split X17 into X / 17.
            parts = re.split(r"[-_./]", term)
            if len(parts) > 1:
                tokens.extend(part for part in parts if part not in STOP_WORDS)
    return tokens


class KeywordRetriever:
    """No cached index: reindex/delete/restart immediately follow SQLite source of truth.

    Corpus statistics are scoped to the selected documents. This scans their chunks on
    each query and is intended for a local workbench, not a large-corpus search server.
    """

    @staticmethod
    def snapshot():
        return {
            "algorithm": "bm25-positive-idf-v1",
            "tokenizer": TOKENIZER,
            "k1": K1,
            "b": B,
            "corpus": "selected-document-chunks",
        }

    def search(self, question, chunks, limit):
        terms = sorted(set(tokenize(question)))
        counts = [Counter(tokenize(chunk["text"])) for chunk in chunks]
        lengths = [sum(count.values()) for count in counts]
        total = len(chunks)
        average = sum(lengths) / total if total else 0
        df = Counter(term for count in counts for term in terms if term in count)
        results = []
        if terms and average:
            idf = {term: math.log1p((total - df[term] + 0.5) / (df[term] + 0.5)) for term in df}
            for chunk, count, length in zip(chunks, counts, lengths, strict=True):
                matched = [term for term in terms if term in count]
                score = sum(
                    idf[term]
                    * count[term]
                    * (K1 + 1)
                    / (count[term] + K1 * (1 - B + B * length / average))
                    for term in matched
                )
                if score > 0:
                    results.append({**chunk, "score": score, "matched_terms": matched})
        results.sort(key=lambda item: (-item["score"], item["id"]))
        return (
            [{**item, "rank": rank} for rank, item in enumerate(results[:limit], 1)],
            {"query_terms": terms, "corpus_chunks": total, "average_chunk_terms": average},
        )
