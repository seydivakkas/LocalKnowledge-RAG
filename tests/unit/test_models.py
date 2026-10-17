import unittest
from dataclasses import FrozenInstanceError
from localknowledge.domain.models import (SourceKind, DocumentRef, VersionRef, PageRef, SpanRef, SearchHit, CitationRef, require_sha256)

SHA = "a" * 64


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.pdf = VersionRef(DocumentRef("doc-pdf", SourceKind.PDF, "belge.pdf"), SHA, 1)
        self.txt = VersionRef(DocumentRef("doc-txt", SourceKind.TXT, "belge.txt"), SHA, 1)
        self.docx = VersionRef(DocumentRef("doc-word", SourceKind.DOCX, "belge.docx"), SHA, 2)

    def test_pdf_page_one_indexed(self):
        self.assertEqual(PageRef(self.pdf, 1).page_number, 1)
        for bad in (0, -2, 1.0, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError): PageRef(self.pdf, bad)

    def test_never_fabricate_text_pages(self):
        for source in (self.txt, self.docx):
            with self.assertRaises(ValueError): PageRef(source, 1)

    def test_spans_only_text(self):
        self.assertEqual(SpanRef(self.txt, 4, 18).start, 4)
        self.assertEqual(SpanRef(self.docx, 0, 9, 2).paragraph_index, 2)
        with self.assertRaises(ValueError): SpanRef(self.pdf, 1, 3)
        for start, end in ((1, 1), (4, 2), (-1, 4), (True, 4)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError): SpanRef(self.txt, start, end)

    def test_sha_validation(self):
        self.assertEqual(require_sha256(SHA), SHA)
        for invalid in ("bad", "B"*64, "_"*64, "a"*63):
            with self.subTest(sha=invalid), self.assertRaises(ValueError): VersionRef(self.pdf.document, invalid, 1)

    def test_frozen_references(self):
        with self.assertRaises(FrozenInstanceError): self.pdf.revision = 2

    def test_search_score_not_confidence(self):
        hit = SearchHit(PageRef(self.pdf, 2), "Türkçe kaynak pasaj", 1, -3.12)
        self.assertAlmostEqual(hit.bm25_score, -3.12)
        for bad in (float('inf'), float('nan'), True):
            with self.assertRaises(ValueError): SearchHit(PageRef(self.pdf, 1), "kanit", 1, bad)

    def test_citation_does_not_verify_itself(self):
        citation = CitationRef(PageRef(self.pdf, 1), "Belgede bulunan metin")
        self.assertFalse(hasattr(citation, "verified"))

    def test_bad_source_types(self):
        with self.assertRaises(ValueError): DocumentRef("abc", "PDF", "x.pdf")
        with self.assertRaises(ValueError): VersionRef(self.pdf.document, SHA, 0)
