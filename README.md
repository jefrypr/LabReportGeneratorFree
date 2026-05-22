# 🔬 Lab Report Generator (OpenRouter Edition)

Generator otomatis **Analisis & Kesimpulan** laporan praktikum berbasis AI.  
Menggunakan **Google Gemini 1.5 Flash** untuk analisis foto dan **OpenRouter** (model gratis) untuk penulisan.

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|-----------|
| 📊 Analisis & Pembahasan | Min. 1000 kata, paragraf naratif, dengan citasi referensi |
| ✅ Kesimpulan | 3 poin padat berisi sebab-akibat |
| 📋 Langkah Kerja | Generate otomatis dari konteks praktikum |
| ✏️ Sesuaikan Isi | Edit bagian tertentu dengan instruksi natural |
| 🔄 Regenerate | Frasa berbeda tiap generate (variasi otomatis) |
| 📥 Export DOCX | Dokumen Word terformat siap print |
| 🌐 Export HTML | File HTML bergaya laporan akademik |

---

## 🏗️ Arsitektur AI

```
Foto percobaan/data  ──►  Google Gemini 1.5 Flash  ──►  deskripsi teks
PDF modul            ──►  pdfplumber (lokal)        ──►  ringkasan teks
                                                          │
                                     ┌────────────────────┘
                                     ▼
                              OpenRouter API
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
              Nemotron-49B:free           Owl Alpha:free
          (analisis & kesimpulan)   (langkah kerja & edit)
```

---

## 🚀 Cara Deploy ke Streamlit Cloud

### 1. Dapatkan API Keys

**Google Gemini (gratis):**
1. Buka https://aistudio.google.com/app/apikey
2. Login dengan akun Google → klik **"Create API key"**
3. Copy API key (format: `AIzaSyXXXXXXX`)

**OpenRouter (gratis):**
1. Daftar di https://openrouter.ai
2. Masuk ke **Account → Keys → Create Key**
3. Copy API key (format: `sk-or-v1-XXXXXXXXXX`)
4. Model yang digunakan sudah `:free` — tidak perlu top-up untuk mulai

> **Cek ketersediaan model gratis terkini:** https://openrouter.ai/models?q=free  
> Ganti `MODEL_ANALYSIS` / `MODEL_HELPER` di `utils/text_generator.py` jika model berubah.

### 2. Isi `secrets.toml`

Edit file `.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY     = "AIzaSyAbc123..."
OPENROUTER_API_KEY = "sk-or-v1-abc123..."
```

### 3. Push ke GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/USERNAME/lab-report-generator.git
git push -u origin main
```

> ⚠️ Jangan push `secrets.toml` — sudah ada di `.gitignore`.

### 4. Deploy di Streamlit Cloud

1. Buka https://share.streamlit.io → **New app**
2. Pilih repo → branch `main` → main file `app.py`
3. Klik **"Advanced settings"** → **Secrets** → paste:
   ```toml
   GOOGLE_API_KEY     = "AIzaSy..."
   OPENROUTER_API_KEY = "sk-or-v1-..."
   ```
4. Klik **Deploy!** → tunggu ~3 menit

---

## 🔧 Ganti Model

Buka `utils/text_generator.py`, ubah dua konstanta ini:

```python
MODEL_ANALYSIS = "nvidia/nemotron-3-super-49b:free"   # analisis & kesimpulan
MODEL_HELPER   = "openrouter/auto"                     # langkah kerja & edit
```

Model gratis lain yang bisa dicoba (per mid-2025):
- `meta-llama/llama-3.3-70b-instruct:free`
- `microsoft/phi-4-reasoning-plus:free`
- `qwen/qwen3-235b-a22b:free`
- `nvidia/nemotron-super-49b-v1:free`

---

## 📁 Struktur Proyek

```
lab-report-generator/
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
├── .streamlit/
│   └── secrets.toml        ← isi API key di sini
└── utils/
    ├── image_processor.py  ← Google Gemini
    ├── pdf_processor.py    ← baca PDF modul
    ├── text_generator.py   ← OpenRouter (edit model di sini)
    └── export_handler.py   ← DOCX & HTML
```

---

## 📄 Lisensi

MIT — bebas digunakan untuk keperluan akademik.
