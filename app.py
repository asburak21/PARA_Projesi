import streamlit as st
import pandas as pd
from datetime import datetime, date
import yfinance as yf
import plotly.express as px
import gspread

# ==========================================
# 1. GOOGLE SHEETS VERİTABANI
# ==========================================
SHEET_ID = "1zYEn7zcg6x-dVsYBsl-QNiL-los_BtXr2FY11SCiaNM"

@st.cache_resource
def google_sheets_baglan():
    s_creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(s_creds)
    return gc.open_by_key(SHEET_ID).sheet1

sheet = google_sheets_baglan()

def verileri_yukle():
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Tarih", "İşlem_Tipi", "Hisse", "Lot", "Fiyat_Tutar"])
    df = pd.DataFrame(data)
    # Veriyi yüklerken hata payı bırakmadan temizle
    df["Lot"] = pd.to_numeric(df["Lot"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    df["Fiyat_Tutar"] = pd.to_numeric(df["Fiyat_Tutar"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    return df

def islem_ekle(tarih, islem_tipi, hisse, lot, fiyat_tutar):
    # Excel'e gönderirken string değil, sayısal formatta bırakıyoruz
    yeni_satir = [
        tarih.strftime("%d.%m.%Y"),
        islem_tipi,
        hisse.upper(),
        float(lot),
        float(fiyat_tutar)
    ]
    sheet.append_row(yeni_satir)

def veritabani_guncelle(df):
    sheet.clear()
    sheet.append_row(["Tarih", "İşlem_Tipi", "Hisse", "Lot", "Fiyat_Tutar"])
    if not df.empty:
        sheet.append_rows(df.values.tolist())

# ==========================================
# 2. HESAPLAMA MOTORU (Pürüzsüz)
# ==========================================
st.set_page_config(page_title="PARA - Portföy", layout="wide", page_icon="💸")
df_islem_defteri = verileri_yukle()

# ==========================================
# 3. YAN MENÜ (Formatlandırılmış)
# ==========================================
st.sidebar.header("➕ Yeni İşlem Ekle")
islem_tipi = st.sidebar.selectbox("İşlem Tipi", ["Alış", "Satış", "Temettü", "Bölünme"])
islem_tarihi = st.sidebar.date_input("İşlem Tarihi", date.today())
hisse_kodu = st.sidebar.text_input("Hisse Kodu (Örn: ASELS)")

# format eklemedik, bırak değerleri düzgün alsın
lot_miktari = st.sidebar.number_input("Lot Sayısı", min_value=0.0, step=0.01)
islem_fiyati = st.sidebar.number_input("Fiyat / Tutar", min_value=0.0, step=0.01)

if st.sidebar.button("Portföye Ekle"):
    islem_ekle(islem_tarihi, islem_tipi, hisse_kodu, lot_miktari, islem_fiyati)
    st.rerun()

# ==========================================
# 4. GÖRÜNTÜLEME (Hata Payı Yok)
# ==========================================
st.title("💸 PARA - Portföy")
if not df_islem_defteri.empty:
    st.dataframe(df_islem_defteri, use_container_width=True)
