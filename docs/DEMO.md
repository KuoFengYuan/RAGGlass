# Video tutorial and current controls

**English** | [繁體中文](DEMO.zh-TW.md)

[Play the English tutorial directly in the README](../README.md#watch-the-demo). The instructional captions are burned into the video: no subtitle switch or separate download is needed. Each scene names the step, the control to use, and what to inspect. Captions sit below the workbench and above the player's control area.

## What the video covers

The freshly recorded **168.4-second** tutorial uses application commit `7855a83`, including the current reading, upload-progress, model-workflow and hybrid-retrieval controls. It starts from empty disposable storage and indexes both original fictional CC0 PDFs. The timed steps describe the actual footage; the [current-controls walkthrough](#try-the-current-controls) also covers operations and evaluation outside the recording.

| Capability | In the published video? | Further instructions |
| --- | --- | --- |
| Fresh upload/progress, questions, citations, parsing, refusal, history and independent cleanup | Yes; neither PDF reuses an index. | [Twenty recorded steps](#twenty-recorded-steps) and [cleanup](CLEANUP.md). |
| Stop processing / reindex | Controls may be visible; these operations are not performed. | [Upload and processing](INGESTION.md). |
| Query progress/stop, PDF search/zoom, copy/Markdown | Yes; a running summary is cancelled. Native text selection and run-JSON download are not demonstrated. | [Reading and query controls](USABILITY.md). |
| Temperature / Top-P / output limits, Context/Token usage and attempts | Yes; no forced failure, retry or JSON repair is recorded. | [Context and model workflows](WORKFLOWS.md). |
| Whole-document three-point summary and per-node sources | Yes; the small sample uses map/final nodes and needs no reduce layer. | [Long-document summary](WORKFLOWS.md#long-document-summary). |
| Vector/BM25/hybrid modes, both candidate lists and Chinese source/search | Yes. | [Retrieval modes](RETRIEVAL.md). |
| Persistent language switch | Yes; switch to Traditional Chinese and reload, then return to English. | [Illustrated usage](USAGE.md). |
| 12-case baseline, 16-case retrieval lab and controlled comparisons | Not filmed; use the CLI linked in the closing scene. | [Retrieval evaluation](RETRIEVAL.md#evaluate-one-treatment). |

## Twenty recorded steps

The recording primarily uses the English UI, with one Traditional Chinese language-persistence scene. Times are rounded scene starts. Pause or seek while following the [illustrated usage guide](USAGE.md).

| Time | Step | What to do and inspect |
| --- | --- | --- |
| 00:00 | RAGGlass. See inside your RAG | Follow a PDF from upload to evidence and a grounded answer. Fresh footage, real local inference, fictional CC0 documents. |
| 00:04 | 1. Upload and track processing | Click Upload PDF; watch inspection, parsing and indexing. This empty workspace creates a fresh index; OCR is disabled. |
| 00:18 | 2. Set generation options | Open Generation options; set Temperature, Top-P and output limit. These options are saved per run, not applied to the shared model server. |
| 00:24 | 3. Ask with vector retrieval | Ask the upload-limit question; click Retrieve & answer. Query progress follows real E5, Qdrant and model inference. |
| 00:30 | 4. Follow a source citation | Click the page-2 source and verify 30 MB in the original table. Valid source IDs do not prove every claim is semantically supported. |
| 00:36 | 5. Search and zoom the PDF | Search for 30 MB and change PDF zoom to 125%. Native text remains searchable and selectable; this is not OCR. |
| 00:43 | 6. Inspect parsed chunks | Open Parsed content and locate the upload-limit table. Compare text, chunk IDs and retained source pages. |
| 00:48 | 7. Try Chinese keyword retrieval | Upload the retrieval lab; choose Keyword and ask about retention. BM25 skips query embedding; the cosine threshold is disabled. |
| 01:00 | 8. Check the Chinese original | Follow page 6 and search the PDF for 九十天. Local PDF.js character maps preserve native Chinese text. |
| 01:07 | 9. Combine vector and keyword retrieval | Choose Hybrid: Top K 3, 20 candidates; ask about CEDAR-X17. RRF merges ranks; cosine filters only the vector branch. |
| 01:14 | 10. Inspect both candidate lists | Expand Retrieval rankings; compare raw scores and selected IDs. Cosine, BM25 and RRF use different scales; none is confidence. |
| 01:22 | 11. Compare estimates and actual tokens | Inspect Context & model calls: input budget and reported usage. UTF-8 preflight estimates differ from model-native token counts. |
| 01:29 | 12. Copy and export evidence | Copy answer & sources, then download the Markdown report. The actual export includes saved hybrid settings and branch scores. |
| 01:34 | 13. Summarize the whole document | Select the field guide; click Summarize document in 3 points. The live summary covers stored chunks and requires cited sources. |
| 01:48 | 14. Inspect summary nodes | Expand a Document summary step to inspect its sources and prompt. Map/final nodes run live; reduce is needed only when notes exceed budget. |
| 01:54 | 15. Stop a running summary | Start another summary, then click Stop query during generation. The cancelled record retains evidence and shows no final answer. |
| 02:01 | 16. Test an unsupported question | Ask about annual electricity cost and inspect the uncited refusal. This fictional document does not provide the requested cost. |
| 02:09 | 17. Restore a hybrid run | Open Run history and reopen the CEDAR-X17 question. The original PDF, retrieval mode and candidate depth are restored. |
| 02:17 | 18. Switch language persistently | Choose 繁體中文; reload and verify the language is retained. UI language does not translate an existing model answer. |
| 02:22 | 19. Delete a PDF independently | Select the retrieval lab in Document library; confirm Delete selected. History remains; links to the removed original become disabled. |
| 02:34 | 20. Clear saved runs | Open Run history, choose Clear all and confirm the scope. The remaining field-guide PDF and index are preserved. |
| 02:42 | Your turn. Reproduce and evaluate | Try both CC0 PDFs; use the CLI for controlled mode comparisons. See the bilingual guide for limitations and the 16-case evaluation. |

## Try the current controls

Start the current application using the [quick start](../README.md#quick-start). The instructions here use the English UI; the language selector persists across reloads. Use the fictional CC0 PDF for practice. Its Cedar facts are fixture content, not live application settings.

1. **Check and process an upload.** Read **Upload limits** before selecting a native-text PDF. Defaults are 30 MB / 200 pages, with no total word-count limit. Watch **Checking PDF… → Uploading PDF…**, then the document's queued/parsing/chunking/embedding/indexing stages. Indexed chunk counts describe confirmed writes, not a parsing completion percentage. A duplicate reuses its index; a new PDF or **Reindex** runs processing. **Stop processing** keeps the original and stops after the current operation; **Reindex** restarts the full pipeline.
2. **Follow or stop a question.** Ask the page-2 upload-size question. Watch stages and elapsed seconds while evidence appears. Use **Stop query** to retain a cancelled trace without a final answer; submit again to create a new run. Closing the browser tab does not stop server work.
3. **Read the source and reuse the answer.** Click its page-2 citation, search for `30 MB` in **Search this PDF…**, adjust **Zoom**, and select native text. Use **Copy answer & sources**, **Download Markdown**, or **Download run JSON**. Source boxes and search highlights have different purposes; neither proves every model claim is correct.
4. **Control generation per run.** Open **Generation options**. Try **Precise phrasing** (`T=0, P=1`), or adjust Temperature / Top-P / output-token limit within the shown ranges. Ask again and reopen the run from history to check its saved values. Low temperature does not guarantee valid JSON or correct facts.
5. **Explain context and recovery.** Compare **Estimated input**, **Input budget**, **Output reserved**, and included/omitted chunks in **Context & model calls**. Compare them with reported input/output tokens. Original omitted chunks remain inspectable but cannot be cited by the model. Expand attempts to inspect prompts, outcomes and timings; retries/repairs appear when needed, not on every query. Usage without a complete model report is unknown, and token counters are not a currency bill. See [bounded recovery](WORKFLOWS.md#bounded-recovery) for caps and [Context and tokens](WORKFLOWS.md#context-and-tokens) for the estimator.
6. **Summarize the whole document.** Choose **Summarize document in 3 points**. Inspect **Document summary steps**: map batches cover every stored chunk, reduce nodes appear if notes exceed the budget, and the final node produces three points or refuses. Follow source buttons and check names, dates, amounts and requested actions. Save/reopen the trace; use **Stop query** if needed. Top-K does not restrict summary sources, and input coverage does not prove all facts survived compression.
7. **Inspect retrieval choices.** Open **Retrieval options → Retrieval mode** and try Vector, Keyword · BM25 and Hybrid · RRF. Compare labeled scores and **Retrieval rankings**; final Top K differs from hybrid candidates per method. The cosine threshold never filters BM25/RRF. Try the [eight-page lab and bilingual cases](RETRIEVAL.md), follow a source citation and reopen history to restore the mode.
8. **Compare a controlled change.** With an indexed field-guide PDF, run the [evaluation commands](WORKFLOWS.md#repeatable-evaluation) against the same 12 English/Chinese cases. Keep document/parser/chunk/embedding/retrieval/prompt conditions fixed and change one generation setting. Inspect page recall/MRR, citation coverage, expected-text matches, refusals, latency and reported/unknown tokens. For retrieval changes, use the separate [16-case mode comparisons](RETRIEVAL.md#evaluate-one-treatment), fixing generation and all other retrieval settings. The evaluator is a CLI; these smoke checks are not a semantic accuracy score.

For a project-based interview explanation, use the [question-to-implementation table](WORKFLOWS.md#interview-questions-tied-to-the-project) and demonstrate a saved run beside its PDF. The separate [workflow milestone](MILESTONE.md) records real validation; those results are not additional scenes in this video.

## Recording and subtitles

The tutorial records application commit `7855a83` at normal speed in an owned disposable workspace. It includes **four real-model questions**, **one completed three-point summary** (map/final), and **one summary cancelled during generation**. Both language videos are 168.4 seconds. The two public PDFs are freshly parsed, embedded and indexed; the lab is then deleted independently of its saved runs, and clearing history preserves the remaining field-guide PDF. Rendering subtitles adds zero model queries. The small sample needs no reduce layer; forced recovery failures and full CLI evaluation are not filmed. The recording does not measure GPU performance. Both CC0 documents are fictional and separate from the owner's normal workspace. See the [cleanup guide](CLEANUP.md) for deletion effects.

- [Published recording receipt](media/demo-recording.json): source document hash, live model answers, citations, and measured query timings.
- [Tutorial source](media/demo-tutorial.json): complete English and Traditional Chinese step text.
- [Render receipt](media/demo-tutorial-render.json): source/renderer hashes and measured output duration, dimensions, and file hashes.
- [English subtitle text](media/ragglass-demo.vtt): the same title, action, and note shown inside the video.

To revise the captions or make a fresh recording, use the [media reproduction instructions](LAUNCH.md#reproduce-the-media). GitHub hosts the inline player; other Markdown viewers may display its URL. Both language tutorials share the actual footage, primarily English UI with a Traditional Chinese switch/reload scene, and their own instructional captions.

When functionality changes, update both READMEs, this guide's coverage/current controls and the relevant feature guides together. Subtitle instructions must match recorded frames. A new feature shown in video requires fresh footage, matching bilingual captions/receipts and published embed metadata; keep the recorded version and uncovered controls explicit until that happens.
