import abc
import io

import structlog
from docx import Document as DocxDocument
from pypdf import PdfReader

logger = structlog.get_logger()


class UnsupportedMimeTypeError(Exception):
    """Mime type hoặc định dạng tệp không được hỗ trợ."""


class BaseParser(abc.ABC):
    @abc.abstractmethod
    def parse(self, content: bytes) -> list[tuple[str, int | None]]:
        """Phân tích nội dung tệp tin sang văn bản thô kèm số trang (nếu có).

        Trả về một danh sách các tuple: (nội dung văn bản, số trang).
        """


class TextParser(BaseParser):
    def parse(self, content: bytes) -> list[tuple[str, int | None]]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback sang latin-1 nếu utf-8 thất bại
            text = content.decode("latin-1")
        return [(text, 1)]


class MarkdownParser(BaseParser):
    def parse(self, content: bytes) -> list[tuple[str, int | None]]:
        # Đối với Markdown, ta coi như toàn bộ là 1 trang
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        return [(text, 1)]


class PDFParser(BaseParser):
    def parse(self, content: bytes) -> list[tuple[str, int | None]]:
        pages: list[tuple[str, int | None]] = []
        try:
            reader = PdfReader(io.BytesIO(content))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages.append((text, i + 1))
        except Exception as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise ValueError(f"Failed to parse PDF: {e!s}") from e
        return pages


class DocxParser(BaseParser):
    def parse(self, content: bytes) -> list[tuple[str, int | None]]:
        try:
            doc = DocxDocument(io.BytesIO(content))
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            text = "\n".join(paragraphs)
            return [(text, 1)]
        except Exception as e:
            logger.error("docx_parse_failed", error=str(e))
            raise ValueError(f"Failed to parse DOCX: {e!s}") from e


def get_parser(mime_type: str, filename: str) -> BaseParser:
    lower_name = filename.lower()

    if mime_type == "text/plain" or lower_name.endswith(".txt"):
        return TextParser()
    elif mime_type == "text/markdown" or lower_name.endswith((".md", ".markdown")):
        return MarkdownParser()
    elif mime_type == "application/pdf" or lower_name.endswith(".pdf"):
        return PDFParser()
    elif mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or lower_name.endswith((".docx", ".doc")):
        return DocxParser()
    else:
        raise UnsupportedMimeTypeError(
            f"Unsupported file format: {mime_type} ({filename})"
        )
