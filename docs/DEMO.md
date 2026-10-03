# Follow the video tutorial

**English** | [繁體中文](DEMO.zh-TW.md)

[Play the English tutorial directly in the README](../README.md#watch-the-demo). The instructional captions are burned into the video: no subtitle switch or separate download is needed. Each scene names the step, the control to use, and what to inspect. Captions sit below the workbench and above the player's control area.

## Seven steps

The recording shows the English UI. The times below are approximate scene starts. Use the player to pause or seek while following the [illustrated usage guide](USAGE.md).

| Time | Step | What to do |
| --- | --- | --- |
| 00:00 | Start the tour | Compare the original PDF on the left with retrieved evidence and the answer on the right. |
| 00:04 | 1. Upload a PDF | Click **Upload PDF**, select the CC0 sample, and wait for **Indexed**. The recording reuses its existing index. |
| 00:09 | 2. Ask a question | Enter “What is the maximum upload size for the Cedar pilot?” and click **Retrieve & answer**. Inspect the retrieved passages and the live answer. |
| 00:18 | 3. Check the citation | Click the source below the answer. Page 2 opens; verify **30 MB** in the original table. |
| 00:26 | 4. Inspect parsing | Open **Parsed content**. Compare the parsed table, chunk ID, and source page with the PDF. Source boxes identify content items, not exact text spans. |
| 00:31 | 5. Review the run | Expand **Run settings & prompt**. Inspect the prompt, model, retrieval configuration, and measured timings. |
| 00:36 | 6. Check an unsupported question | Ask “What is the pilot's annual electricity cost in dollars?” The document cannot confirm this; the saved answer refuses and has no citations. |
| 00:42 | 7. Reopen history | Open **Run history**, choose a saved question, and revisit its answer, evidence, and settings. |
| 00:47 | Try it yourself | Follow the [quick start](../README.md#quick-start) and run the public sample's [six questions](../examples/questions.json) with your own model service. |

## Recording and subtitles

The current tutorial reuses the original real-inference footage and plays at normal speed. Only the instructional captions and their background area were re-rendered. This edit adds **zero model queries**, preserves the original answers and query timings, and does not measure GPU performance. The fictional CC0 fixture describes an invented Cedar pilot.

- [Original recording receipt](media/demo-recording.json): source document hash, live model answers, citations, and measured query timings.
- [Tutorial source](media/demo-tutorial.json): complete English and Traditional Chinese step text.
- [Render receipt](media/demo-tutorial-render.json): source/renderer hashes and measured output duration, dimensions, and file hashes.
- [English subtitle text](media/ragglass-demo.vtt): the same title, action, and note shown inside the video.

To revise the captions or make a fresh recording, use the [media reproduction instructions](LAUNCH.md#reproduce-the-media). GitHub hosts the inline player; other Markdown viewers may display its URL. The current Chinese tutorial uses the same English UI with Traditional Chinese instructional captions. The application itself offers a persistent language switch.
