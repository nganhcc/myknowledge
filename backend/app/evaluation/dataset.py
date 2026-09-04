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
            sources = tuple(
                SourceReference(source["document"], source.get("page"))
                for source in data["expected_sources"]
            )
            cases.append(EvaluationCase(data["case_id"], data["question"], sources))
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid benchmark at line {line_number}: {error}") from error
    if not cases:
        raise ValueError("Benchmark does not contain any cases")
    return version, cases