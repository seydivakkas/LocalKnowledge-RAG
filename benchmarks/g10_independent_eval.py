"""G10 independent retrieval evaluator for locally supplied rights-cleared PDF/DOCX/TXT.

Gold labels are supplied before retrieval. NEVER upload real customer data to CI/GitHub.
Any result is MEASURED_NOT_ACCEPTED until independent provenance review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.search.service import SearchService


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_inputs(corpus: Path, manifest: Path, judgments: Path):
    base = corpus.resolve(strict=True)
    items = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Nonempty manifest list required")
    known, paths, digests = set(), [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"key", "path", "sha256", "rights"}:
            raise ValueError("Invalid manifest fields")
        key = item["key"]
        rel = Path(item["path"])
        if not isinstance(key, str) or not key or key in known:
            raise ValueError("Duplicate/invalid document key")
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError("Unsafe corpus path")
        if not isinstance(item["rights"], str) or not item["rights"].strip():
            raise ValueError("Rights declaration required")
        path = (base / rel).resolve(strict=True)
        if not path.is_relative_to(base) or path.suffix.lower() not in (".pdf", ".docx", ".txt"):
            raise ValueError("Document outside corpus or unsupported")
        digest = sha(path)
        if digest != item["sha256"] or digest in digests:
            raise ValueError("Hash mismatch or duplicate content")
        known.add(key)
        digests.add(digest)
        paths.append((key, path))
    labels, seen = [], set()
    for line in judgments.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != {"id", "query", "expected", "relevant"}:
            raise ValueError("Invalid judgment fields")
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in seen:
            raise ValueError("Duplicate judgment")
        seen.add(row["id"])
        if not isinstance(row["query"], str) or not row["query"].strip():
            raise ValueError("Empty query")
        if row["expected"] not in ("ANSWERABLE", "NO_EVIDENCE"):
            raise ValueError("Expected ANSWERABLE or NO_EVIDENCE")
        related = row["relevant"]
        if not isinstance(related, list) or len(set(related)) != len(related) or not set(related).issubset(known):
            raise ValueError("Invalid relevant doc keys")
        if bool(related) != (row["expected"] == "ANSWERABLE"):
            raise ValueError("Contradictory gold labels")
        labels.append(row)
    if not labels:
        raise ValueError("No independent judgments")
    return paths, labels


def score(labels, predictions, citations):
    positives = negatives = recall = false_positives = citation_total = citation_correct = 0
    reciprocal = 0.0
    for j, ids, checks in zip(labels, predictions, citations):
        if len(ids) != len(checks):
            raise ValueError("Citation count mismatch")
        citation_total += len(checks)
        citation_correct += sum(bool(check) for check in checks)
        if j["expected"] == "NO_EVIDENCE":
            negatives += 1
            false_positives += bool(ids)
        else:
            positives += 1
            rank = next((i for i, key in enumerate(ids, 1) if key in j["relevant"]), None)
            recall += bool(rank and rank <= 5)
            reciprocal += 1 / rank if rank and rank <= 10 else 0
    return {
        "answerable": positives, "negative": negatives,
        "recall_at_5": round(recall / positives, 4) if positives else None,
        "mrr_at_10": round(reciprocal / positives, 4) if positives else None,
        "negative_false_positive_rate": round(false_positives / negatives, 4) if negatives else None,
        "citation_exact_rate": round(citation_correct / citation_total, 4) if citation_total else None,
        "citations_verified": citation_correct, "citations_returned": citation_total,
    }


def evaluate(corpus: Path, manifest: Path, judgments: Path, output: Path):
    files, labels = read_inputs(corpus, manifest, judgments)
    with tempfile.TemporaryDirectory(prefix="lk-g10-independent-") as td:
        root = Path(td) / "data"
        intake = IntakeService(root)
        keys = {}
        for key, path in files:
            imported = intake.import_document(path)
            keys[imported.document_id] = key
        runner = Runner(root, poll_interval=.03)
        runner.start(workers=2)
        until = time.monotonic() + max(90, 15 * len(files))
        try:
            while time.monotonic() < until:
                jobs = runner.queue.list(limit=max(150, len(files) + 1))
                if len(jobs) == len(files) and all(j.status not in ("PENDING", "RUNNING") for j in jobs):
                    break
                time.sleep(.08)
        finally:
            runner.stop()
        jobs = runner.queue.list(limit=max(150, len(files) + 1))
        if len(jobs) != len(files) or any(j.status != "COMPLETED" for j in jobs):
            raise RuntimeError("Extraction incomplete: NO-GO")
        search = SearchService(root)
        predictions, citations, cases = [], [], []
        for row in labels:
            # Invalid FTS query is a dataset error; never silently drop an evaluation question.
            hits = search.search(row["query"], limit=10)
            found, verified = [], []
            for hit in hits:
                found.append(keys.get(hit.document_id, "UNEXPECTED"))
                linked = search.source_passage(hit.chunk_id)
                verified.append(bool(linked and linked[0].sha256 == hit.sha256 and
                                     linked[1][linked[2]:linked[3]] == hit.exact_quote))
            predictions.append(found)
            citations.append(verified)
            cases.append({"id": row["id"], "expected": row["expected"], "hits": found,
                          "verified": verified})
        report = {
            "status": "MEASURED_NOT_ACCEPTED",
            "dataset": "DECLARED_RIGHTS_NOT_INDEPENDENTLY_AUDITED",
            "documents": len(files), "judgments": len(labels),
            "manifest_sha256": sha(manifest), "judgments_sha256": sha(judgments),
            "metrics": score(labels, predictions, citations), "cases": cases,
            "real_corpus_acceptance": False, "commercial_release": "HOLD",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(evaluate(a.corpus, a.manifest, a.judgments, a.output)["metrics"], ensure_ascii=False))
