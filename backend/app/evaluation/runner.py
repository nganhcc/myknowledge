import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.session import async_session_factory
from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import aggregate_results, evaluate_case
from app.services.embedder import embed_texts
from app.services.reranker import rerank_chunks
from app.services.retrieval import (
    _lexical_candidates,
    _vector_candidates,
    reciprocal_rank_fusion,
)


async def _retrieve(
    db: Any,
    workspace_id: uuid.UUID,
    question: str,
    embedding: list[float],
    mode: str,
    top_k: int,
) -> list[Any]:
    candidate_limit = max(top_k, settings.retrieval_candidate_limit)
    vector_chunks = await _vector_candidates(db, workspace_id, embedding, candidate_limit)
    if mode == "vector":
        return vector_chunks[:top_k]
    lexical_chunks = await _lexical_candidates(db, workspace_id, question, candidate_limit)
    fused_chunks = reciprocal_rank_fusion(
        vector_chunks, lexical_chunks, settings.retrieval_rrf_k
    )[:candidate_limit]
    if mode == "hybrid":
        return fused_chunks[:top_k]
    if mode == "reranked":
        return await rerank_chunks(question, fused_chunks, top_k)
    raise ValueError(f"Unknown retrieval mode: {mode}")


async def run_evaluation(
    dataset_path: Path,
    workspace_id: uuid.UUID,
    modes: tuple[str, ...] = ("vector", "hybrid", "reranked"),
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, Any]:
    dataset_version, cases = load_dataset(dataset_path)
    report: dict[str, Any] = {
        "dataset_version": dataset_version,
        "workspace_id": str(workspace_id),
        "embedding_model": settings.gemini_embedding_model,
        "modes": {},
    }
    async with async_session_factory() as db:
        embeddings_by_case = {
            case.case_id: (await embed_texts([case.question]))[0] for case in cases
        }
        for mode in modes:
            per_case = []
            for case in cases:
                started = time.perf_counter()
                chunks = await _retrieve(
                    db,
                    workspace_id,
                    case.question,
                    embeddings_by_case[case.case_id],
                    mode,
                    max(k_values),
                )
                metrics = evaluate_case(case, chunks, k_values)
                metrics["latency_ms"] = int((time.perf_counter() - started) * 1000)
                metrics["returned_sources"] = [
                    {
                        "document": chunk.document_title,
                        "page": chunk.page_number,
                        "chunk_id": str(chunk.chunk_id),
                    }
                    for chunk in chunks
                ]
                per_case.append(metrics)
            report["modes"][mode] = {
                "aggregate": aggregate_results(per_case),
                "cases": per_case,
            }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--workspace-id", type=uuid.UUID, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", default=["vector", "hybrid", "reranked"])
    args = parser.parse_args()
    report = asyncio.run(run_evaluation(args.dataset, args.workspace_id, tuple(args.modes)))
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()