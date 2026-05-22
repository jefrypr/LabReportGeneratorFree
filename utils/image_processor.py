# utils/image_processor.py
"""
Memproses foto percobaan dan hasil data menggunakan Google Gemini 1.5 Flash.
Menghasilkan deskripsi teks yang digunakan sebagai konteks untuk DeepSeek.
"""

import google.generativeai as genai
import PIL.Image
import io
from typing import List, Optional


def _load_image(file_obj) -> Optional[PIL.Image.Image]:
    """Load image dari Streamlit UploadedFile ke PIL Image."""
    try:
        file_obj.seek(0)
        img = PIL.Image.open(io.BytesIO(file_obj.read()))
        # Resize jika terlalu besar untuk hemat token
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, PIL.Image.LANCZOS)
        return img.convert("RGB")
    except Exception:
        return None


def process_images(
    percobaan_files: List,
    hasil_data_files: List,
    api_key: str,
) -> tuple[str, str]:
    """
    Analisis foto percobaan & hasil data dengan Gemini 1.5 Flash.

    Returns:
        percobaan_desc: Deskripsi setup/proses percobaan
        hasil_data_desc: Deskripsi data kuantitatif dan pola hasil
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    percobaan_desc = ""
    hasil_data_desc = ""

    # --- Analisis foto percobaan ---
    if percobaan_files:
        images = []
        for f in percobaan_files:
            img = _load_image(f)
            if img:
                images.append(img)

        if images:
            prompt = (
                "Kamu adalah asisten teknis praktikum laboratorium. "
                "Deskripsikan secara singkat dan teknis apa yang terlihat pada foto percobaan berikut. "
                "Fokus pada: peralatan yang digunakan, konfigurasi/setup percobaan, dan kondisi yang terlihat. "
                "Jangan menebak-nebak. Tulis dalam Bahasa Indonesia. Maksimal 200 kata."
            )
            response = model.generate_content([prompt] + images)
            percobaan_desc = response.text.strip()

    # --- Analisis foto hasil data ---
    if hasil_data_files:
        images = []
        for f in hasil_data_files:
            img = _load_image(f)
            if img:
                images.append(img)

        if images:
            prompt = (
                "Kamu adalah asisten teknis praktikum laboratorium. "
                "Baca dan deskripsikan secara teknis dan numerik data yang terlihat pada gambar berikut. "
                "Sebutkan: semua nilai/angka yang terukur, judul tabel/grafik jika ada, "
                "satuan pengukuran, dan tren atau pola data yang terlihat. "
                "Jika ada tabel, sebutkan kolom dan beberapa nilai sampelnya. "
                "Jika ada grafik, deskripsikan bentuk kurva dan nilai-nilai pentingnya. "
                "Tulis dalam Bahasa Indonesia. Maksimal 350 kata."
            )
            response = model.generate_content([prompt] + images)
            hasil_data_desc = response.text.strip()

    return percobaan_desc, hasil_data_desc
