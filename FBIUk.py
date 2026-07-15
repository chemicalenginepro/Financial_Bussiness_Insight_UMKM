import streamlit as st
import pandas as pd
import plotly.express as px
import pypdf
from fpdf import FPDF
import io
import re

# ==============================================================================
# 1. KONFIGURASI HALAMAN & INI-TIALISASI (Optimasi Layar HP / Mobile Responsive)
# ==============================================================================

st.set_page_config(
    page_title="Business Insight AI",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Kustomisasi CSS agar tampilan tombol dan input nyaman ditekan di layar HP
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .stDownloadButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background-color: #00CC66; color: white; }
    </style>""", unsafe_allow_html=True)

st.title("Business Insight AI 📊")
st.caption("Aplikasi Analisis Finansial Otomatis untuk UKM, Akuntan, Auditor, & Investor")

# Memeriksa API Key Gemini dari Streamlit Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# Menginisialisasi variabel penyimpanan data di dalam session state agar tidak hilang saat halaman reload
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "ai_report" not in st.session_state:
    st.session_state.ai_report = ""

# ==============================================================================
# 2. KOMPONEN UPLOAD & CLEANING DATA OTOMATIS (ZERO ERROR PROCESSING)
# ==============================================================================

uploaded_file = st.file_uploader(
    "Unggah Dokumen Keuangan Anda (Excel, CSV, atau PDF)", 
    type=["csv", "xlsx", "xls", "pdf"]
)

if uploaded_file is not None:
    file_name = uploaded_file.name
    file_type = file_name.split(".")[-1].lower()
    
    # PROSES 1: Jika Input Berupa Dokumen PDF (Laporan Narasi / Rekening Koran Scan Teks)
    if file_type == "pdf":
        try:
            pdf_reader = pypdf.PdfReader(uploaded_file)
            full_text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            if full_text.strip():
                st.session_state.extracted_text = full_text
                st.session_state.cleaned_df = None  # Reset data tabular jika ganti ke PDF
                st.success("✅ Teks PDF Berhasil Diekstrak Secara Presisi!")
                with st.expander("👁️ Intip Preview Dokumen PDF", expanded=False):
                    st.text_area("Konten Mentah", full_text[:1000], height=150, disabled=True)
            else:
                st.error("❌ Gagal membaca PDF: Dokumen kosong atau berupa gambar (butuh OCR).")
        except Exception as e:
            st.error(f"⚠️ Terjadi galat saat memproses PDF: {str(e)}")
            
    # PROSES 2: Jika Input Berupa File Tabular (Excel / CSV Laporan Keuangan)
    else:
        try:
            if file_type == "csv":
                df_raw = pd.read_csv(uploaded_file)
            else:
                df_raw = pd.read_excel(uploaded_file)
                
            if df_raw.empty:
                st.error("❌ File yang Anda unggah tidak memiliki baris data (kosong).")
            else:
                # --- SISTEM CLEANING OTOMATIS (Anti-Crash Layer) ---
                df_proc = df_raw.copy()
                # Hapus baris dan kolom yang 100% kosong tanpa sisa
                df_proc.dropna(how="all", inplace=True)
                df_proc.dropna(how="all", axis=1, inplace=True)
                
                # Standarisasi judul kolom (lowercase, hapus spasi berlebih, ganti spasi dengan '_')
                df_proc.columns = df_proc.columns.str.strip().str.replace(r'\s+', '_', regex=True).str.lower()
                
                # Pembersihan sel kosong berdasarkan tipe data
                for col in df_proc.columns:
                    if pd.api.types.is_numeric_dtype(df_proc[col]):
                        df_proc[col] = df_proc[col].fillna(0) # Ganti NaN angka dengan 0
                    else:
                        df_proc[col] = df_proc[col].fillna("N/A") # Ganti NaN teks dengan N/A
                
                st.session_state.cleaned_df = df_proc
                st.session_state.extracted_text = df_proc.to_string(index=False) # Untuk dibaca AI nanti
                st.success(f"✅ Data '{file_name}' Berhasil Dibersihkan Otomatis!")
                
                with st.expander("👁️ Lihat Tabel Data Hasil Penyelarasan", expanded=True):
                    st.dataframe(df_proc, use_container_width=True)
        except Exception as e:
            st.error(f"⚠️ Gagal memproses data tabel: {str(e)}")

# ==============================================================================
# 3. DASHBOARD INTERAKTIF & ENGINE FORMULA MATEMATIS
# ==============================================================================

if st.session_state.cleaned_df is not None:
    df_active = st.session_state.cleaned_df
    available_cols = df_active.columns.tolist()
    
    st.markdown("---")
    st.subheader("Interactive Financial Dashboard")
    
    # Selektor sumbu grafik yang aman dan anti-error meskipun nama kolom acak
    col_x = st.selectbox("Pilih Sumbu X (Misal: Bulan / Tanggal / Akun):", available_cols, index=0)
    col_y = st.selectbox("Pilih Sumbu Y (Nilai Angka Keuangan):", available_cols, index=min(1, len(available_cols)-1))
    
    # Validasi apakah kolom Y berisi angka sebelum membuat grafik grafik
    if pd.api.types.is_numeric_dtype(df_active[col_y]):
        try:
            fig = px.line(
                df_active, 
                x=col_x, 
                y=col_y, 
                title=f"Tren Perubahan {col_y.replace('_',' ').title()} Berdasarkan {col_x.replace('_',' ').title()}", 
                markers=True
            )
            fig.update_layout(margin=dict(l=15, r=15, t=40, b=15)) # Margin super ketat untuk HP
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Gagal merender grafik: {str(e)}")
    else:
        st.warning(f"⚠️ Kolom '{col_y}' bukan tipe data angka. Silakan pilih kolom angka untuk menampilkan tren grafik.")

# ==============================================================================
# 4. INTEGRASI INTELEKTUAL GEMINI 2.5 API (GRATIS & POWERFUL)
# ==============================================================================

if st.session_state.extracted_text:
    st.markdown("---")
    st.subheader("Otak Analisis Kecerdasan Buatan")
    
    if st.button("🚀 Jalankan Analisis Komprehensif AI"):
        if not GEMINI_API_KEY:
            st.error("⚠️ Error Pengaturan: API Key 'GEMINI_API_KEY' tidak ditemukan di Streamlit Secrets Anda!")
        else:
            with st.spinner("Mengirim data ke server Google Gemini Cloud... Mohon tunggu..."):
                try:
                    # Menggunakan metode requests HTTP REST asli untuk menjamin zero-dependence error library
                    import requests
                    import json
                    
                    # URL Endpoint Resmi Google AI Studio untuk Gemini 2.5 Flash (Sesuai dokumentasi terbaru)
                    url = f"https://googleapis.com{GEMINI_API_KEY}"
                    
                    system_instruction = (
                        "Anda adalah sistem AI pakar finansial gabungan dari Akuntan Publik, Auditor Forensik, "
                        "dan Konsultan Manajemen Risiko Korporat Senior. Tugas Anda adalah menganalisis data keuangan "
                        "yang diberikan pengguna secara brutal jujur, akurat, matematis, dan memberikan insight mendalam."
                    )
                    
                    user_prompt = f"""
                    Lakukan analisis keuangan mendalam terhadap data berikut ini:
                    
                    {st.session_state.extracted_text}
                    
                    Sajikan laporan komprehensif menggunakan Bahasa Indonesia yang formal dan mudah dipahami, dengan sistematika berikut wajib diisi:
                    
                    1. ANALISIS RASIO KEUANGAN UTAMA
                       - Jabarkan evaluasi likuiditas, profitabilitas, serta efisiensi modal berdasarkan data yang tersedia.
                       
                    2. ANALISIS ARUS KAS (CASH FLOW)
                       - Evaluasi kestabilan perputaran kas masuk dan keluar.
                       
                    3. PREDIKSI KEBANGRUTAN (ALTMAN Z-SCORE / MODEL FINANSIAL)
                       - Berikan penilaian matematis atau indikasi logis apakah bisnis berada dalam Zona Aman (Safe), Abu-abu (Grey), atau Bahaya (Distress).
                       
                    4. DETEKSI ANOMALI DAN RISIKO KECURANGAN
                       - Soroti lonjakan angka, transaksi ganjil, pengeluaran berlebih, atau ketidakseimbangan saldo jika terdeteksi.
                       
                    5. REKOMENDASI STRATEGI BISNIS TAKTIS
                       - Berikan panduan tindakan konkret yang harus diambil oleh UKM, Auditor, atau Investor untuk meningkatkan laba atau menyelamatkan operasional.
                    """
                    
                    headers = {'Content-Type': 'application/json'}
                    payload = {
                        "contents": [{
                            "parts": [{"text": f"{system_instruction}\n\n{user_prompt}"}]
                        }]
                    }
                    
                    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
                    response_json = response.json()
                    
                    # Parsing jawaban dari struktur JSON respon Google Gemini
                    if response.status_code == 200:
                        text_output = response_json['candidates'][0]['content']['parts'][0]['text']
                        st.session_state.ai_report = text_output
                    else:
                        error_msg = response_json.get('error', {}).get('message', 'Unknown API Error')
                        st.error(f"Google API mengembalikan error: {error_msg}")
                except Exception as api_err:
                    st.error(f"Gagal terhubung ke layanan kecerdasan Google: {str(api_err)}")

# Menampilkan laporan hasil kecerdasan AI ke layar HP jika sudah digenerate
if st.session_state.ai_report:
    st.success("✅ Analisis AI Selesai Disusun!")
    st.markdown("### Laporan Inteligensi Finansial")
    st.info(st.session_state.ai_report)

# ==============================================================================
# 5. GENERATOR EKSPOR PDF PROFESIONAL (CLEAN LATIN-1 COMPLIANT)
# ==============================================================================

try:
    # Fungsi konversi string aman agar PDF tidak crash saat membaca karakter khusus/emoji
    def clean_text_for_pdf(text):
        # Ganti karakter penanda markdown bolds, bullet points, dan karakter aneh agar mulus di PDF
        text = text.replace("**", "").replace("*", "-").replace("`", "'")
        # Loloskan konversi ke format pengkodean latin-1
        return text.encode('latin-1', 'replace').decode('latin-1')
    
    # Membangun file PDF di dalam RAM HP/Cloud menggunakan BytesIO
    pdf = FPDF()
    pdf.add_page()
    
    # Judul Laporan
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.cell(190, 10, txt="BUSINESS INSIGHT AI REPORT", ln=True, align='C')
    pdf.set_font("Helvetica", style="I", size=10)
    pdf.cell(190, 8, txt="Dokumen Analisis Otomatis - Profesional & Rahasia", ln=True, align='C')
    pdf.ln(10)
    
    # Isi Laporan
    pdf.set_font("Helvetica", size=10)
    lines = st.session_state.ai_report.split('\n')
    for line in lines:
        cleaned_line = clean_text_for_pdf(line)
        # Gunakan multi_cell agar teks otomatis turun ke baris baru saat mentok pinggir kertas PDF
        pdf.multi_cell(190, 6, txt=cleaned_line)
    
    pdf_bytes = pdf.output()
    
    st.download_button(
        label="📥 Unduh Hasil Laporan PDF Profesional",
        data=bytes(pdf_bytes),
        file_name="Laporan_Business_Insight_AI.pdf",
        mime="application/pdf"
    )
except Exception as pdf_err:
    st.error(f"Gagal mengonversi teks laporan menjadi berkas PDF: {str(pdf_err)}")

else:
    st.info("💡 Petunjuk: Silakan unggah berkas data keuangan Anda di atas untuk mengaktifkan grafik interaktif dashboard dan menyusun laporan intelijen AI otomatis.")
