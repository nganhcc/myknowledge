# Retrieval evaluation

The evaluator compares vector-only, hybrid/RRF, and hybrid-plus-reranking retrieval against a JSONL benchmark. It is read-only: it does not create conversations, messages, usage logs, or modify documents.

## Benchmark format

The first non-empty line may define a version:

```json
{"type":"metadata","version":"1"}
```

Each remaining line is one case. `document` must match the stored document title, and `page` is optional. Multiple sources are allowed:

```json
{"case_id":"policy-01","question":"How long is the trial period?","expected_sources":[{"document":"employee-handbook.pdf","page":4}]}
```

Keep benchmark files free of secrets and avoid putting full document content in them. Store stable cases in version control and use a dedicated workspace containing the corresponding `READY` documents and embeddings.

## Run

Start PostgreSQL, apply migrations, configure `SECRET_KEY` and `GEMINI_API_KEY`, then run from `backend/`:

```bash
uv run python -m app.evaluation.runner \
  --dataset evals/benchmark.jsonl \
  --workspace-id 00000000-0000-0000-0000-000000000000 \
  --output evals/report.json
```

Embeddings are generated once per case, so the embedding API key is required even though answer generation is not. The output contains aggregate metrics and per-case returned document/page identities, ranks, and latency. It does not contain chunk content.

Use `--modes vector hybrid reranked` to compare modes, or select one mode while developing a benchmark. The reranker may download and load the configured model on its first run.

Metrics are calculated at the requested cutoffs (currently 1, 3, and 5): Hit@k, Recall@k, Precision@k, and MRR. Treat the first report as a baseline for manual inspection before adding CI thresholds.

## End-to-end evaluation

Add a `ground_truth` answer to a case to enable answer judging:

```json
{"case_id":"example-01","question":"What is the trial period?","ground_truth":"The trial lasts 30 days.","expected_sources":[{"document":"handbook.pdf","page":4}],"answerable":true}
```

Run generation, citation analysis, and retrieval comparison with `--e2e`:

```bash
uv run python -m app.evaluation.runner \
  --dataset evals/benchmark.jsonl \
  --workspace-id 00000000-0000-0000-0000-000000000000 \
  --output evals/e2e-report.json \
  --e2e \
  --modes vector hybrid reranked
```

The E2E evaluator is read-only. It does not create conversations, messages, usage logs, or documents. It records the generated answer, returned source identities, token counts, latency, deterministic citation metrics, and (when `ground_truth` is present) Gemini judge scores for answer correctness and context relevance. Citation labels are checked against the actual `[Source N]` positions supplied to the model; an out-of-range label is invalid. The report intentionally excludes retrieved chunk content.

E2E runs require Gemini access for embeddings, answer generation, and judging. Each case and retrieval mode uses a generation request and a separate judge request, so running all three modes has a materially higher cost than retrieval-only evaluation. Review a report manually before treating judge scores as release-quality evidence.