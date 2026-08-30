from dataclasses import dataclass, field


@dataclass
class ChunkData:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    metadata: dict = field(default_factory=dict)


def chunk_document(
    parsed_pages: list[tuple[str, int | None]],
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[ChunkData]:
    """Chia nhỏ văn bản từ các trang thành các chunk dựa trên từ (words).

    Mỗi chunk sẽ giữ lại thông tin số trang (page_number) của từ đầu tiên trong chunk.
    """
    all_words: list[tuple[str, int | None]] = []

    for text, page_num in parsed_pages:
        # Tách từ, giữ nguyên các ký tự đặc biệt dính liền
        words = text.split()
        for w in words:
            all_words.append((w, page_num))

    if not all_words:
        return []

    chunks = []
    chunk_idx = 0
    i = 0
    total_words = len(all_words)

    while i < total_words:
        window = all_words[i : i + chunk_size]

        # Ghép các từ lại thành chuỗi
        chunk_content = " ".join([w[0] for w in window])

        # Page number được xác định bởi từ đầu tiên của window
        page_num = window[0][1]
        token_count = len(window)

        chunks.append(
            ChunkData(
                chunk_index=chunk_idx,
                content=chunk_content,
                token_count=token_count,
                page_number=page_num,
                metadata={},
            )
        )

        chunk_idx += 1

        # Tính bước nhảy
        step = max(1, chunk_size - overlap)

        # Nếu window đã phủ hết đến cuối tài liệu thì dừng
        if i + chunk_size >= total_words:
            break

        i += step

    return chunks
