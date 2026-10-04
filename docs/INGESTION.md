# Upload checks and document processing

**English** | [繁體中文](INGESTION.zh-TW.md)

[Back to README](../README.md) · [Workbench guide](USAGE.md) · [Reading and query controls](USABILITY.md) · [Measured validation](MILESTONE.md)

## Upload a native-text PDF

The workbench and document library display both configured limits: **30 MB and 200 pages per PDF by default**. There is no total word-count limit. Select a file using **Upload PDF**; the browser checks its size and PDF header, opens it with PDF.js, checks page count and encryption, and looks for selectable text before sending it to the API. **Checking PDF…** and **Uploading PDF…** show which step is running and the filename. Invalid uploads explain what to change; they do not create document records or invoke the document models.

The API independently checks size, PDF validity, encryption, page count, and native text, including requests that bypass the UI. Its PDF inspection runs outside the API event loop. A successful response queues processing immediately; the original PDF is available for reading while the document is processed. Re-uploading identical bytes reuses the existing document ID and index; a stopped or failed duplicate needs **Reindex** to run again.

Native-text inspection is a preflight check, not a guarantee that every page parses well. A mixed PDF with some selectable text can pass; image-only pages are not automatically OCRed. This release rejects documents with no detectable native text and still has no OCR/VLM support.

## Follow progress

The document panel shows **Queued**, **Parsing**, **Chunking**, **Embedding**, or **Indexing**, together with elapsed time. Waiting time is shown while queued; processing elapsed time starts when the worker takes the job. Counts appear after chunks have been produced:

- **Embedded X / N** counts completed embedding batches.
- **Indexed Y / N** counts batches acknowledged by Qdrant. The progress bar represents these written chunks, not the percentage of parsing or total wall time.

Embedding and indexing alternate as batches finish. Parsing shows its stage and measured elapsed time without an estimated percentage or ETA. Active documents refresh approximately every 750 ms; ordinary workspace/service refresh remains every four seconds. Reloading the page reads saved document state without submitting another job. The library also shows indexed/total counts on active document rows.

Document details retain queue/start/finish timestamps, the actual batch size, progress, settings, and stage timings. Embedding and indexing timings accumulate across batches; `total` measures processing time and `queue_wait` is recorded separately. Documents created before these controls remain readable; reindexing populates the new fields.

## Stop or retry

Press **Stop processing**. A queued job can be removed immediately. A running job acknowledges the request with **Stopping…**, finishes its current CPU or Qdrant operation, and stops before the next operation or batch. Docling parsing cannot be interrupted in the middle of conversion, so stopping during parsing may take as long as the remaining conversion. The application keeps cleanup/reindex guards active until the worker has returned.

The final state is **Cancelled**. The original PDF, completed parse artifacts, saved chunks, and confirmed partial vector writes remain available for inspection. Cancelled/failed documents cannot be queried. A progress count describes completed work, not a usable full index. The backend still accepts only ready documents when a query starts, and historical query evidence is not rewritten by cancellation or reindexing.

Choose **Reindex** to process the original PDF again. This restarts the whole pipeline, resets progress, prepares the current collection once, removes this document's obsolete vectors, and builds a full index. It does not resume from a checkpoint. A stopped document can also be deleted using the existing explicit cleanup controls; stopping itself does not delete the PDF or query history.

Normal API shutdown requests cancellation and waits for current operations. After an abrupt interruption, startup marks unfinished jobs failed for explicit reindexing. Saved cancelled records keep their status and progress across restart. This remains a local, single-worker queue, not a distributed background-job service.

## Configure bounded vector batches

Set these values in `.env` before starting the API:

```dotenv
MAX_UPLOAD_MB=30
MAX_PDF_PAGES=200
INGEST_BATCH_SIZE=32
```

`INGEST_BATCH_SIZE` accepts **1–256 chunks**, default **32**. Each outer batch is embedded using the existing internal batch size of 16, written to Qdrant with acknowledgement, and released before the next batch is embedded. This bounds retained vector results by the configured batch, rather than total chunk count. It does not make Docling parsing, all text/chunk metadata, or uploads fully streaming, and is not a claim of a measured reduction in whole-process peak memory. Larger batches can trade more memory and longer stop latency for fewer writes; measure them against your documents. Changing this batching value does not change the embedding-space fingerprint or require an embedding-model migration.

## Reproduce verification

```bash
bash scripts/check.sh
.venv/bin/python scripts/verify_ingestion.py --browser
```

The verifier owns a disposable loopback API and a `qdrant/qdrant:v1.15.5` container, reuses the configured model HTTP service, and removes its own services afterward. It checks early upload rejection, actual batch writes/counts, queued and running cancellation, restart, complete reindex of a fictional 24-page CC0 variant, six live-model sample questions, browser preflight/stop/retry, and existing reading/query/cleanup flows. It hashes the owner's document/SQLite files before and after. Measurements and logs stay ignored under `.data/ingestion-*`.

Synthetic Python contracts separately check vector lifetime between batches, stop boundaries, mutation guards, failures, and shutdown. Browser tests clearly label mocked progress metadata; PDF opening and local preflight tests use actual PDF.js. The six sample questions and repeated fixture are smoke/stress checks, not a retrieval-quality benchmark or a large-corpus performance claim. See the milestone record for results that actually ran.
