# utils/text_generator.py
"""
Generator teks analisis, kesimpulan, dan langkah kerja via OpenRouter API.

Model assignment:
  - nvidia/nemotron-super-49b-v1:free  → generate_analysis (tugas berat: analisis + kesimpulan)
  - cognitivecomputations/dolphin3.0-mistral-24b:free  → generate_langkah_kerja & adjust_content

OpenRouter menggunakan endpoint OpenAI-compatible:
  Base URL : https://openrouter.ai/api/v1
  Auth     : Bearer <OPENROUTER_API_KEY>
"""

import random
from openai import OpenAI
from typing import Generator

# ─── Model Constants ─────────────────────────────────────────────────────────
# Ganti nilai di sini jika model ID berubah di OpenRouter
MODEL_ANALYSIS  = "nvidia/nemotron-3-super-49b:free"          # tugas berat: analisis & kesimpulan
MODEL_HELPER    = "openrouter/owl-alpha"       # tugas ringan: langkah kerja & edit

# MODEL yang diinginkan user (tetap tersedia sebagai alternatif):
# MODEL_ANALYSIS_ALT = "nvidia/nemotron-3-super-120b-a12b:free"
# MODEL_HELPER_ALT   = "openrouter/owl-alpha"
# Cek ketersediaan terkini di: https://openrouter.ai/models?q=free

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ─── System Prompt Global ────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah asisten akademik untuk penulisan laporan praktikum laboratorium.

ATURAN WAJIB PENULISAN:
1. Gaya bahasa: formal akademik yang ringan, mudah dipahami, dan tidak terkesan seperti tulisan AI
2. Gunakan kata "praktikan" — DILARANG menggunakan: saya, kami, aku, kita, penulis
3. Istilah asing/teknis yang lebih dikenal dalam bahasa asing: tulis dalam bahasa asing dan cetak miring (italic) dengan tanda _kata_
4. KATA YANG DILARANG KERAS (jangan gunakan dalam bentuk apapun): anomali, menginvestigasi, fundamental, berfokus, praktis, presisi, menegaskan, teoretis
5. Jangan gunakan kalimat puitis, metafora berlebihan, atau ekspresi emosional
6. Selalu gunakan kata "praktikum" — DILARANG: penelitian, eksperimen, percobaan
7. Konteks selalu di laboratorium
8. Gaya bahasa seperti pada modul akademik, bukan artikel blog atau karya sastra
9. Jangan gunakan kata "komprehensif", "holistik", "esensial", "krusial", "signifikan" secara berlebihan"""


# ─── Prompt Builders ─────────────────────────────────────────────────────────

def _build_analysis_prompt(data: dict, seed: int) -> str:
    modul_snippet = ""
    if data.get("modul_info"):
        modul_snippet = f"\nRingkasan Modul: {data['modul_info'][:700]}"

    percobaan_line = ""
    if data.get("percobaan_info"):
        percobaan_line = f"\nDeskripsi Percobaan (dari foto): {data['percobaan_info']}"

    hasil_data_line = ""
    if data.get("hasil_data_info"):
        hasil_data_line = f"\nData Hasil Pengukuran (dari foto): {data['hasil_data_info']}"

    konteks_line = ""
    if data.get("konteks_tambahan"):
        konteks_line = f"\nKonteks Tambahan: {data['konteks_tambahan']}"

    refs_raw = data.get("daftar_pustaka", "").strip().split("\n")
    refs_formatted = []
    for i, ref in enumerate(refs_raw, 1):
        ref = ref.strip()
        if ref:
            cleaned = ref.lstrip("0123456789.-) ").strip()
            refs_formatted.append(f"[{i}] {cleaned}")
    refs_text = "\n".join(refs_formatted) if refs_formatted else "tidak ada"

    return f"""[ID-VARIASI: {seed}] — Penting: Gunakan frasa, struktur kalimat, dan urutan pembahasan yang BERBEDA dari versi sebelumnya. Hindari pengulangan pola kalimat.

===KONTEKS PRAKTIKUM===
Mata Praktikum: {data['mata_praktikum']}
Judul Modul: {data['judul']}{modul_snippet}{percobaan_line}{hasil_data_line}{konteks_line}

===DAFTAR PUSTAKA (cantumkan citasi [1], [2], dst. ke dalam teks analisis)===
{refs_text}

===TUGAS===

Buat output berikut dengan FORMAT PERSIS seperti di bawah:

**ANALISIS DAN PEMBAHASAN**
[Tulis analisis di sini]

**KESIMPULAN**
1. [poin 1]
2. [poin 2]
3. [poin 3]

