"""G10 two-worker queue soak. Synthetic engineering evidence, not real Windows user acceptance."""
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


def run(output: Path, count: int = 12, workers: int = 2, deadline_seconds: float = 180) -> dict:
    if not 6 <= count <= 80 or workers not in (1, 2):
        raise ValueError("Invalid workload")
    from reportlab.pdfgen.canvas import Canvas
    from docx import Document

    with tempfile.TemporaryDirectory(prefix="lk-g10-soak-") as temp:
        base = Path(temp)
        root = base / "data"
        service = IntakeService(root)
        imported, sources = [], []
        for i in range(count):
            token = f"MaviKoridor{i:03d}"
            if i % 3 == 0:
                src = base / f"example_{i}.pdf"
                page = Canvas(str(src))
                page.drawString(60, 760, f"{token} sentetik test belgesi")
                page.showPage()
                page.save()
            elif i % 3 == 1:
                src = base / f"example_{i}.docx"
                doc = Document()
                doc.add_paragraph(f"{token} Türkçe örnek belge")
                doc.save(src)
            else:
                src = base / f"example_{i}.txt"
                src.write_text(f"{token} Türkiye ı İ ğ ü ve kaynak denetimi\n", encoding="utf-8")
            before = hashlib.sha256(src.read_bytes()).hexdigest()
            result = service.import_document(src)
            imported.append((result, token))
            sources.append((src, before))

        runner = Runner(root, timeout_seconds=120, poll_interval=.03)
        job_ids = [j.id for j in runner.queue.list(limit=count + 1)]
        # Exercise explicit cancel and retry before worker execution.
        assert runner.queue.cancel_pending(job_ids[0])
        assert runner.queue.retry(job_ids[0])
        start = time.monotonic()
        runner.start(workers=workers)
        deadline = time.monotonic() + deadline_seconds
        try:
            while time.monotonic() < deadline:
                jobs = runner.queue.list(limit=count + 1)
                if len(jobs) == count and all(j.status not in ("PENDING", "RUNNING") for j in jobs):
                    break
                time.sleep(.08)
        finally:
            runner.stop()

        jobs = runner.queue.list(limit=count + 1)
        successful = sum(j.status == "COMPLETED" for j in jobs)
        search = SearchService(root)
        verified = 0
        for imported_result, token in imported:
            matches = [h for h in search.search(token, limit=10)
                       if h.document_id == imported_result.document_id]
            if matches and all(h.verified and search.source_passage(h.chunk_id) is not None for h in matches):
                verified += 1
        unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == sha for path, sha in sources)
        exactly_once = all(j.attempt == 1 and j.processed_units == j.total_units for j in jobs)
        status = "PASS" if successful == count and verified == count and unchanged and exactly_once else "FAIL"
        result = {
            "status": status, "synthetic": True, "os_validation": "AUTOMATED_CI_ONLY",
            "count": count, "workers": workers, "completed": successful,
            "source_verified": verified, "source_unchanged": unchanged,
            "exactly_once": exactly_once, "statuses": {
                state: sum(j.status == state for j in jobs) for state in sorted({j.status for j in jobs})
            },
            "elapsed_seconds": round(time.monotonic() - start, 3), "commercial_release": "HOLD",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if status != "PASS":
            raise AssertionError(result)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(run(args.output, count=args.count), ensure_ascii=False))
