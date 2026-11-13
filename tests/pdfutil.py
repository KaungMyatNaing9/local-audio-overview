"""Build a tiny text PDF for ingestion tests. No third-party writer required."""

from __future__ import annotations


def build_pdf(pages: list[str]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    for text in pages:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 18 Tf 72 720 Td ({safe}) Tj ET".encode()
        contents_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_id = add(
            (
                "<< /Type /Page /Parent PAGES 0 R /MediaBox [0 0 612 792] "
                f"/Contents {contents_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode()
        )
        page_ids.append(page_id)
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
    objects = [body.replace(b"PAGES 0 R", f"{pages_id} 0 R".encode()) for body in objects]
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    chunks: list[bytes] = []
    offsets = [0]
    cursor = len(header)
    for number, body in enumerate(objects, start=1):
        chunk = f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
        offsets.append(cursor)
        chunks.append(chunk)
        cursor += len(chunk)
    size = len(objects) + 1
    xref = [f"xref\n0 {size}\n".encode(), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    trailer = (f"trailer\n<< /Size {size} /Root {catalog_id} 0 R >>\nstartxref\n{cursor}\n%%EOF\n").encode()
    return header + b"".join(chunks) + b"".join(xref) + trailer
