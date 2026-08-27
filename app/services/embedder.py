import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class EmbeddingError(Exception):
    """Lỗi xảy ra khi gọi API Gemini để tạo embedding."""


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Tạo embedding cho danh sách các đoạn văn bản sử dụng Gemini API.

    Mỗi lượt gọi API giới hạn tối đa 100 phần tử để tránh quá tải payload.
    """
    if not texts:
        return []

    api_key = settings.gemini_api_key
    if not api_key:
        raise EmbeddingError("GEMINI_API_KEY is not configured in settings")

    # API endpoint cho batchEmbedContents
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_embedding_model}:batchEmbedContents?key={api_key}"
    )

    batch_size = 100
    all_embeddings: list[list[float]] = []

    async with httpx.AsyncClient() as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            requests = [
                {
                    "model": f"models/{settings.gemini_embedding_model}",
                    "content": {"parts": [{"text": text}]},
                }
                for text in batch
            ]

            try:
                response = await client.post(
                    url, json={"requests": requests}, timeout=30.0
                )
                if response.status_code != 200:
                    logger.error(
                        "gemini_embedding_api_failed",
                        status_code=response.status_code,
                        response_body=response.text,
                    )
                    raise EmbeddingError(
                        f"Gemini API returned status code {response.status_code}: {response.text}"
                    )

                data = response.json()
                embeddings_data = data.get("embeddings", [])
                if len(embeddings_data) != len(batch):
                    raise EmbeddingError(
                        "Mismatch in number of returned embeddings from Gemini API"
                    )

                for emb in embeddings_data:
                    all_embeddings.append(emb["values"])

            except Exception as e:
                if not isinstance(e, EmbeddingError):
                    logger.error("gemini_embedding_request_exception", error=str(e))
                    raise EmbeddingError(
                        f"Failed to communicate with Gemini API: {e!s}"
                    ) from e
                raise

    return all_embeddings
