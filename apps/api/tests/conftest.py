import pymupdf
import pytest

from app.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store.clear()
    yield
    store.clear()


def make_pdf(pages: list[str], **save_kwargs) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = doc.tobytes(**save_kwargs)
    doc.close()
    return data
