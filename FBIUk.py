import streamlit as stimport pandas as pdimport plotly.express as pximport pypdffrom fpdf import FPDFimport ioimport requestsimport jsonfrom supabase import create_client, Client
# ==============================================================================# 1. HALAMAN UTAMA & KONFIGURASI MOBILE RESPONSIVE# ==============================================================================
st.set_page_config(
    page_title="Business Insight AI Premium",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)
# Kustomisasi CSS Tombol untuk Kenyamanan Layar Sentuh Smartphone
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .stDownloadButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; background-color: #00CC66; color: white; }
    </style>""", unsafe_allow_html=True)
# Mengambil seluruh Kunci Kredensial Rahasia dari Streamlit SecretsSUPABASE_URL = st.secrets.get("SUPABASE_URL")SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")  # Diisi oleh 'anon/public' API key SupabaseGEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
# Inisialisasi Koneksi Klien Supabase DBsupabase: Client = Noneif SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Gagal mengoneksikan pangkalan data Supabase: {e}")
# Inisialisasi Lapisan Memori Klien (Session State Management)if "logged_in" not in st.session_state:
    st.session_state.logged_in = Falseif "user_email" not in st.session_state:
    st.session_state.user_email = ""if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = Noneif "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""if "ai_report" not in st.session_state:
    st.session_state.ai_report = ""
# ==============================================================================# 2. GERBANG OTENTIKASI SISTEM (SUPABASE AUTH SHIELD LAYER)# ==============================================================================if not st.session_state.logged_in:
    st.title("🔐 Akses Terproteksi")
    st.caption("Business Insight AI - Solusi Analisis Keuangan Premium")
    
    tab_login, tab_register = st.tabs(["🔑 Masuk (Login)", "📝 Daftar Akun Baru"])
    
    with tab_login:
        login_email = st.text_input("Email Pengguna:", key="login_em")
        login_password = st.text_input("Kata Sandi:", type="password", key="login_pw")
        
        if st.button("Masuk ke Aplikasi"):
            if supabase is None:
                st.error("Sistem Database internal belum terkonfigurasi di Streamlit Secrets.")
            elif not login_email or not login_password:
                st.warning("Mohon isi seluruh kolom email dan kata sandi!")
            else:
                try:
                    # Memeriksa data login ke server sistem otentikasi enterprise Supabase
                    response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                    st.session_state.logged_in = True
                    st.session_state.user_email = login_email
                    st.success("🎯 Login Berhasil! Membuka gerbang aplikasi...")
                    st.rerun()
                except Exception as auth_err:
                    st.error(f"❌ Gagal Masuk: Kombinasi Email atau Password salah! ({str(auth_err)})")
                    
    with tab_register:
        st.info("Pendaftaran ini ditujukan bagi klien baru Anda untuk mendapatkan hak akses berbayar.")
        reg_email = st.text_input("Masukkan Email Klien Baru:", key="reg_em")
        reg_password = st.text_input("Buat Kata Sandi Klien (Minimal 6 Karakter):", type="password", key="reg_pw")
        
        if st.button("Daftarkan Akun Klien"):
            if supabase is None:
                st.error("Sistem Hubungan Database terputus.")
            elif not reg_email or len(reg_password) < 6:
                st.warning("Email wajib diisi dan kata sandi minimal harus berjumlah 6 karakter!")
            else:
                try:
                    # Mendaftarkan email pengguna baru ke tabel internal Supabase secara terenkripsi
                    supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                    st.success("✅ Pendaftaran Akun Berhasil! Silakan instruksikan klien Anda untuk memeriksa kotak masuk/spam email mereka guna konfirmasi aktivasi.")
                except Exception as reg_err:
                    st.error(f"❌ Proses Pendaftaran Akun Gagal: {str(reg_err)}")
                    
    st.stop()  # Mengunci script secara brutal agar halaman inti tidak bisa di-bypass lewat inspect element
# ==============================================================================# 3. ANTARMUKA UTAMA (SETELAH USER BERHASIL LOGIN)# ==============================================================================col_user_info, col_logout_act = st.columns([3, 1])with col_user_info:
    st.write(f"👤 Pengguna Aktif: **{st.session_state.user_email}**")with col_logout_act:
    if st.button("🚪 Keluar"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.cleaned_df = None
        st.session_state.extracted_text = ""
        st.session_state.ai_report = ""
        st.rerun()

st.title("Business Insight AI 📊")
st.caption("Aplikasi Analisis Finansial Otomatis untuk UKM, Akuntan, Auditor, & Investor")
# ==============================================================================# 4. FILTER UPLOAD & ENGINES PEMBERSIH DATA TABULAR/PDF (ANTI-CRASH LOGIC)# ==============================================================================uploaded_file = st.file_uploader(
    "Unggah Dokumen Keuangan Anda (Excel, CSV, atau PDF)", 
    type=["csv", "xlsx", "xls", "pdf"]
)
if uploaded_file is not None:
    file_name = uploaded_file.name
    file_type = file_name.split(".")[-1].lower()
    
    # KONDISI 1: Parsing Teks Dokumen Cetak / Laporan Keuangan PDF
    if file_type == "pdf":
        try:
            pdf_reader = pypdf.PdfReader(uploaded_file)
            full_text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            if full_text.strip():
                st.session_state.extracted_text = full_text
                st.session_state.cleaned_df = None  # Reset memori tabel tabular
                st.success("✅ Seluruh Teks Dokumen PDF Berhasil Diekstrak Secara Presisi!")
                with st.expander("👁️ Intip Preview Ekstraksi PDF", expanded=False):
                    st.text_area("Konten Mentah Teks", full_text[:1000], height=150, disabled=True)
            else:
                st.error("❌ Dokumen PDF kosong atau berupa hasil foto kamera tanpa lapisan teks tembus baca (bukan PDF teks).")
        except Exception as e:
            st.error(f"⚠️ Terjadi gangguan fatal pemrosesan PDF: {str(e)}")
            
    # KONDISI 2: Pemrosesan Berkas Spreadsheet Angka (Excel / CSV)
    else:
        try:
            if file_type == "csv":
                df_raw = pd.read_csv(uploaded_file)
            else:
                df_raw = pd.read_excel(uploaded_file)
                
            if df_raw.empty:
                st.error("❌ Berkas data yang diunggah kosong (tidak memiliki baris atau kolom data).")
            else:
                # --- JALUR PEMBERSIHAN DATA MAKSIMAL (CLEANING LAYER) ---
                df_proc = df_raw.copy()
                df_proc.dropna(how="all", inplace=True)
                df_proc.dropna(how="all", axis=1, inplace=True)
                
                # Menghilangkan spasi liar pada baris nama kolom dan mengubahnya ke huruf kecil
                df_proc.columns = df_proc.columns.str.strip().str.replace(r'\s+', '_', regex=True).str.lower()
                
                # Mengisi baris kosong secara otomatis berdasarkan jenis kolom data
                for col in df_proc.columns:
                    if pd.api.types.is_numeric_dtype(df_proc[col]):
                        df_proc[col] = df_proc[col].fillna(0)  # Menambal angka kosong dengan nilai 0
                    else:
                        df_proc[col] = df_proc[col].fillna("N/A")  # Menambal teks kosong dengan tanda N/A
                
                st.session_state.cleaned_df = df_proc
                st.session_state.extracted_text = df_proc.to_string(index=False)
                st.success(f"✅ Data Tabel '{file_name}' Berhasil Diselaraskan Otomatis!")
                
                with st.expander("👁️ Tinjau Struktur Tabel Hasil Penyelarasan", expanded=True):
                    st.dataframe(df_proc, use_container_width=True)
        except Exception as e:
            st.error(f"⚠️ Sistem gagal merapikan data tabel keuangan Anda: {str(e)}")
# ==============================================================================# 5. DASHBOARD GRAFIK TREN KEUANGAN RESPONSIVE (PLOTLY ENGINE)# ==============================================================================if st.session_state.cleaned_df is not None:
    df_active = st.session_state.cleaned_df
    available_cols = df_active.columns.tolist()
    
    st.markdown("---")
    st.subheader("Interactive Financial Dashboard")
    
    col_x = st.selectbox("Pilih Kolom Sumbu X (Misal: Periode / Bulan / Akun):", available_cols, index=0)
    col_y = st.selectbox("Pilih Kolom Sumbu Y (Nilai Keuangan Angka):", available_cols, index=min(1, len(available_cols)-1))
    
    if pd.api.types.is_numeric_dtype(df_active[col_y]):
        try:
            fig = px.line(
                df_active, 
                x=col_x, 
                y=col_y, 
                title=f"Tren Perubahan {col_y.replace('_',' ').title()} Berdasarkan {col_x.replace('_',' ').title()}", 

markers=True
)
fig.update_layout(margin=dict(l=15, r=15, t=40, b=15)) # Pembatasan margin super ketat untuk HP
st.plotly_chart(fig, use_container_width=True)
except Exception as e:
st.error(f"Gagal memetakan grafik visual: {str(e)}")
else:
st.warning(f"⚠️ Kolom '{col_y}' terdeteksi bukan berupa deret data angka. Silakan pilih opsi kolom angka lain agar grafik tren muncul.")
## ==============================================================================## 6. ENGINES INTEGRASI INTEGRITAS GOOGLE GEMINI 2.5 API (HTTP CORE PROCESSING)## ==============================================================================
if st.session_state.extracted_text:
st.markdown("---")
st.subheader("Otak Analisis Kecerdasan Buatan")
if st.button("🚀 Jalankan Analisis Komprehensif AI", use_container_width=True):
if not GEMINI_API_KEY:
st.error("⚠️ Masalah Konfigurasi Server: Kunci rahasia 'GEMINI_API_KEY' belum dimasukkan ke pengaturan Streamlit Secrets!")
else:
with st.spinner("Mengevaluasi laporan finansial Anda bersama Google Gemini Cloud... Mohon tunggu sebentar..."):
try:
# Menembak lurus REST API Endpoint Google AI Studio untuk jaminan independensi bebas usang
url = f"googleapis.com{GEMINI_API_KEY}"
system_instruction = (
"Anda adalah sistem AI pakar finansial gabungan dari Akuntan Publik, Auditor Forensik, "
"dan Konsultan Manajemen Risiko Korporat Senior. Tugas Anda adalah menganalisis data keuangan "
"yang diberikan pengguna secara jujur, objektif, matematis, dan memberikan insight operasional."
)
user_prompt = f"""
Lakukan analisis laporan keuangan mendalam terhadap data berikut ini:
{st.session_state.extracted_text}
Sajikan laporan komprehensif menggunakan Bahasa Indonesia yang formal dengan sistematika struktur wajib sebagai berikut:
1. ANALISIS RASIO KEUANGAN UTAMA
- Jabarkan evaluasi rasio likuiditas, profitabilitas, serta efisiensi modal dari data yang tersedia.
2. ANALISIS ARUS KAS (CASH FLOW)
- Evaluasi kestabilan perputaran kas masuk dan kas keluar.
3. PREDIKSI KEBANGRUTAN (ALTMAN Z-SCORE / MODEL FINANSIAL)
- Berikan penilaian berupa indikasi matematis/logis apakah bisnis berada dalam Zona Aman (Safe), Abu-abu (Grey), atau Bahaya (Distress).
4. DETEKSI ANOMALI DAN RISIKO KECURANGAN
- Soroti jika terdeteksi adanya lonjakan angka janggal, transaksi ganjil, pengeluaran berlebih, atau ketidakseimbangan akun saldo.
5. REKOMENDASI STRATEGI BISNIS TAKTIS
- Berikan panduan tindakan konkret yang harus diambil oleh pemilik UKM, Auditor, atau Investor untuk mendongkrak laba atau menyelamatkan operasional perusahaan.
"""
headers = {'Content-Type': 'application/json'}
payload = {
"contents": [{
"parts": [{"text": f"{system_instruction}\n\n{user_prompt}"}]
}]
}
response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
response_json = response.json()
if response.status_code == 200:
st.session_state.ai_report = response_json['candidates'][0]['content']['parts'][0]['text']
else:
error_msg = response_json.get('error', {}).get('message', 'Galat API Eksternal Tidak Teridentifikasi')
st.error(f"Google Cloud Systems mengembalikan pesan penolakan: {error_msg}")
except Exception as api_err:
st.error(f"Gagal menghubungkan sambungan ke pusat komputasi AI Google Cloud: {str(api_err)}")
# Blok Penampil Hasil Penyusunan Analisis AI ke Layar HP Pengguna
if st.session_state.ai_report:
st.success("✅ Analisis Intelijen AI Selesai Disusun!")
st.markdown("### Laporan Inteligensi Finansial")
st.info(st.session_state.ai_report)
# ==============================================================================
# 7. GENERATOR EKSPOR DOKUMEN PDF PROFESIONAL (PROTECTION ENCODING COMPLIANT)
# ==============================================================================
try:
# Fungsi khusus pembersih sisa penulisan Markdown bintang tebal agar PDF Compiler tidak crash
def clean_text_for_pdf(text):
text = text.replace("**", "").replace("*", "-").replace("`", "'")
return text.encode('latin-1', 'replace').decode('latin-1')
# Membangun objek berkas cetak PDF di dalam memori RAM virtual
pdf = FPDF()
pdf.add_page()
# Pengaturan Kop Surat Formal Dokumen PDF
pdf.set_font("Helvetica", style="B", size=16)
pdf.cell(190, 10, txt="BUSINESS INSIGHT AI REPORT", ln=True, align='C')
pdf.set_font("Helvetica", style="I", size=10)
pdf.cell(190, 8, txt="Dokumen Hasil Analisis Otomatis - Profesional & Rahasia", ln=True, align='C')
pdf.ln(10)
# Menuangkan Teks Analisis AI Secara Baris demi Baris ke Lembar Kertas PDF
pdf.set_font("Helvetica", size=10)
lines = st.session_state.ai_report.split('\n')
for line in lines:
cleaned_line = clean_text_for_pdf(line)
# multi_cell menjamin baris kalimat panjang akan otomatis dibungkus ke baris bawahnya secara simetris
pdf.multi_cell(190, 6, txt=cleaned_line)
pdf_bytes = pdf.output()
st.download_button(
label="📥 Unduh Hasil Laporan PDF Profesional",
data=bytes(pdf_bytes),
file_name="Laporan_Business_Insight_AI.pdf",
mime="application/pdf",
use_container_width=True
)
except Exception as pdf_err:
st.error(f"Sistem operasi gagal mengonversi salinan teks menjadi berkas PDF digital: {str(pdf_err)}")
else:
st.info("💡 Petunjuk Penggunaan: Silakan unggah berkas data laporan keuangan Anda di atas untuk membuka dasbor tren grafik visual dan menyusun analisis kecerdasan AI otomatis.")




