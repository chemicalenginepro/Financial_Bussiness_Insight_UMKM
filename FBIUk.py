import streamlit as st
import pandas as pd
import plotly.express as px
import pypdf
from fpdf import FPDF
import io
import requests
import json
from supabase import create_client, Client

# ==============================================================================
# 1. HALAMAN UTAMA & KONFIGURASI MOBILE RESPONSIVE
# ==============================================================================

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
    </style>
""", unsafe_allow_html=True)

# Mengambil seluruh Kunci Kredensial Rahasia dari Streamlit Secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")  # Diisi oleh 'anon/public' API key Supabase
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# Inisialisasi Koneksi Klien Supabase DB
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Gagal mengoneksikan pangkalan data Supabase: {e}")

# Inisialisasi Lapisan Memori Klien (Session State Management)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "ai_report" not in st.session_state:
    st.session_state.ai_report = ""

# ==============================================================================
# 2. GERBANG OTENTIKASI SISTEM (TOKEN SEKALI PAKAI & ANTI-BOCOOR MULTI DEVICE)
# ==============================================================================

if not st.session_state.logged_in:
    st.title("🔐 Akses Premium Terproteksi")
    st.caption("Business Insight AI - Silakan Masuk atau Daftarkan Lisensi Anda")

    # KUNCI CONFIG UTAMA (DITARUH DI LUAR AGAR KEDUA TAB BISA MEMBACA TANPA ERROR)
    EMAIL_OWNER_UTAMA = "borris.setyawan@gmail.com"  # <--- GANTI JADI EMAIL MAS
    TOKEN_SUPER_ADMIN = "ADMIN-SUPER-SIDOARJO"  # <--- TOKEN KHUSUS UNTUK MAS

    tab_login, tab_register = st.tabs(["🔑 Masuk (Login)", "📝 Aktivasi Akun Mandiri"])

    # --------------------------------------------------------------------------
    # TAB 1: FORMULIR LOGIN (DENGAN KUNCI PERANGKAT KETAT & BYPASS ADMIN)
    # --------------------------------------------------------------------------
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
                    # 1. Cek email dan password ke server Supabase Auth
                    auth_resp = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                    user_info = auth_resp.user

                    # 2. Ambil Sidik Jari browser fisik yang sedang dipakai login saat ini
                    device_fingerprint = st.context.headers.get("User-Agent", "Unknown-Device")

                    # 3. Ambil daftar perangkat yang sudah terikat di metadata akun user ini
                    registered_devices = user_info.user_metadata.get("allowed_devices", [])

                    # JALUR KHUSUS A: Jika yang Login adalah Mas (Owner), Loloskan Perangkat Apa Saja!
                    if login_email.strip().lower() == EMAIL_OWNER_UTAMA.lower():
                        st.session_state.logged_in = True
                        st.session_state.user_email = login_email
                        st.rerun()

                    # JALUR KETAT B: Untuk Pembeli (Wajib Kunci 2 Perangkat Pertama)
                    else:
                        if device_fingerprint in registered_devices:
                            st.session_state.logged_in = True
                            st.session_state.user_email = login_email
                            st.rerun()
                        else:
                            if len(registered_devices) < 2:
                                # Jika jatah perangkat masih di bawah 2, kunci perangkat baru ini otomatis
                                registered_devices.append(device_fingerprint)
                                supabase.auth.admin.update_user_by_id(
                                    user_info.id,
                                    attributes={"user_metadata": {"allowed_devices": registered_devices}}
                                )
                                st.session_state.logged_in = True
                                st.session_state.user_email = login_email
                                st.success("✅ Perangkat baru Anda berhasil diverifikasi dan dikunci!")
                                st.rerun()
                            else:
                                # Jika perangkat ke-3 milik temannya mencoba menyusup, BLOKIR TOTAL!
                                st.error("❌ Akses Ditolak! Akun lisensi ini sudah terkunci maksimal pada 2 perangkat pertama Anda (1 Laptop + 1 HP). Hubungi Admin untuk reset perangkat baru.")
                except Exception as auth_err:
                    st.error("❌ Gagal Masuk: Kombinasi Email atau Password salah!")

    # --------------------------------------------------------------------------
    # TAB 2: FORMULIR DAFTAR MANDIRI (TOKEN SEKALI PAKAI + BYPASS REGISTER ADMIN)
    # --------------------------------------------------------------------------
    with tab_register:
        st.info("Pendaftaran mandiri hanya berlaku bagi pembeli resmi yang memiliki Token Aktivasi Sekali Pakai.")
        reg_email = st.text_input("Masukkan Email Anda:", key="reg_em")
        reg_password = st.text_input("Buat Kata Sandi Baru (Min. 6 Karakter):", type="password", key="reg_pw")
        input_token = st.text_input("Masukkan Token Aktivasi Pembelian Anda:", type="password", key="reg_token")

        if st.button("Aktifkan Akun Saya"):
            if supabase is None:
                st.error("Sistem pangkalan data terputus.")
            elif not reg_email or len(reg_password) < 6 or not input_token:
                st.warning("Mohon isi seluruh kolom email, kata sandi, dan token aktivasi!")
            else:
                try:
                    # JALUR MASTER 1: Jika Mas yang mendaftar pertama kali
                    if reg_email.strip().lower() == EMAIL_OWNER_UTAMA.lower() and input_token.strip() == TOKEN_SUPER_ADMIN:
                        supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        st.success("👑 Selamat Datang Super Admin! Akun berhasil diaktifkan secara instan. Silakan masuk via tab Login.")

                    # JALUR KOMERSIAL 2: Untuk Pembeli (Wajib Validasi dan Hanguskan Token)
                    else:
                        token_query = supabase.table("activation_tokens").select("is_used").eq("token_code", input_token.strip()).execute()

                        if len(token_query.data) == 0:
                            st.error("❌ Token Aktivasi Tidak Valid! Periksa kembali kode kupon Anda.")
                        elif token_query.data[0]["is_used"] == True:
                            st.error("❌ Token Akses Gagal! Token ini sudah hangus karena telah digunakan oleh pembeli lain.")
                        else:
                            # Daftarkan pembeli ke database
                            supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                            # Hanguskan token detik itu juga agar tidak bisa dipakai email lain
                            supabase.table("activation_tokens").update({"is_used": True}).eq("token_code", input_token.strip()).execute()
                            st.success("🎉 Aktivasi Sukses! Token Anda resmi dihanguskan. Silakan pindah ke tab 'Masuk (Login)' untuk mengunci 2 perangkat pertama Anda.")
                except Exception as reg_err:
                    st.error(f"❌ Pendaftaran Gagal: Email mungkin sudah terdaftar. ({str(reg_err)})")

    st.stop()  # Mengunci script sisa ke bawah

# ==============================================================================
# 3. ANTARMUKA UTAMA (SETELAH USER BERHASIL LOGIN)
# ==============================================================================

col_user_info, col_logout_act = st.columns(2)
with col_user_info:
    st.write(f"👤 Pengguna Aktif: **{st.session_state.user_email}**")
with col_logout_act:
    if st.button("🚪 Keluar"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.cleaned_df = None
        st.session_state.extracted_text = ""
        st.session_state.ai_report = ""
        st.rerun()

st.title("Business Insight AI 📊")
st.caption("Aplikasi Analisis Finansial Otomatis untuk UKM, Akuntan, Auditor, & Investor")

# ==============================================================================
# 4. FILTER UPLOAD & ENGINES PEMBERSIH DATA TABULAR/PDF (ANTI-CRASH LOGIC)
# ==============================================================================

uploaded_file = st.file_uploader(
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

# ==============================================================================
# 5. DASHBOARD GRAFIK TREN KEUANGAN RESPONSIVE (PLOTLY ENGINE)
# ==============================================================================

if st.session_state.cleaned_df is not None:
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
            fig.update_layout(margin=dict(l=15, r=15, t=40, b=15))  # Pembatasan margin super ketat untuk HP
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Gagal memetakan grafik visual: {str(e)}")
    else:
        st.warning(f"⚠️ Kolom '{col_y}' terdeteksi bukan berupa deret data angka. Silakan pilih opsi kolom angka lain agar grafik tren muncul.")

# ==============================================================================
# 6. ENGINES INTEGRASI INTEGRITAS GOOGLE GEMINI 2.5 API (HTTP CORE PROCESSING)
# ==============================================================================

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
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"

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
                    2. ANALISIS ARUS KAS (CASH FLOW)
                    3. PREDIKSI KEBANGRUTAN (ALTMAN Z-SCORE)
                    4. DETEKSI ANOMALI DAN RISIKO KECURANGAN
                    5. REKOMENDASI STRATEGI BISNIS TAKTIS
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
    st.info("💡 Petunjuk Penggunaan: Silakan unggah berkas data laporan keuangan Anda di atas untuk membuka dasbor tren grafik visual dan menyusun laporan intelijen AI otomatis.")
```
