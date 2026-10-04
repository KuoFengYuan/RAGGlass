# RAGGlass announcement drafts

**English** | [繁體中文](ANNOUNCEMENT.zh-TW.md)

These drafts describe the current native-text PDF workbench. Before posting, adapt the motivation to your own experience and confirm that you can help people run it. Pair a post with the [current English-captioned demo](../README.md#watch-the-demo) or [share cover](images/social-preview.png). Channel rules and a suggested first-week plan are in [Sharing RAGGlass](LAUNCH.md).

## Short post

When a PDF RAG answer looks wrong, how do you check the original source?

I'm building RAGGlass: a local, open-source workbench that puts PDFs, retrieved evidence, and answers side by side. Click a citation to its source page; inspect saved prompts, settings, and timings.

Try the sample: https://github.com/KuoFengYuan/RAGGlass

Suggested optional tags: `#RAG #OpenSource #LocalAI`. Adjust the text for the platform's current length limit; the short draft does not require a fixed character quota.

## Longer technical post

PDF RAG can return a plausible answer while making it hard to check what the model actually saw. Was the table parsed correctly? Did retrieval find the right row? Which original page supports the answer?

I'm building **RAGGlass — See inside your RAG.** It's an MIT-licensed local workbench for inspecting that document-to-answer path.

The current workbench lets you:

- Upload a native-text PDF and inspect Docling's parsed content.
- Compare the original PDF, scored retrieved passages, and a live model answer.
- Click validated source IDs to open the corresponding original pages.
- Inspect vector/BM25/hybrid rankings, context budgets and reported model tokens.
- Generate a three-point document summary, stop a run, and export evidence.
- Reopen saved runs with prompts, evidence, configuration, answers, and stage timings.

The fresh 20-step demo indexes two fictional CC0 PDFs, follows the 30 MB answer to the original table, searches Chinese source text, compares BM25/hybrid candidates and inspects actual token usage. It also shows a three-point summary, cancellation, exports, an unsupported question, history and independent cleanup. Inference uses a real local model at normal speed; complete controlled evaluation is a separate CLI workflow.

Stack: Vue 3/PDF.js, FastAPI, Docling, Qdrant, SQLite, local E5 embeddings, and a separate Ollama or compatible model HTTP service. English and Traditional Chinese setup/usage guides are included.

Native-text PDFs are the current scope. Vector/BM25/hybrid modes and small controlled bilingual evaluations are implemented; see the [retrieval guide](RETRIEVAL.md). OCR, reranking, automatic diagnosis and broad production evaluations remain future work. Source-ID validation checks where a citation came from; it does not prove that every answer claim is supported.

Try the public sample or share a sanitized reproduction of a parsing/retrieval problem:
https://github.com/KuoFengYuan/RAGGlass

If it helps your RAG work, a star helps other engineers discover it.

## Show HN title

**Show HN: RAGGlass – Trace PDF RAG answers back to their source pages**

Submission link: https://github.com/KuoFengYuan/RAGGlass

## Show HN first comment draft

RAGGlass is a local workbench for engineers inspecting PDF RAG. The original PDF sits beside the retrieved passages and answer, and a source button takes you to the original page. Runs retain the actual prompt, configuration, evidence, answer, and timings in SQLite/local storage, with vectors in Qdrant.

The repository includes a three-page fictional CC0 PDF, six smoke-test questions, English/Traditional Chinese instructions, and a recorded live-model demo. You need Python 3.12, Node 20.19+, Docker Compose, and a reachable Ollama or compatible model service. First-time dependency and model downloads require internet access. This is an early native-text PDF release and runs on loopback by default.

The implementation separates parser, embedder, retriever, and answer-model adapters. Citations are checked against IDs retrieved for that query, then resolved on the backend to the original file/page. That prevents nonexistent source links, but doesn't establish claim entailment; that needs additional evaluation.

I'm interested in feedback about PDF/table evidence inspection, installation friction, and which information makes a failed retrieval easier to understand. Public sample reproductions are welcome.

Author note before posting: add your own concrete reason for building it and the implementation details you can discuss. Follow the [Show HN guidelines](https://news.ycombinator.com/showhn.html); the submission and first comment intentionally invite feedback without an upvote request.

## Follow-up post

How can you tell whether a PDF RAG answer used the right table row?

This RAGGlass walkthrough follows a real local-model answer through the retrieved chunk to the original page, then checks an unanswerable question. It includes reproduction steps and explains what citation validation can and cannot establish:

https://github.com/KuoFengYuan/RAGGlass/blob/main/docs/CASE_STUDY.md

These are prepared drafts. Their presence in the repository does not mean they have been posted or generated traffic.