---

KETENTUAN ANALISIS DAN PEMBAHASAN:
• Minimal 1000 kata, format paragraf naratif (BUKAN poin/bullet/numbering)
• Analisis mendalam terhadap hasil data yang diperoleh
• Bahas hubungan sebab-akibat dari hasil pengamatan
• Kaitkan hasil dengan teori dasar yang relevan
• Jelaskan semua variabel yang berperan (variabel bebas, terikat, dan kontrol)
• Bahas signifikansi hasil yang diperoleh
• Cantumkan citasi referensi [1], [2], dst. secara alami dalam kalimat
• JANGAN membahas langkah-langkah percobaan
• Jangan gunakan rumus matematika langsung; bahas secara naratif (hubungan, sebab-akibat, pengaruh)

KETENTUAN KESIMPULAN:
• Tepat 3 poin saja
• Setiap poin: maksimal 1 kalimat yang singkat, padat, dan berisi sebab-akibat
• Setiap poin harus memuat temuan penting yang berbeda
• Hindari pengulangan informasi antar poin
• JANGAN gunakan frasa seperti "berhasil memvalidasi", "terbukti sesuai teori", atau sejenisnya"""


def _build_langkah_kerja_prompt(context: dict) -> str:
    percobaan_hint = ""
    if context.get("percobaan_info"):
        percobaan_hint = f"\nDeskripsi percobaan: {context['percobaan_info'][:300]}"

    modul_hint = ""
    if context.get("modul_info"):
        modul_hint = f"\nCuplikan modul: {context['modul_info'][:300]}"

    return f"""Buat langkah kerja untuk praktikum berikut:
Mata Praktikum: {context['mata_praktikum']}
Judul: {context['judul']}{percobaan_hint}{modul_hint}

KETENTUAN LANGKAH KERJA:
• Format: penomoran (1. 2. 3. dst.)
• Setiap nomor: tepat 1 kalimat, singkat dan padat
• Gunakan kata kerja aktif (ambil, ukur, catat, hubungkan, dll.)
• Hanya langkah operasional, bukan teori
• Maksimal 15 langkah
• Jangan ada sub-poin di dalam satu nomor"""


def _build_adjust_prompt(current_content: str, instruction: str, section_name: str) -> str:
    return f"""Berikut adalah konten {section_name} yang perlu disesuaikan:

---KONTEN SAAT INI---
{current_content}
---AKHIR KONTEN---

Instruksi perubahan dari pengguna:
{instruction}

Tulis ulang konten tersebut sesuai instruksi. Pertahankan bagian yang tidak perlu diubah. Jangan tambahkan penjelasan sebelum atau sesudah konten."""


# ─── Client Factory ──────────────────────────────────────────────────────────

def _get_client(api_key: str) -> OpenAI:
    """Buat OpenAI client yang mengarah ke OpenRouter."""
    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://lab-report-generator.streamlit.app",
            "X-Title": "Lab Report Generator",
        },
    )


# ─── API Functions ────────────────────────────────────────────────────────────

def generate_analysis(data: dict, api_key: str) -> Generator[str, None, None]:
    """
    Generate analisis dan kesimpulan via OpenRouter — model Nemotron (streaming).
    Seed acak menjamin frasa selalu berbeda tiap generate.
    """
    client = _get_client(api_key)
    seed = random.randint(1000, 99999)
    prompt = _build_analysis_prompt(data, seed)

    stream = client.chat.completions.create(
        model=MODEL_ANALYSIS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=1.0,
        max_tokens=3500,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def generate_langkah_kerja(context: dict, api_key: str) -> Generator[str, None, None]:
    """Generate langkah kerja via OpenRouter — model helper (streaming)."""
    client = _get_client(api_key)
    prompt = _build_langkah_kerja_prompt(context)

    stream = client.chat.completions.create(
        model=MODEL_HELPER,
        messages=[
            {
                "role": "system",
                "content": (
                    "Kamu adalah asisten laporan praktikum. "
                    "Buat langkah kerja yang singkat, padat, jelas, dan operasional. "
                    "Satu kalimat per nomor."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=700,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def adjust_content(
    current_content: str,
    instruction: str,
    section_name: str,
    api_key: str,
) -> Generator[str, None, None]:
    """Edit konten yang sudah ada via OpenRouter — model helper (streaming)."""
    client = _get_client(api_key)
    prompt = _build_adjust_prompt(current_content, instruction, section_name)

    stream = client.chat.completions.create(
        model=MODEL_HELPER,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.85,
        max_tokens=3500,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
