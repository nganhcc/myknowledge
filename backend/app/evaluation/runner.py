import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import aggregate_results, citation_metrics, evaluate_case
from app.services.chat import build_context, generate_answer
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


async def _judge_answer(
    question: str,
    ground_truth: str,
    answer: str,
    context: str,
) -> dict[str, Any]:
    """Ask Gemini for bounded correctness and context relevance scores."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for answer judging")
    prompt = (
        "Evaluate the candidate answer against the reference answer and supplied context. "
        "Return JSON only with numeric values from 0 to 1 for answer_correctness and "
        "context_relevance, plus a short explanation string. Do not use outside knowledge.\n\n"
        f"Question: {question}\nReference answer: {ground_truth}\n"
        f"Candidate answer: {answer}\nContext:\n{context}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_generation_model}:generateContent"
    )
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
            timeout=45.0,
        )
    if response.status_code != 200:
        raise RuntimeError(f"Judge API returned status {response.status_code}")
    try:
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        correctness = float(result["answer_correctness"])
        relevance = float(result["context_relevance"])
        explanation = str(result.get("explanation", ""))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Judge returned invalid JSON scores") from error
    if not 0.0 <= correctness <= 1.0 or not 0.0 <= relevance <= 1.0:
        raise RuntimeError("Judge scores must be between 0 and 1")
    return {
        "answer_correctness": correctness,
        "context_relevance": relevance,
        "explanation": explanation,
    }


async def run_e2e_evaluation(
    dataset_path: Path,
    workspace_id: uuid.UUID,
    modes: tuple[str, ...] = ("vector", "hybrid", "reranked"),
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, Any]:
    """Evaluate retrieval, generation, and citations without persisting chat state."""
    dataset_version, cases = load_dataset(dataset_path)
    report: dict[str, Any] = {
        "dataset_version": dataset_version,
        "workspace_id": str(workspace_id),
        "embedding_model": settings.gemini_embedding_model,
        "generation_model": settings.gemini_generation_model,
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
                context = build_context(chunks)
                answer, input_tokens, output_tokens = await generate_answer(
                    case.question, context
                )
                result = {
                    "case_id": case.case_id,
                    "answer": answer,
                    "ground_truth": case.ground_truth,
                    "answerable": case.answerable,
                    "citations": citation_metrics(
                        answer, chunks, case.expected_sources
                    ),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "returned_sources": [
                        {
                            "document": chunk.document_title,
                            "page": chunk.page_number,
                            "chunk_id": str(chunk.chunk_id),
                        }
                        for chunk in chunks
                    ],
                }
                if case.ground_truth:
                    result["judge"] = await _judge_answer(
                        case.question, case.ground_truth, answer, context
                    )
                per_case.append(result)
            report["modes"][mode] = {"cases": per_case}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--workspace-id", type=uuid.UUID, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", default=["vector", "hybrid", "reranked"])
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Generate answers and evaluate citations in addition to retrieval",
    )
    args = parser.parse_args()
    runner = run_e2e_evaluation if args.e2e else run_evaluation
    report = asyncio.run(runner(args.dataset, args.workspace_id, tuple(args.modes)))
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()