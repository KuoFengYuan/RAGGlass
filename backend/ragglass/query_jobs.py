"""Track cancellable queries in this application's single API worker."""

import asyncio

from .errors import PipelineError
from .pipeline import QueryControl
from .store import now


class QueryJobs:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.active = {}

    def start(self, question, documents, top_k, threshold, generation=None, **workflow):
        activity = self.pipeline.workspace.activity(
            [d["id"] for d in documents], query=True, wait=False
        )
        activity.__enter__()
        try:
            run = self.pipeline.new_query(
                question, documents, top_k, threshold, generation, **workflow
            )
            control = QueryControl()
            task = asyncio.create_task(self._execute(run, control, activity))
            self.active[run["id"]] = (run, control, task)
            return run
        except BaseException:
            activity.__exit__(None, None, None)
            raise

    async def _execute(self, run, control, activity):
        try:
            return await self.pipeline.execute_query(run, control)
        finally:
            activity.__exit__(None, None, None)
            self.active.pop(run["id"], None)

    def cancel(self, run_id):
        current = self.active.get(run_id)
        if current:
            run, control, _ = current
            if not run["cancel_requested"]:
                run.update(cancel_requested=True, cancel_requested_at=now())
                self.pipeline.store.save_run(run)
                control.cancel()
            return run
        run = self.pipeline.store.run(run_id)
        if run is None:
            raise PipelineError("run_missing", "找不到執行紀錄。", 404)
        if run["status"] == "running":
            raise PipelineError("query_not_cancellable", "此查詢由同步 API 執行，請等待完成。", 409)
        return run

    async def close(self):
        tasks = [entry[2] for entry in self.active.values()]
        for run_id in list(self.active):
            self.cancel(run_id)
        await asyncio.gather(*tasks, return_exceptions=True)
