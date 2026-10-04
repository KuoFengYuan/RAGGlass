# Video tutorial and current controls

**English** | [繁體中文](DEMO.zh-TW.md)

[Play the English tutorial directly in the README](../README.md#watch-the-demo). The instructional captions are burned into the video: no subtitle switch or separate download is needed. Each scene names the step, the control to use, and what to inspect. Captions sit below the workbench and above the player's control area.

## What the video covers

The published **84.7-second** recording uses application commit `7e16f9b`. Reading/query controls, upload progress and model workflows were added afterward. The timed steps below describe that footage; the [current-controls walkthrough](#try-the-current-controls) describes the application after those updates. It has no video timestamps because these controls have not been recorded in the published video.

| Capability | In the published video? | Current instructions |
| --- | --- | --- |
| Upload, question, citation, parsing, refusal, history and cleanup | Yes; upload reuses an existing index. | [Nine recorded steps](#nine-recorded-steps) and [cleanup](CLEANUP.md). |
| Upload preflight, confirmed chunk progress, stop/reindex | No. | [Upload and processing](INGESTION.md). |
| Query progress/stop, PDF search/zoom/text selection, copy/Markdown | No. | [Reading and query controls](USABILITY.md). |
| Temperature / Top-P / output limits, Context/Token usage, bounded recovery | No. | [Context and model workflows](WORKFLOWS.md). |
| Whole-document three-point summary and per-node sources | No. | [Long-document summary](WORKFLOWS.md#long-document-summary). |
| Fixed 12-case bilingual evaluation and generation comparisons | No; use the CLI. | [Repeatable evaluation](WORKFLOWS.md#repeatable-evaluation). |

## Nine recorded steps

The recording shows the English UI. The times below are approximate scene starts. Use the player to pause or seek while following the [illustrated usage guide](USAGE.md).

| Time | Step | What to do |
| --- | --- | --- |
| 00:00 | Start the tour | Compare the original PDF on the left with retrieved evidence and the answer on the right. |
| 00:04 | 1. Upload a PDF | Click **Upload PDF**, select the CC0 sample, and wait for **Indexed**. The recording reuses its existing index. |
| 00:09 | 2. Ask a question | Enter “What is the maximum upload size for the Cedar pilot?” and click **Retrieve & answer**. Inspect the retrieved passages and the live answer. |
| 00:14 | 3. Check the citation | Click the source below the answer. Page 2 opens; verify **30 MB** in the original table. |
| 00:21 | 4. Inspect parsing | Open **Parsed content**. Compare the parsed table, chunk ID, and source page with the PDF. Source boxes identify content items, not exact text spans. |
| 00:26 | 5. Review the run | Expand **Run settings & prompt**. Inspect the prompt, model, retrieval configuration, and measured timings. |
| 00:31 | 6. Check an unsupported question | Ask “What is the pilot's annual electricity cost in dollars?” The document cannot confirm this; the saved answer refuses and has no citations. |
| 00:37 | 7. Reopen history | Open **Run history**, choose a saved question, and revisit its answer, evidence, and settings. |
| 00:42 | 8. Clean up PDFs | Open **Document library**, search/select the fixture, and **Delete selected**. Read and confirm the permanent removal. History remains; unavailable original-page links are disabled. |
| 00:53 | 9. Clear history | Open **Run history → Clear all → Delete permanently**. Read the count and scope. This removes records independently from PDFs. |
| 01:02 | Try it yourself | Follow the [quick start](../README.md#quick-start) and run the public sample's [six questions](../examples/questions.json) with your own model service. |

## Try the current controls

Start the current application using the [quick start](../README.md#quick-start). The instructions here use the English UI; the language selector persists across reloads. Use the fictional CC0 PDF for practice. Its Cedar facts are fixture content, not live application settings.

1. **Check and process an upload.** Read **Upload limits** before selecting a native-text PDF. Defaults are 30 MB / 200 pages, with no total word-count limit. Watch **Checking PDF… → Uploading PDF…**, then the document's queued/parsing/chunking/embedding/indexing stages. Indexed chunk counts describe confirmed writes, not a parsing completion percentage. A duplicate reuses its index; a new PDF or **Reindex** runs processing. **Stop processing** keeps the original and stops after the current operation; **Reindex** restarts the full pipeline.
2. **Follow or stop a question.** Ask the page-2 upload-size question. Watch stages and elapsed seconds while evidence appears. Use **Stop query** to retain a cancelled trace without a final answer; submit again to create a new run. Closing the browser tab does not stop server work.
3. **Read the source and reuse the answer.** Click its page-2 citation, search for `30 MB` in **Search this PDF…**, adjust **Zoom**, and select native text. Use **Copy answer & sources**, **Download Markdown**, or **Download run JSON**. Source boxes and search highlights have different purposes; neither proves every model claim is correct.
4. **Control generation per run.** Open **Generation options**. Try **Precise phrasing** (`T=0, P=1`), or adjust Temperature / Top-P / output-token limit within the shown ranges. Ask again and reopen the run from history to check its saved values. Low temperature does not guarantee valid JSON or correct facts.
5. **Explain context and recovery.** Compare **Estimated input**, **Input budget**, **Output reserved**, and included/omitted chunks in **Context & model calls**. Compare them with reported input/output tokens. Original omitted chunks remain inspectable but cannot be cited by the model. Expand attempts to inspect prompts, outcomes and timings; retries/repairs appear when needed, not on every query. Usage without a complete model report is unknown, and token counters are not a currency bill. See [bounded recovery](WORKFLOWS.md#bounded-recovery) for caps and [Context and tokens](WORKFLOWS.md#context-and-tokens) for the estimator.
6. **Summarize the whole document.** Choose **Summarize document in 3 points**. Inspect **Document summary steps**: map batches cover every stored chunk, reduce nodes appear if notes exceed the budget, and the final node produces three points or refuses. Follow source buttons and check names, dates, amounts and requested actions. Save/reopen the trace; use **Stop query** if needed. Top-K does not restrict summary sources, and input coverage does not prove all facts survived compression.
7. **Compare a controlled change.** With an indexed field-guide PDF, run the [evaluation commands](WORKFLOWS.md#repeatable-evaluation) against the same 12 English/Chinese cases. Keep document/parser/chunk/embedding/retrieval/prompt conditions fixed and change one generation setting. Inspect page recall, citation coverage, expected-text matches, refusals, latency and reported/unknown tokens. The evaluator is a CLI; these smoke checks are not a semantic accuracy score.

For a project-based interview explanation, use the [question-to-implementation table](WORKFLOWS.md#interview-questions-tied-to-the-project) and demonstrate a saved run beside its PDF. The separate [workflow milestone](MILESTONE.md) records real validation; those results are not additional scenes in this video.

## Recording and subtitles

The published tutorial was recorded from application commit `7e16f9b` with cleanup controls. It includes **two live model queries** and actual PDF/history deletion in a disposable workspace, at normal speed. Both language videos are 84.7 seconds. Rendering captions over this footage adds no further model queries and cannot demonstrate controls absent from the original frames. The recording does not measure GPU performance; the CC0 Cedar pilot is fictional. Your normal workspace is separate. See the [cleanup guide](CLEANUP.md) for the effects of deletion.

- [Published recording receipt](media/demo-recording.json): source document hash, live model answers, citations, and measured query timings.
- [Tutorial source](media/demo-tutorial.json): complete English and Traditional Chinese step text.
- [Render receipt](media/demo-tutorial-render.json): source/renderer hashes and measured output duration, dimensions, and file hashes.
- [English subtitle text](media/ragglass-demo.vtt): the same title, action, and note shown inside the video.

To revise the captions or make a fresh recording, use the [media reproduction instructions](LAUNCH.md#reproduce-the-media). GitHub hosts the inline player; other Markdown viewers may display its URL. The current Chinese tutorial uses the same English UI with Traditional Chinese instructional captions. The application itself offers a persistent language switch.

When functionality changes, update both READMEs, this guide's coverage/current controls and the relevant feature guides together. Subtitle instructions must match recorded frames. A new feature shown in video requires fresh footage, matching bilingual captions/receipts and published embed metadata; keep the recorded version and uncovered controls explicit until that happens.
