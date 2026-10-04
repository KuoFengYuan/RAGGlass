# Retrieval modes and controlled evaluation

**English** | [繁體中文](RETRIEVAL.zh-TW.md)

RAGGlass can compare vector, keyword and hybrid retrieval without changing the PDF, parser, embedding model or answer model. Open **Retrieval options → Retrieval mode**. The existing **Vector** default and old API requests remain compatible; existing indexed documents need no migration for keyword/hybrid search.

## Controls and scores

| Mode | How it retrieves | Evidence score |
| --- | --- | --- |
| Vector (`dense`) | E5 query embedding → Qdrant cosine search in selected documents. | Cosine similarity; not answer confidence. |
| Keyword (`keyword`) | Local BM25 over the selected documents' SQLite chunks. Query embedding/vector search are skipped. | Positive BM25 relevance; not comparable to cosine. |
| Hybrid (`hybrid`) | Retrieve candidates from each method, deduplicate chunk IDs and merge ranks with equal-weight RRF. | `sum(1 / (60 + branch_rank))`; not a probability. |

**Top K** is the final evidence limit (default 5, range 1–12). **Minimum score** (default 0.70) filters only the cosine branch, including in hybrid mode. It never filters BM25 or RRF and is disabled for keyword mode. **Candidates per method** appears for hybrid mode (default 20, up to 100, at least Top K). A candidate outside final evidence or omitted by the [context budget](WORKFLOWS.md#context-and-tokens) cannot be cited.

Evidence cards label cosine, BM25 or RRF explicitly and show each available branch's original rank/score. Open **Retrieval rankings** to inspect all candidates, source pages, keyword matches and which IDs entered final evidence. A missing branch rank means that chunk was not in that branch's retained candidates, not a zero relevance score. Stopped hybrid retrieval marks its retained ranking as partial. History restores the mode/depth; JSON and Markdown exports retain diagnostic scores. History lists exclude the larger candidate trace; detail/export endpoints retain it.

No candidates produces a saved refusal before inference. A hybrid vector failure fails visibly rather than silently changing the method. Keyword retrieval still requires a ready document in the current embedding space, preserving the indexed-document eligibility contract.

## Implementation and boundaries

`keyword.py` is a replaceable retriever, independent of the Qdrant/model adapters. It reads stored chunks at query time, so reindexing/deletion/restarts have no second lexical index to synchronize. BM25 uses `k1=1.2`, `b=0.75`, unique query terms, and positive IDF `log(1 + (N - df + 0.5) / (df + 0.5))`. Corpus length/frequency statistics cover only selected documents. The run retains corpus size, query terms, tokenizer/algorithm version and parameters.

The tokenizer uses Unicode NFKC, case folding, Latin/alphanumeric words, full punctuation-separated identifiers and their components, plus Han character unigrams/bigrams. `CEDAR-X17` remains distinct from `CEDAR-X71`; shared components can still retrieve a different identifier. A fixed English stop-word list is versioned in the implementation. This is not linguistic Chinese word segmentation, stemming, simplified/traditional conversion or phrase/exact-match filtering. Other scripts and Han extensions outside the documented regex need future tokenizer work.

BM25 scans/tokenizes all selected chunks per query. It adds CPU/memory work proportional to their text and is intended for the local workbench, not a large-corpus inverted-index service. Qdrant's existing dense collections, backend runtime dependencies and model services are unchanged. The frontend serves PDF.js CMaps/standard fonts locally in development and built modes for Chinese CID PDFs, copying pinned package resources and licenses without a CDN. TypeScript builds add pinned Node type declarations. Fusion uses ranks because raw cosine and BM25 scales differ; it does not learn relevance. Equal RRF scores prefer the higher BM25 score within that single scale, then the dense rank and chunk ID. This explicit tie policy avoids arbitrary IDs deciding between a BM25 tie and a semantic preference; it still does not prove relevance. Candidate depth, repeated/overlapping chunks and irrelevant keyword matches can worsen a result. Reranking remains a later adapter; it cannot recover a source absent from both candidate lists. Check real source content: valid citation membership does not establish semantic entailment.

The separate `dense_retrieval`, `keyword_retrieval` and `rank_fusion` timers record actual work; `retrieval` is their aggregate. Do not add that aggregate to its children. Query embedding time remains separate and is absent for keyword queries.

## Evaluate one treatment

The existing [12-case field guide](../examples/evaluation-cases.json) remains the dense smoke baseline. The original [eight-page retrieval lab](../examples/ragglass-retrieval-lab.pdf) adds [16 bilingual cases](../examples/retrieval-cases.json) covering identifiers/error codes, numbers/dates, similar records, paraphrases and missing answers. Both fixtures and annotations are fictional CC0 data. Upload/index the lab and find its document ID in document details or `/api/documents`.

Run the same questions with fixed K/threshold/depth and generation options; only the retrieval mode changes:

```bash
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode dense --output .data/dense.json
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode keyword --compare .data/dense.json --compare-axis retrieval --output .data/keyword.json
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode hybrid --compare .data/dense.json --compare-axis retrieval --output .data/hybrid.json
```

All three commands default to candidate depth 20 and cosine threshold 0.70. Explicit `--compare-axis retrieval` allows only mode/strategy to vary. Generation/model options, dataset/document/stored-chunk hashes, parser/chunk/embedding/prompt settings, context/recovery settings, candidate depth, K, threshold and lexical/fusion algorithm settings must match. The default generation comparison still requires identical retrieval settings. A mismatch is reported as `comparable: false`, with no deltas presented as a controlled comparison.

Reports include gold-page Recall@K, first-gold-page reciprocal rank (MRR@K), citation coverage, literal expected-text matches, answerability/refusals, retrieval/query latency, reported/unknown token usage, per-category slices and complete run traces. MRR uses the first evidence item containing any gold page; it is page-level, not chunk/claim-level relevance. No-answer cases have no gold-page metric. A retrieved gold page can still be omitted by the context budget or fail to support the answer. Literal matches, a small toy dataset and a sequential run do not establish semantic accuracy, statistical significance or a universal speed/quality gain. Temperature 0 does not guarantee deterministic inference; model weights and shared workloads also matter.

## Verify and explain in interviews

```bash
bash scripts/check.sh
.venv/bin/python scripts/verify_retrieval.py
```

The latter owns temporary loopback API/Qdrant storage, reuses the configured model service, runs the legacy real-stack check, records the dense baseline first, evaluates all three modes, checks threshold/no-evidence behavior, actually restarts its API and runs built Chrome flows. It verifies owner data is unchanged and removes its own services. Full reports stay in ignored `.data/retrieval-verification.json` and `.data/retrieval-evaluation-{dense,keyword,hybrid}.json`. Synthetic contracts are separate from this evidence; actual results are in [the milestone record](MILESTONE.md).

Demonstrate `CEDAR-X17` / `CEDAR-X71` or the Chinese retention question, inspect both candidate lists, follow the final citation and compare the evaluation reports. An interview explanation: “Vector retrieval finds related meanings, while BM25 retains identifiers and keywords. I combine ranks with RRF, keep branch scores distinct, and change only retrieval mode in an annotated evaluation. The trace helps locate a retrieval miss versus a context or generation error; I report regressions as well as improvements.” The [freshly recorded video](DEMO.md#twenty-recorded-steps) shows Chinese BM25, hybrid controls, both candidate lists and source checks; full controlled comparisons remain a separate CLI workflow.

Algorithm references: [BM25 in Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html), [the original RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf). The positive-IDF variant above is explicitly part of this implementation, rather than a claim that every BM25 library uses identical scores.
