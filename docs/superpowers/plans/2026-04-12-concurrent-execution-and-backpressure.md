# Concurrent Execution And Backpressure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded task admission, concurrent task/rule execution, and model concurrency limits so single tasks finish faster without overrunning shared model capacity.

**Architecture:** Keep the service single-process, but split execution control across three layers: bounded waiting queue at submission time, concurrent worker/rule scheduling inside the process, and semaphore-based resource limits for model/API calls. Preserve current task semantics by ordering final results deterministically and isolating per-rule failures into `error` results instead of failing whole tasks.

**Tech Stack:** Python 3.12, FastAPI, asyncio, aiosqlite, httpx, pytest, uv

---

### Task 1: Prepare Baseline And Queue Admission Tests

**Files:**
- Modify: `tests/test_api/test_router.py`
- Modify: `tests/test_worker/test_worker.py`
- Test: `tests/test_api/test_router.py`
- Test: `tests/test_worker/test_worker.py`

- [ ] **Step 1: Write failing queue/backpressure tests**

Add tests covering:
- `TaskQueue(maxsize=1)` rejects the second `try_enqueue()`
- `/api/v1/check/submit` returns `429` when the waiting queue is full
- `429` submission does not leave a persisted task row or uploaded files behind

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run python -m pytest tests/test_api/test_router.py tests/test_worker/test_worker.py -q`
Expected: FAIL because queue capacity APIs and `429` behavior do not exist yet

- [ ] **Step 3: Implement bounded queue admission**

Modify:
- `src/report_check/worker/queue.py`
- `src/report_check/api/router.py`
- `src/report_check/storage/database.py` if deletion helper is needed
- `src/report_check/storage/file.py` if cleanup helper needs extension

Implementation points:
- Add `maxsize` support to `TaskQueue`
- Add `try_enqueue(task_id) -> bool`
- Make submit handler return `429` with `Retry-After` when the waiting queue is full
- Clean up task row and uploaded files when queue admission fails

- [ ] **Step 4: Re-run the focused tests**

Run: `uv run python -m pytest tests/test_api/test_router.py tests/test_worker/test_worker.py -q`
Expected: PASS for the new queue/admission cases

- [ ] **Step 5: Commit**

```bash
git add tests/test_api/test_router.py tests/test_worker/test_worker.py src/report_check/worker/queue.py src/report_check/api/router.py src/report_check/storage/database.py src/report_check/storage/file.py
git commit -m "feat: add bounded task admission"
```

### Task 2: Add Configurable Worker Concurrency

**Files:**
- Modify: `src/report_check/main.py`
- Modify: `src/report_check/worker/worker.py`
- Modify: `config/app.yaml`
- Modify: `tests/test_worker/test_worker.py`
- Test: `tests/test_worker/test_worker.py`

- [ ] **Step 1: Write failing worker concurrency tests**

Add tests covering:
- `BackgroundWorker` starts multiple consumer tasks when `worker_concurrency > 1`
- Two queued tasks can be processed concurrently under a controlled fake checker/model setup

- [ ] **Step 2: Run the worker tests to verify they fail**

Run: `uv run python -m pytest tests/test_worker/test_worker.py -q`
Expected: FAIL because worker concurrency is currently hard-coded to one loop

- [ ] **Step 3: Implement worker concurrency**

Implementation points:
- Load `execution.worker_concurrency` from `config/app.yaml`
- Start and stop multiple worker loops in `BackgroundWorker`
- Keep orphan recovery behavior working with the shared queue
- Expose running-worker metadata if needed for health reporting

- [ ] **Step 4: Re-run the worker tests**

Run: `uv run python -m pytest tests/test_worker/test_worker.py -q`
Expected: PASS including the new concurrency coverage

- [ ] **Step 5: Commit**

```bash
git add src/report_check/main.py src/report_check/worker/worker.py config/app.yaml tests/test_worker/test_worker.py
git commit -m "feat: add concurrent task workers"
```

### Task 3: Add Per-Task Rule Concurrency And Ordered Result Aggregation

**Files:**
- Modify: `src/report_check/worker/worker.py`
- Modify: `src/report_check/checkers/factory.py`
- Modify: `tests/test_worker/test_worker.py`
- Test: `tests/test_worker/test_worker.py`

- [ ] **Step 1: Write failing rule concurrency tests**

Add tests covering:
- Rules execute concurrently within one task when `per_task_rule_concurrency > 1`
- Final `check_results` order still matches DSL order
- A single rule exception becomes an `error` result without failing sibling rules

- [ ] **Step 2: Run the worker tests to verify they fail**

Run: `uv run python -m pytest tests/test_worker/test_worker.py -q`
Expected: FAIL because rules are still executed sequentially

- [ ] **Step 3: Implement per-task rule scheduling**

Implementation points:
- Load `execution.per_task_rule_concurrency`
- Replace the sequential rule loop with bounded concurrent scheduling
- Preserve result ordering by rule index
- Convert per-rule exceptions into synthetic `error` results
- Rework progress updates around completed rule count instead of loop index

- [ ] **Step 4: Re-run the worker tests**

Run: `uv run python -m pytest tests/test_worker/test_worker.py -q`
Expected: PASS with new concurrency and error isolation cases

- [ ] **Step 5: Commit**

```bash
git add src/report_check/worker/worker.py src/report_check/checkers/factory.py tests/test_worker/test_worker.py
git commit -m "feat: add concurrent rule execution"
```

### Task 4: Add Model Concurrency Limits

**Files:**
- Modify: `src/report_check/models/manager.py`
- Modify: `src/report_check/main.py`
- Modify: `config/models.yaml`
- Modify: `tests/test_models/test_manager.py`
- Test: `tests/test_models/test_manager.py`

- [ ] **Step 1: Write failing model limit tests**

Add tests covering:
- provider-level semaphore bounds total concurrent calls
- text and multimodal semaphore limits can be enforced independently
- retry sleeps do not keep the semaphore occupied

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `uv run python -m pytest tests/test_models/test_manager.py -q`
Expected: FAIL because `ModelManager` has no concurrency controls yet

- [ ] **Step 3: Implement semaphore-based model limits**

Implementation points:
- Accept provider config for `max_concurrency`, `text_max_concurrency`, `multimodal_max_concurrency`
- Track inflight counts for observability
- Wrap single request attempts, not the whole retry lifecycle

- [ ] **Step 4: Re-run the model tests**

Run: `uv run python -m pytest tests/test_models/test_manager.py -q`
Expected: PASS for concurrency-limit behaviors

- [ ] **Step 5: Commit**

```bash
git add src/report_check/models/manager.py src/report_check/main.py config/models.yaml tests/test_models/test_manager.py
git commit -m "feat: add model concurrency limits"
```

### Task 5: Thread Offload, Health Reporting, And Regression Coverage

**Files:**
- Modify: `src/report_check/worker/worker.py`
- Modify: `src/report_check/api/schemas.py`
- Modify: `src/report_check/api/router.py`
- Modify: `src/report_check/main.py`
- Modify: `tests/test_api/test_router.py`
- Modify: `tests/test_worker/test_worker.py`
- Modify: `tests/test_models/test_manager.py`
- Test: `tests/test_api/test_router.py`
- Test: `tests/test_worker/test_worker.py`
- Test: `tests/test_models/test_manager.py`

- [ ] **Step 1: Write failing regression/health tests**

Add tests covering:
- parsing is dispatched through `asyncio.to_thread`
- `/api/v1/health` includes the new execution counters
- progress remains monotonic under concurrent rule completion

- [ ] **Step 2: Run the regression test set to verify it fails**

Run: `uv run python -m pytest tests/test_api/test_router.py tests/test_worker/test_worker.py tests/test_models/test_manager.py -q`
Expected: FAIL because health payload and thread-offload behaviors are not implemented yet

- [ ] **Step 3: Implement the remaining runtime changes**

Implementation points:
- offload blocking parser work with `asyncio.to_thread`
- expose queue/running/model inflight fields in health response
- ensure progress updates are monotonic and throttled if needed

- [ ] **Step 4: Run the focused regression suite**

Run: `uv run python -m pytest tests/test_api/test_router.py tests/test_worker/test_worker.py tests/test_models/test_manager.py -q`
Expected: PASS

- [ ] **Step 5: Run a broader backend regression**

Run: `uv run python -m pytest tests/test_api tests/test_worker tests/test_models tests/test_storage -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/report_check/worker/worker.py src/report_check/api/schemas.py src/report_check/api/router.py src/report_check/main.py tests/test_api/test_router.py tests/test_worker/test_worker.py tests/test_models/test_manager.py
git commit -m "feat: finish concurrent execution backpressure runtime"
```
