# app.py — Lab Report Generator
# Streamlit Cloud Deployment | DeepSeek V3 + Google Gemini 1.5 Flash

import streamlit as st
import time
import re

from utils.image_processor import process_images
from utils.pdf_processor import extract_pdf_content
from utils.text_generator import generate_analysis, generate_langkah_kerja, adjust_content
from utils.export_handler import export_to_docx, export_to_html


# ─── Page Config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Lab Report Generator",
    page_icon="🔬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Hide Streamlit default elements */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Header */
.app-header {
    text-align: center;
    padding: 1.2rem 0 0.5rem 0;
}
.app-header h1 { font-size: 1.9rem; font-weight: 700; margin-bottom: 0.2rem; }
.app-header p { color: #666; font-size: 0.95rem; }

/* Section labels */
.section-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}

/* Result content box */
.result-content {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    line-height: 1.85;
    font-size: 0.95rem;
    max-height: 500px;
    overflow-y: auto;
}

/* Word count badge */
.word-count {
    font-size: 0.75rem;
    color: #888;
    text-align: right;
    margin-top: 4px;
}

/* Action buttons area */
.action-area {
    background: #f0f4ff;
    border-radius: 10px;
    padding: 1rem;
    margin-top: 1rem;
}

/* Divider label */
.divider-label {
    text-align: center;
    color: #aaa;
    font-size: 0.8rem;
    margin: 0.5rem 0;
}

