"""G05 services: G04 local library plus transactional FTS5 search."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from .config import data_dir
from .documents.repository import DocumentRepository, LibraryDocument
from .ingest.service import IntakeService
from .jobs.queue import JobQueue
from .jobs.runner import Runner
from .search.service import SearchService
from .storage.backup import BackupService
from .viewer.service import SourceViewerService


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    available: bool
    registered_documents: int | None = None
    stored_versions: int | None = None
    pending_index: int | None = None
    indexed_documents: int | None = None
    indexed_chunks: int | None = None
    saved_searches: int | None = None
    active_jobs: int | None = None
    last_documents: tuple[LibraryDocument, ...] = ()


class DashboardService:
    def __init__(self, repository: DocumentRepository | None = None,search: SearchService | None = None):
        self.repository = repository
        self.search = search

    def summary(self) -> DashboardSnapshot:
        if self.repository is None:
            return DashboardSnapshot(False)
        s = self.repository.stats()
        recent = self.repository.list_documents(limit=5)
        index = self.search.stats() if self.search else {'indexed_documents':0,'indexed_chunks':0}
        return DashboardSnapshot(True,s.registered_documents,s.stored_versions,s.pending_index,
                                 index['indexed_documents'],index['indexed_chunks'],None,None,recent)


class AppServices:
    def __init__(self, dashboard: DashboardService | None = None, root: Path | str | None = None):
        self.intake = IntakeService(root)
        self.repository = self.intake.repository
        self.search = SearchService(self.intake.root)
        self.viewer = SourceViewerService(self.intake.root,self.search)
        self.dashboard = dashboard if dashboard is not None else DashboardService(self.repository,self.search)
        self.jobs = JobQueue(self.intake.db_path)
        self.runner = Runner(self.intake.root)
        self.backup = BackupService(self.intake.root)
