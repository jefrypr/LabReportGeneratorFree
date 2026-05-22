# utils/pdf_processor.py
"""
Ekstraksi konten dari file PDF modul praktikum.
Mengambil bagian paling relevan: tujuan, dasar teori, dan informasi umum.
"""

import pdfplumber
import io
import re
from typing import Optional


def _clean_text(text: str) -> str:
    """Bersihkan teks dari karakter aneh dan spasi berlebih."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x20-\x7E\u00C0-\u024F\u0100-\u017F\n]', '', text)
    return text.strip()


def extract_pdf_content(pdf_file, max_chars: int = 3000) -> str:
    """
    Ekstrak konten penting dari PDF modul praktikum.
    Prioritas: halaman awal (tujuan + dasar teori biasanya di sini).

    Args:
        pdf_file: Streamlit UploadedFile object
        max_chars: Maksimum karakter yang diambil

    Returns:
        Teks yang diekstrak dan dibersihkan
    """
    try:
        pdf_file.seek(0)
        raw = pdf_file.read()
        text_parts = []

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            total_pages = len(pdf.pages)
            # Ambil max 12 halaman pertama (modul umumnya di sini)
            pages_to_read = min(total_pages, 12)

            for i in range(pages_to_read):
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    cleaned = _clean_text(page_text)
                    if cleaned:
                        text_parts.append(cleaned)

                if sum(len(p) for p in text_parts) >= max_chars:
                    break

        full_text = "\n".join(text_parts)

        # Coba ambil bagian tujuan dan dasar teori saja jika ada keyword
        keywords = ["tujuan", "dasar teori", "tinjauan pustaka", "latar belakang"]
        relevant_sections = []

        for keyword in keywords:
            idx = full_text.lower().find(keyword)
            if idx != -1:
                # Ambil 600 karakter setelah keyword
                section = full_text[idx : idx + 600]
                relevant_sections.append(section)

        if relevant_sections:
            # Gabungkan bagian relevan
            result = " [...] ".join(relevant_sections)
            return result[:max_chars]
        else:
            return full_text[:max_chars]

    except Exception:
        # Jika gagal baca PDF, kembalikan string kosong (tidak fatal)
        return ""
