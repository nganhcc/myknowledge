from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.session import async_session_factory
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.services.chunker import chunk_document
from app.services.document import process_document
from app.services.embedder import EmbeddingError, embed_texts
from app.services.parser import (
    DocxParser,
    MarkdownParser,
    PDFParser,
    TextParser,
    UnsupportedMimeTypeError,
    get_parser,
)


# 1. Test Parsers
def test_text_parser() -> None:
    parser = TextParser()
    res = parser.parse(b"hello world")
    assert len(res) == 1
    assert res[0][0] == "hello world"
    assert res[0][1] == 1


def test_markdown_parser() -> None:
    parser = MarkdownParser()
    res = parser.parse(b"# Title\ncontent")
    assert len(res) == 1
    assert res[0][0] == "# Title\ncontent"
    assert res[0][1] == 1


def test_pdf_parser() -> None:
    with patch("app.services.parser.PdfReader") as MockReader:
        mock_reader = MockReader.return_value
        page1 = MagicMock()
        page1.extract_text.return_value = "page 1 text"
        page2 = MagicMock()
        page2.extract_text.return_value = "page 2 text"
        mock_reader.pages = [page1, page2]

        parser = PDFParser()
        res = parser.parse(b"dummy pdf bytes")
        assert len(res) == 2
        assert res[0] == ("page 1 text", 1)
        assert res[1] == ("page 2 text", 2)


def test_docx_parser() -> None:
    with patch("app.services.parser.DocxDocument") as MockDocx:
        mock_doc = MockDocx.return_value
        p1 = MagicMock(text="para 1")
        p2 = MagicMock(text="para 2")
        mock_doc.paragraphs = [p1, p2]

        parser = DocxParser()
        res = parser.parse(b"dummy docx bytes")
        assert len(res) == 1
        assert res[0][0] == "para 1\npara 2"


def test_get_parser() -> None:
    assert isinstance(get_parser("text/plain", "file.txt"), TextParser)
    assert isinstance(get_parser("text/markdown", "file.md"), MarkdownParser)
    assert isinstance(get_parser("application/pdf", "file.pdf"), PDFParser)
    assert isinstance(
        get_parser(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file.docx",
        ),
        DocxParser,
    )

    with pytest.raises(UnsupportedMimeTypeError):
        get_parser("image/png", "file.png")


# 2. Test Chunker
def test_chunker() -> None:
    pages: list[tuple[str, int | None]] = [("word1 word2 word3 word4", 1), ("word5 word6", 2)]
    # chunk_size=3, overlap=1
    chunks = chunk_document(pages, chunk_size=3, overlap=1)
    
    assert len(chunks) == 3
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == "word1 word2 word3"
    assert chunks[0].page_number == 1

    assert chunks[1].chunk_index == 1
    assert chunks[1].content == "word3 word4 word5"
    assert chunks[1].page_number == 1  # word3 thuộc trang 1

    assert chunks[2].chunk_index == 2
    assert chunks[2].content == "word5 word6"
    assert chunks[2].page_number == 2  # word5 thuộc trang 2


