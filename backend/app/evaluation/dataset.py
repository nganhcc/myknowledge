import json
from pathlib import Path

from app.evaluation.metrics import EvaluationCase, SourceReference


def load_dataset(path: Path) -> tuple[str, list[EvaluationCase]]:
    """Load a versioned JSONL benchmark."""
    cases: list[EvaluationCase] = []
    version = "1"
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("type") == "metadata":
                version = str(data.get("version", version))
                continue
            if not isinstance(data.get("case_id"), str):
                raise TypeError("case_id must be a string")
            if not isinstance(data.get("question"), str):
                raise TypeError("question must be a string")
            sources = tuple(
                SourceReference(source["document"], source.get("page"))
                for source in data["expected_sources"]
            )
            ground_truth = data.get("ground_truth")
            if ground_truth is not None and not isinstance(ground_truth, str):
                raise ValueError("ground_truth must be a string")
            answerable = data.get("answerable", True)
            if not isinstance(answerable, bool):
                raise TypeError("answerable must be a boolean")
            cases.append(
                EvaluationCase(
                    data["case_id"],
                    data["question"],
                    sources,
                    ground_truth,
                    answerable,
                )
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid benchmark at line {line_number}: {error}") from error
    if not cases:
        raise ValueError("Benchmark does not contain any cases")
    return version, cases