/* Info chips */
.chip {
    display: inline-block;
    background: #e8f0fe;
    color: #1a56db;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.78rem;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ──────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "step": "input",           # input | processing | results
        "results": {},             # analysis, conclusion, langkah_kerja
        "input_data": {},          # form data
        "analysis_context": {},    # processed context for LLM
        "show_langkah_form": False,
        "show_edit_form": False,
        "edit_target": "Analisis dan Pembahasan",
        "regen_count": 0,          # berapa kali di-regenerate
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Helper: API Keys ────────────────────────────────────────────────────────

def _get_keys() -> tuple[str | None, str | None]:
    try:
        return st.secrets["GOOGLE_API_KEY"], st.secrets["OPENROUTER_API_KEY"]
    except Exception:
        return None, None


# ─── Helper: Parse Output ────────────────────────────────────────────────────

def _parse_output(text: str) -> tuple[str, str]:
    """
    Pisahkan ANALISIS DAN PEMBAHASAN dari KESIMPULAN.
    Robust terhadap variasi format dari LLM.
    """
    # Normalisasi marker
    normalized = text
    for pattern in [
        r'\*\*ANALISIS DAN PEMBAHASAN\*\*',
        r'## ANALISIS DAN PEMBAHASAN',
        r'# ANALISIS DAN PEMBAHASAN',
        r'ANALISIS DAN PEMBAHASAN\n',
    ]:
        normalized = re.sub(pattern, '<<<ANALYSIS>>>', normalized, flags=re.IGNORECASE)

    for pattern in [
        r'\*\*KESIMPULAN\*\*',
        r'## KESIMPULAN',
        r'# KESIMPULAN',
        r'KESIMPULAN\n',
    ]:
        normalized = re.sub(pattern, '<<<CONCLUSION>>>', normalized, flags=re.IGNORECASE)

    parts = normalized.split('<<<CONCLUSION>>>')
    if len(parts) >= 2:
        analysis_raw = parts[0].replace('<<<ANALYSIS>>>', '').strip()
        conclusion_raw = parts[1].strip()
    else:
        # Fallback: coba cari nomor 1. 2. 3. sebagai kesimpulan di bagian akhir
        analysis_raw = normalized.replace('<<<ANALYSIS>>>', '').strip()
        conclusion_raw = ""

        # Cari 3 poin terakhir
        lines = analysis_raw.split('\n')
        for i, line in enumerate(lines):
            if re.match(r'^1[\.\)]', line.strip()):
                potential = '\n'.join(lines[i:])
                if re.search(r'^3[\.\)]', potential, re.MULTILINE):
                    analysis_raw = '\n'.join(lines[:i]).strip()
                    conclusion_raw = potential
                    break

    return analysis_raw, conclusion_raw


def _word_count(text: str) -> int:
    """Hitung jumlah kata."""
    return len(text.split()) if text else 0


# ─── STEP 1: INPUT FORM ──────────────────────────────────────────────────────

def page_input():
    st.markdown("""
    <div class="app-header">
        <h1>🔬 Lab Report Generator</h1>
        <p>Generator Analisis & Kesimpulan Laporan Praktikum • Powered by DeepSeek V3 + Gemini</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    with st.form("input_form", clear_on_submit=False):
        # --- Row 1: Mata Praktikum & Judul ---
        col1, col2 = st.columns([1, 1.5])
        with col1:
            mata = st.text_input(
                "📚 Mata Praktikum *",
                placeholder="Fisika Dasar, Kimia Organik...",
                help="Nama mata kuliah/praktikum"
            )
        with col2:
            judul = st.text_input(
                "📝 Judul Modul Praktikum *",
                placeholder="Hukum Ohm, Titrasi Asam-Basa...",
                help="Judul modul atau percobaan"
            )

        # --- Row 2: PDF & Konteks ---
        col3, col4 = st.columns([1, 1])
        with col3:
            modul_pdf = st.file_uploader(
                "📄 File Modul PDF",
                type=["pdf"],
                help="Upload modul praktikum (opsional, untuk konteks tambahan)"
            )
        with col4:
            konteks = st.text_area(
                "💬 Konteks Tambahan",
                placeholder="Informasi tambahan yang relevan tentang percobaan...",
                height=97,
                help="Penjelasan situasi khusus, kondisi alat, dll."
            )

        # --- Row 3: Foto ---
        col5, col6 = st.columns([1, 1])
        with col5:
            foto_percobaan = st.file_uploader(
                "📷 Foto Percobaan",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help="Foto setup alat / proses praktikum (opsional)"
            )
        with col6:
            foto_data = st.file_uploader(
                "📊 Foto Hasil Data",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help="Foto tabel data, grafik, atau hasil pengukuran (opsional)"
            )

        # --- Daftar Pustaka ---
        pustaka = st.text_area(
            "📖 Daftar Pustaka *",
            placeholder=(
                "Tulis satu referensi per baris, contoh:\n"
                "Halliday, D., Resnick, R., Walker, J. 2014. Fundamentals of Physics. Wiley.\n"
                "Tipler, P.A. 2001. Fisika untuk Sains dan Teknik. Erlangga."
            ),
            height=120,
            help="Citasi [1], [2], dst. akan otomatis ditambahkan ke analisis"
        )

        # --- Info box ---
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:0.82rem;color:#92400e;margin-top:4px">
        ⚡ <b>Tips untuk hasil terbaik:</b> Upload foto hasil data yang jelas (tabel/grafik terbaca) dan isi konteks tambahan jika ada kondisi khusus. Foto percobaan membantu AI memahami setup yang digunakan.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "🚀 Generate Laporan",
            type="primary",
            use_container_width=True
        )

        if submitted:
            # Validasi
            errors = []
            if not mata.strip():
                errors.append("Mata Praktikum")
            if not judul.strip():
                errors.append("Judul Modul Praktikum")
            if not pustaka.strip():
                errors.append("Daftar Pustaka")

            if errors:
                st.error(f"⚠️ Field wajib belum diisi: **{', '.join(errors)}**")
                return

            # Cek API keys
            g_key, ds_key = _get_keys()
            if not g_key or not ds_key:
                st.error(
                    "❌ API keys tidak ditemukan!\n\n"
                    "Pastikan `.streamlit/secrets.toml` sudah berisi:\n"
                    "```\nGOOGLE_API_KEY = \"...\"\nOPENROUTER_API_KEY = \"...\"\n```"
                )
                return

            # Simpan ke session
            st.session_state.input_data = {
                "mata_praktikum": mata.strip(),
                "judul": judul.strip(),
                "modul_pdf": modul_pdf,
                "foto_percobaan": foto_percobaan,
                "foto_data": foto_data,
                "daftar_pustaka": pustaka.strip(),
                "konteks_tambahan": konteks.strip(),
            }
            st.session_state.step = "processing"
            st.rerun()


# ─── STEP 2: PROCESSING ──────────────────────────────────────────────────────

def page_processing():
    data = st.session_state.input_data
    g_key, ds_key = _get_keys()

    st.markdown(f"""
    <div class="app-header">
        <h1>⚙️ Memproses...</h1>
        <p>{data['mata_praktikum']} — {data['judul']}</p>
    </div>
    """, unsafe_allow_html=True)

    progress = st.progress(0, text="Memulai...")
    status_box = st.empty()

    # ── 1. Ekstrak PDF ──
    modul_info = ""
    if data.get("modul_pdf"):
        status_box.info("📄 Membaca modul PDF...")
        progress.progress(10, text="Membaca PDF...")
        modul_info = extract_pdf_content(data["modul_pdf"])

    # ── 2. Proses gambar dengan Gemini ──
    percobaan_info = ""
    hasil_data_info = ""

    has_images = bool(data.get("foto_percobaan") or data.get("foto_data"))
    if has_images:
        status_box.info("🖼️ Menganalisis foto dengan Google Gemini...")
        progress.progress(25, text="Analisis foto (Gemini)...")
        try:
            percobaan_info, hasil_data_info = process_images(
                data.get("foto_percobaan") or [],
                data.get("foto_data") or [],
                g_key,
            )
        except Exception as e:
            st.warning(f"⚠️ Foto tidak dapat diproses: {e}. Melanjutkan tanpa analisis foto.")

    # ── 3. Bangun context untuk DeepSeek ──
    analysis_context = {
        "mata_praktikum": data["mata_praktikum"],
        "judul": data["judul"],
        "modul_info": modul_info,
        "percobaan_info": percobaan_info,
        "hasil_data_info": hasil_data_info,
        "daftar_pustaka": data["daftar_pustaka"],
        "konteks_tambahan": data.get("konteks_tambahan", ""),
    }
    st.session_state.analysis_context = analysis_context

    # ── 4. Generate dengan DeepSeek V3 (streaming) ──
    status_box.info("🧠 Membuat analisis dengan DeepSeek V3...")
    progress.progress(40, text="DeepSeek V3 generating...")

    st.markdown("---")
    st.markdown("### 📝 Output — *streaming...*")

    full_output = ""
    output_placeholder = st.empty()

    try:
        for chunk in generate_analysis(analysis_context, ds_key):
            full_output += chunk
            # Update tiap ~50 chars untuk efisiensi render
            if len(full_output) % 80 < 5:
                output_placeholder.markdown(full_output + " ▌")

        output_placeholder.markdown(full_output)
        progress.progress(95, text="Memproses hasil...")

        # Parse sections
        analysis, conclusion = _parse_output(full_output)

        st.session_state.results = {
            "analysis": analysis,
            "conclusion": conclusion,
            "langkah_kerja": "",
            "full_output": full_output,
        }
        st.session_state.regen_count += 1

        progress.progress(100, text="✅ Selesai!")
        status_box.success("✅ Laporan berhasil dibuat!")
        time.sleep(0.8)

        st.session_state.step = "results"
        st.rerun()

    except Exception as e:
        progress.empty()
        status_box.empty()
        st.error(f"❌ Gagal saat generate: `{e}`")
        st.info("Pastikan OPENROUTER_API_KEY valid dan akun OpenRouter aktif.")
        if st.button("← Kembali ke Input"):
            st.session_state.step = "input"
            st.rerun()


# ─── STEP 3: RESULTS ─────────────────────────────────────────────────────────

def page_results():
    data = st.session_state.input_data
    results = st.session_state.results
    _, ds_key = _get_keys()

    # --- Header ---
    st.markdown(f"""
    <div class="app-header">
        <h1>📄 Hasil Laporan</h1>
        <p>
            <span class="chip">📚 {data['mata_praktikum']}</span>
            <span class="chip">📝 {data['judul']}</span>
            {"<span class='chip'>🔄 Versi " + str(st.session_state.regen_count) + "</span>" if st.session_state.regen_count > 1 else ""}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # --- Tabs ---
    tab_labels = ["📊 Analisis & Pembahasan", "✅ Kesimpulan"]
    if results.get("langkah_kerja"):
        tab_labels.append("📋 Langkah Kerja")

    tabs = st.tabs(tab_labels)

    # Tab: Analisis
    with tabs[0]:
        analysis = results.get("analysis", "")
        wc = _word_count(analysis)
        wc_color = "#16a34a" if wc >= 1000 else "#dc2626"
        st.markdown(
            f'<div class="word-count" style="color:{wc_color}">📝 {wc} kata '
            f'{"✓ (memenuhi min. 1000)" if wc >= 1000 else "⚠️ (kurang dari 1000)"}</div>',
            unsafe_allow_html=True
        )
        if analysis:
            st.markdown(analysis)
        else:
            st.warning("Analisis tidak tersedia. Coba regenerate.")

    # Tab: Kesimpulan
    with tabs[1]:
        conclusion = results.get("conclusion", "")
        if conclusion:
            st.markdown(conclusion)
        else:
            st.warning("Kesimpulan tidak tersedia.")

    # Tab: Langkah Kerja (jika ada)
    if results.get("langkah_kerja") and len(tabs) > 2:
        with tabs[2]:
            st.markdown(results["langkah_kerja"])

    st.markdown("---")

    # ─── Action Buttons ───────────────────────────────────────────────────────

    st.markdown("### 🛠️ Tindakan Lanjutan")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📋 Tambah Langkah Kerja", use_container_width=True):
            st.session_state.show_langkah_form = True
            st.session_state.show_edit_form = False

    with col2:
        if st.button("✏️ Sesuaikan Isi", use_container_width=True):
            st.session_state.show_edit_form = True
            st.session_state.show_langkah_form = False

    with col3:
        if st.button("🔄 Regenerate (frasa baru)", use_container_width=True):
            st.session_state.step = "processing"
            st.rerun()

    # Export buttons
    col4, col5 = st.columns(2)

    export_data = {
        "mata_praktikum": data["mata_praktikum"],
        "judul": data["judul"],
        "daftar_pustaka": data.get("daftar_pustaka", ""),
    }

    with col4:
        try:
            docx_bytes = export_to_docx(export_data, results)
            fname = f"laporan_{data['mata_praktikum'].replace(' ', '_')}.docx"
            st.download_button(
                "📥 Export DOCX",
                data=docx_bytes,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"DOCX gagal: {e}")

    with col5:
        try:
            html_str = export_to_html(export_data, results)
            fname_html = f"laporan_{data['mata_praktikum'].replace(' ', '_')}.html"
            st.download_button(
                "🌐 Export HTML",
                data=html_str.encode("utf-8"),
                file_name=fname_html,
                mime="text/html",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"HTML gagal: {e}")

    # ─── Generate Langkah Kerja ───────────────────────────────────────────────

    if st.session_state.show_langkah_form:
        st.markdown("---")
        with st.container():
            st.markdown("#### 📋 Generate Langkah Kerja")
            st.caption(
                "Langkah kerja dibuat berdasarkan konteks modul dan foto percobaan yang sudah diproses."
            )

            col_gen, col_cancel = st.columns([2, 1])
            with col_gen:
                gen_btn = st.button("▶️ Generate Sekarang", type="primary", use_container_width=True)
            with col_cancel:
                if st.button("✕ Batal", use_container_width=True):
                    st.session_state.show_langkah_form = False
                    st.rerun()

            if gen_btn:
                ctx = st.session_state.analysis_context.copy()
                ctx.update({
                    "mata_praktikum": data["mata_praktikum"],
                    "judul": data["judul"],
                })

                lk_output = ""
                lk_placeholder = st.empty()

                try:
                    for chunk in generate_langkah_kerja(ctx, ds_key):
                        lk_output += chunk
                        if len(lk_output) % 60 < 5:
                            lk_placeholder.markdown(lk_output + " ▌")

                    lk_placeholder.markdown(lk_output)
                    st.session_state.results["langkah_kerja"] = lk_output
                    st.session_state.show_langkah_form = False
                    time.sleep(0.3)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Gagal generate langkah kerja: {e}")

    # ─── Edit / Sesuaikan Isi ─────────────────────────────────────────────────

    if st.session_state.show_edit_form:
        st.markdown("---")
        with st.container():
            st.markdown("#### ✏️ Sesuaikan Isi")

            target_options = ["Analisis dan Pembahasan", "Kesimpulan"]
            if results.get("langkah_kerja"):
                target_options.append("Langkah Kerja")

            target = st.selectbox(
                "Bagian yang ingin disesuaikan:",
                target_options,
                index=target_options.index(st.session_state.edit_target)
                if st.session_state.edit_target in target_options
                else 0,
            )
            st.session_state.edit_target = target

            instruction = st.text_area(
                "Instruksi perubahan:",
                placeholder=(
                    "Contoh:\n"
                    "• Tambahkan pembahasan tentang sumber kesalahan pengukuran\n"
                    "• Perkuat analisis variabel bebas dengan kaitkan ke teori\n"
                    "• Buat kesimpulan poin 2 lebih spesifik menyebut nilai data\n"
                    "• Ganti semua frasa yang terdengar seperti AI"
                ),
                height=120,
            )

            col_adj, col_cancel2 = st.columns([2, 1])
            with col_adj:
                adj_btn = st.button("🔄 Proses Perubahan", type="primary", use_container_width=True)
            with col_cancel2:
                if st.button("✕ Batal ", use_container_width=True):
                    st.session_state.show_edit_form = False
                    st.rerun()

            if adj_btn:
                if not instruction.strip():
                    st.warning("⚠️ Tulis instruksi perubahan terlebih dahulu.")
                else:
                    key_map = {
                        "Analisis dan Pembahasan": "analysis",
                        "Kesimpulan": "conclusion",
                        "Langkah Kerja": "langkah_kerja",
                    }
                    result_key = key_map[target]
                    current = results.get(result_key, "")

                    if not current:
                        st.warning("⚠️ Konten yang dipilih masih kosong. Generate dulu.")
                    else:
                        adjusted = ""
                        adj_placeholder = st.empty()

                        try:
                            for chunk in adjust_content(current, instruction, target, ds_key):
                                adjusted += chunk
                                if len(adjusted) % 80 < 5:
                                    adj_placeholder.markdown(adjusted + " ▌")

                            adj_placeholder.markdown(adjusted)
                            st.session_state.results[result_key] = adjusted
                            st.session_state.show_edit_form = False
                            time.sleep(0.3)
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Gagal menyesuaikan isi: {e}")

    # ─── Laporan Baru ────────────────────────────────────────────────────────

    st.markdown("---")
    if st.button("🔬 Buat Laporan Baru", use_container_width=True):
        keys_to_clear = [
            "step", "results", "input_data", "analysis_context",
            "show_langkah_form", "show_edit_form", "edit_target", "regen_count",
        ]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        _init_state()
        st.rerun()


# ─── Sidebar: Info & API Status ──────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.markdown("### ℹ️ Tentang Aplikasi")
        st.caption(
            "Generator laporan praktikum berbasis AI. "
            "Menggunakan Google Gemini untuk analisis foto dan DeepSeek V3 untuk penulisan."
        )

        st.markdown("---")
        st.markdown("### 🔑 Status API")
        g_key, or_key = _get_keys()

        if g_key:
            st.success("✓ Google Gemini API terhubung")
        else:
            st.error("✗ GOOGLE_API_KEY tidak ditemukan")

        if or_key:
            st.success("✓ OpenRouter API terhubung")
        else:
            st.error("✗ OPENROUTER_API_KEY tidak ditemukan")

        st.markdown("---")
        st.markdown("### 📊 Arsitektur AI")
        st.markdown("""
        | Tugas | Model |
        |-------|-------|
        | Analisis foto | Gemini 1.5 Flash |
        | Analisis & kesimpulan | Nemotron-49B (free) |
        | Langkah kerja & edit | Owl Alpha (free) |
        """)

        st.markdown("---")
        st.markdown("### 📝 Panduan Singkat")
        with st.expander("Cara pakai"):
            st.markdown("""
            1. Isi Mata Praktikum & Judul Modul
            2. Upload PDF modul *(opsional)*
            3. Upload foto percobaan & hasil data *(opsional)*
            4. Isi daftar pustaka (1 per baris)
            5. Klik **Generate Laporan**
            6. Tunggu analisis selesai
            7. Download DOCX atau HTML
            """)

        with st.expander("Tips hasil terbaik"):
            st.markdown("""
            - Foto hasil data yang jelas meningkatkan akurasi analisis
            - Isi **Konteks Tambahan** untuk kondisi khusus
            - Gunakan **Regenerate** jika frasa terasa kurang tepat
            - Gunakan **Sesuaikan Isi** untuk edit spesifik
            """)

        if st.session_state.step == "results" and st.session_state.results.get("analysis"):
            st.markdown("---")
            wc = len(st.session_state.results["analysis"].split())
            st.metric("Panjang Analisis", f"{wc} kata", delta=f"{wc - 1000:+d} dari min. 1000")


# ─── Main Router ─────────────────────────────────────────────────────────────

def main():
    _sidebar()

    step = st.session_state.step

    if step == "input":
        page_input()
    elif step == "processing":
        page_processing()
    elif step == "results":
        page_results()
    else:
        st.session_state.step = "input"
        st.rerun()


if __name__ == "__main__":
    main()