# 3. Test Embedder (Gemini API Call)
@pytest.mark.asyncio
async def test_embed_texts_success() -> None:
    with patch("app.core.config.settings.gemini_api_key", "test-key"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [{"values": [0.1] * 768}, {"values": [0.2] * 768}]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            res = await embed_texts(["text1", "text2"])
            assert len(res) == 2
            assert res[0] == [0.1] * 768
            assert res[1] == [0.2] * 768

            args, kwargs = mock_post.call_args
            assert "text-embedding-004" in args[0]
            assert "key=test-key" in args[0]
            assert len(kwargs["json"]["requests"]) == 2


@pytest.mark.asyncio
async def test_embed_texts_api_error() -> None:
    with patch("app.core.config.settings.gemini_api_key", "test-key"):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid API Key"

        with (
            patch("httpx.AsyncClient.post", return_value=mock_response),
            pytest.raises(EmbeddingError),
        ):
            await embed_texts(["text1"])


# 4. Test Orchestrator process_document
@pytest.mark.asyncio
async def test_process_document_pipeline() -> None:
    async with async_session_factory() as db:
        from app.models.user import User
        from app.models.workspace import Workspace

        user = User(
            email="test_pipe@example.com",
            password_hash="hash",
            name="Pipe User",
        )
        db.add(user)
        await db.flush()

        ws = Workspace(name="Pipe Workspace", created_by=user.id)
        db.add(ws)
        await db.flush()

        doc = Document(
            workspace_id=ws.id,
            title="test.txt",
            filename="test.txt",
            mime_type="text/plain",
            size=11,
            status=DocumentStatus.PENDING,
            storage_key="/tmp/test.txt",
            content_hash="somehash",
            retry_count=0,
            created_by=user.id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Mock storage read_file
        mock_storage = MagicMock()
        mock_storage.read_file = AsyncMock(
            return_value=b"hello word chunking test"
        )

        # Mock embedder
        mock_embeddings = [[0.5] * 768, [0.6] * 768]
        with patch(
            "app.services.embedder.embed_texts",
            AsyncMock(return_value=mock_embeddings),
        ):
            await process_document(db, mock_storage, doc.id)

            await db.refresh(doc)
            assert doc.status == DocumentStatus.READY

            from sqlalchemy import select

            result = await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
            )
            chunks = result.scalars().all()
            assert len(chunks) > 0
            assert chunks[0].content is not None
            assert chunks[0].embedding == [0.5] * 768


@pytest.mark.asyncio
async def test_process_document_retry_increments_count() -> None:
    async with async_session_factory() as db:
        from app.models.user import User
        from app.models.workspace import Workspace

        user = User(
            email="test_retry@example.com",
            password_hash="hash",
            name="Retry User",
        )
        db.add(user)
        await db.flush()

        ws = Workspace(name="Retry Workspace", created_by=user.id)
        db.add(ws)
        await db.flush()

        doc = Document(
            workspace_id=ws.id,
            title="test_retry.txt",
            filename="test_retry.txt",
            mime_type="text/plain",
            size=11,
            status=DocumentStatus.PENDING,
            storage_key="/tmp/test_retry.txt",
            content_hash="retryhash",
            retry_count=0,
            created_by=user.id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        mock_storage = MagicMock()
        mock_storage.read_file = AsyncMock(
            return_value=b"hello retry text"
        )

        # Mock embed_texts to raise an exception
        with patch(
            "app.services.embedder.embed_texts",
            AsyncMock(side_effect=Exception("Embedding API error")),
        ):
            await process_document(db, mock_storage, doc.id)

            await db.refresh(doc)
            assert doc.status == DocumentStatus.PENDING
            assert doc.retry_count == 1


@pytest.mark.asyncio
async def test_process_document_permanently_fails_after_max_retries() -> None:
    async with async_session_factory() as db:
        from app.core.config import settings
        from app.models.user import User
        from app.models.workspace import Workspace

        user = User(
            email="test_fail@example.com",
            password_hash="hash",
            name="Fail User",
        )
        db.add(user)
        await db.flush()

        ws = Workspace(name="Fail Workspace", created_by=user.id)
        db.add(ws)
        await db.flush()

        doc = Document(
            workspace_id=ws.id,
            title="test_fail.txt",
            filename="test_fail.txt",
            mime_type="text/plain",
            size=11,
            status=DocumentStatus.PENDING,
            storage_key="/tmp/test_fail.txt",
            content_hash="failhash",
            retry_count=settings.max_document_retries - 1,
            created_by=user.id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        mock_storage = MagicMock()
        mock_storage.read_file = AsyncMock(
            return_value=b"hello fail text"
        )

        # Mock embed_texts to raise an exception
        with patch(
            "app.services.embedder.embed_texts",
            AsyncMock(side_effect=Exception("Embedding API error")),
        ):
            await process_document(db, mock_storage, doc.id)

            await db.refresh(doc)
            assert doc.status == DocumentStatus.FAILED
            assert doc.retry_count == settings.max_document_retries
