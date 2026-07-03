import streamlit as st
import pandas as pd
from datetime import datetime, date
import yfinance as yf
import plotly.express as px
import gspread

# ==========================================
# 1. GOOGLE SHEETS VERİTABANI BAĞLANTISI
# ==========================================
# Senin oluşturduğumuz benzersiz Excel dosyasının ID'si[cite: 1]
SHEET_ID = "1zYEn7zcg6x-dVsYBsl-QNiL-los_BtXr2FY11SCiaNM"

@st.cache_resource
def google_sheets_baglan():
    # Streamlit'in gizli kasasından anahtarı çek
    s_creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(s_creds)
    return gc.open_by_key(SHEET_ID).sheet1

sheet = google_sheets_baglan()

def verileri_yukle():
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Tarih", "İşlem_Tipi", "Hisse", "Lot", "Fiyat_Tutar"])
    return pd.DataFrame(data)

def islem_ekle(tarih, islem_tipi, hisse, lot, fiyat_tutar):
    yeni_satir = [
        tarih.strftime("%d.%m.%Y"),
        islem_tipi,
        hisse.upper(),
        float(lot) if lot else 0.0,
        float(fiyat_tutar) if fiyat_tutar else 0.0
    ]
    sheet.append_row(yeni_satir)

def veritabani_guncelle(df):
    sheet.clear()
    sheet.append_row(list(df.columns))
    if not df.empty:
        sheet.append_rows(df.values.tolist())

# ==========================================
# 2. YFINANCE FİYAT MOTORU (Günlük K/Z Uyumlu)
# ==========================================
def fiyatlari_getir(hisse_kodu):
    try:
        ticker_str = hisse_kodu if ".IS" in hisse_kodu or "^" in hisse_kodu else hisse_kodu + ".IS"
        ticker = yf.Ticker(ticker_str)
        veri = ticker.history(period="5d")
        
        if not veri.empty and len(veri) >= 2:
            bugun = float(veri['Close'].iloc[-1])
            dun = float(veri['Close'].iloc[-2])
            return bugun, dun
        elif not veri.empty and len(veri) == 1:
            bugun = float(veri['Close'].iloc[-1])
            return bugun, bugun 
    except:
        pass
    return 0.0, 0.0

# ==========================================
# 3. SAYFA TEMEL AYARLARI VE YÜKLEME
# ==========================================
st.set_page_config(page_title="PARA - Portföy", layout="wide", page_icon="💸")

# Veriyi Google Sheets'ten canlı çek
df_islem_defteri = verileri_yukle()

# ==========================================
# 4. YAN MENÜ (Dinamik İşlem Paneli)
# ==========================================
st.sidebar.header("➕ Yeni İşlem Ekle")

islem_tipi = st.sidebar.selectbox("İşlem Tipi", ["Alış", "Satış", "Temettü", "Bölünme"])
islem_tarihi = st.sidebar.date_input("İşlem Tarihi", date.today())
hisse_kodu = st.sidebar.text_input("Hisse Kodu (Örn: ASELS)")

lot_miktari = None
islem_fiyati = None

if islem_tipi in ["Alış", "Satış"]:
    lot_miktari = st.sidebar.number_input("Lot Sayısı", min_value=0.0, step=1.0, value=None)
    islem_fiyati = st.sidebar.number_input("İşlem Fiyatı (TL)", min_value=0.0, step=0.01, value=None)
elif islem_tipi == "Temettü":
    islem_fiyati = st.sidebar.number_input("Alınan Toplam Nakit Temettü (TL)", min_value=0.0, step=1.0, value=None)
elif islem_tipi == "Bölünme":
    lot_miktari = st.sidebar.number_input("Bedelsiz Gelen Ekstra Lot Sayısı", min_value=0.0, step=1.0, value=None)

if st.sidebar.button("Portföye Ekle"):
    if hisse_kodu:
        if (islem_tipi in ["Alış", "Satış"] and lot_miktari is not None and islem_fiyati is not None) or \
           (islem_tipi == "Temettü" and islem_fiyati is not None) or \
           (islem_tipi == "Bölünme" and lot_miktari is not None):
            
            islem_ekle(islem_tarihi, islem_tipi, hisse_kodu, lot_miktari, islem_fiyati)
            st.sidebar.success(f"{islem_tipi} işlemi Google Sheets'e başarıyla kaydedildi!")
            st.rerun()
        else:
            st.sidebar.error("Lütfen zorunlu alanları doldurun.")
    else:
        st.sidebar.error("Lütfen Hisse Kodu girin.")

st.sidebar.markdown("---")
st.sidebar.header("🧨 Tüm Portföyü Temizle")
silme_onayi = st.sidebar.checkbox("Tüm verileri silmeyi onaylıyorum")
if st.sidebar.button("Portföyü Tamamen Temizle", disabled=not silme_onayi):
    df_bos = pd.DataFrame(columns=["Tarih", "İşlem_Tipi", "Hisse", "Lot", "Fiyat_Tutar"])
    veritabani_guncelle(df_bos)
    st.rerun()

# ==========================================
# 5. AKILLI HESAPLAMA MOTORU (Midas Uyumlu)
# ==========================================
portfoy_listesi = []
toplam_alinan_temettu = 0.0

if not df_islem_defteri.empty:
    for hisse in df_islem_defteri["Hisse"].unique():
        df_hisse = df_islem_defteri[df_islem_defteri["Hisse"] == hisse]
        
        toplam_lot = 0.0
        toplam_yatirilan = 0.0
        
        for idx, row in df_hisse.iterrows():
            tip = row["İşlem_Tipi"]
            # Google Sheets'ten gelen değerleri temizleyip floata çevir
            lot = float(str(row["Lot"]).replace(',', '.'))
            deger = float(str(row["Fiyat_Tutar"]).replace(',', '.'))
            
            if tip == "Alış":
                toplam_lot += lot
                toplam_yatirilan += (lot * deger)
            elif tip == "Satış":
                if toplam_lot > 0:
                    ort_maliyet = toplam_yatirilan / toplam_lot
                    toplam_lot -= lot
                    toplam_yatirilan -= (lot * ort_maliyet)
                    if toplam_lot <= 0:
                        toplam_lot = 0.0
                        toplam_yatirilan = 0.0
            elif tip == "Temettü":
                toplam_alinan_temettu += deger
            elif tip == "Bölünme":
                toplam_lot += lot
                
        if toplam_lot > 0:
            ort_maliyet = toplam_yatirilan / toplam_lot
            portfoy_listesi.append({
                "Hisse": hisse,
                "Lot": toplam_lot,
                "Brut_Yatirilan": toplam_yatirilan,
                "Maliyet": ort_maliyet
            })

df_portfoy = pd.DataFrame(portfoy_listesi)

# ==========================================
# 6. CANLI FİYAT VE GÜNLÜK K/Z HESAPLAMASI
# ==========================================
toplam_portfoy_degeri = 0.0
brut_ana_para_toplami = 0.0
gunluk_kar_zarar_toplami = 0.0

if not df_portfoy.empty:
    guncel_fiyatlar = []
    toplam_degerler = []
    kar_zarar_oranlari = []
    kar_zarar_tutar = []

    for index, row in df_portfoy.iterrows():
        bugun_fiyat, dun_fiyat = fiyatlari_getir(row["Hisse"])
        
        guncel_fiyatlar.append(bugun_fiyat)
        toplam_deger = bugun_fiyat * row["Lot"]
        toplam_degerler.append(toplam_deger)
        
        gunluk_kar_zarar_toplami += (bugun_fiyat - dun_fiyat) * row["Lot"]
        
        ana_para = row["Brut_Yatirilan"]
        brut_ana_para_toplami += ana_para
        toplam_portfoy_degeri += toplam_deger
        
        if row["Maliyet"] > 0 and bugun_fiyat > 0:
            oran = ((bugun_fiyat - row["Maliyet"]) / row["Maliyet"]) * 100
            tutar = toplam_deger - ana_para
        else:
            oran = 0.0
            tutar = 0.0
            
        kar_zarar_oranlari.append(oran)
        kar_zarar_tutar.append(tutar)

    df_portfoy["Anlık Fiyat"] = guncel_fiyatlar
    df_portfoy["Toplam Değer"] = toplam_degerler
    df_portfoy["K/Z (%)"] = kar_zarar_oranlari
    df_portfoy["K/Z (Tutar)"] = kar_zarar_tutar

# ==========================================
# 7. ÜST KISIM (Başlık ve 6'lı KPI Paneli)
# ==========================================
col_baslik, col_sayac = st.columns([3, 1])
with col_baslik:
    st.title("💸 PARA - Portföy Yönetim Merkezi")
with col_sayac:
    st.write(f"**Tarih:** {date.today().strftime('%d.%m.%Y')}")

st.markdown("---")

net_ana_para = brut_ana_para_toplami - toplam_alinan_temettu
genel_kar_zarar_tutari = toplam_portfoy_degeri - net_ana_para
genel_kar_zarar_yuzdesi = (genel_kar_zarar_tutari / net_ana_para * 100) if net_ana_para > 0 else 0.0

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
kpi1.metric(label="Toplam Portföy", value=f"{toplam_portfoy_degeri:,.2f} ₺")
kpi2.metric(label="Günlük K/Z", value=f"{gunluk_kar_zarar_toplami:,.2f} ₺", delta=f"{gunluk_kar_zarar_toplami:,.2f} ₺")
kpi3.metric(label="Net Kâr/Zarar", value=f"{genel_kar_zarar_tutari:,.2f} ₺", delta=f"{genel_kar_zarar_tutari:,.2f} ₺")
kpi4.metric(label="Genel Getiri (%)", value=f"% {genel_kar_zarar_yuzdesi:.2f}", delta=f"{genel_kar_zarar_yuzdesi:.2f} %")
kpi5.metric(label="Cebimden Çıkan", value=f"{net_ana_para:,.2f} ₺")
kpi6.metric(label="Toplam Temettü", value=f"{toplam_alinan_temettu:,.2f} ₺")

st.markdown("---")

# ==========================================
# 8. SEKMELER (TABS)
# ==========================================
tab_ana_ekran, tab_hisse_detay = st.tabs(["📊 Ana Portföy", "🔍 Hisse Detay ve İşlem Geçmişi"])

with tab_ana_ekran:
    col_tablo, col_grafik = st.columns([2, 1])

    with col_tablo:
        st.subheader("📊 Birleştirilmiş Ana Portföy")
        if df_portfoy.empty:
            st.info("Henüz sisteme hisse eklenmedi.")
        else:
            def renk_ver(val):
                if isinstance(val, (int, float)):
                    if val > 0: return 'color: #00ff00'
                    elif val < 0: return 'color: #ff4b4b'
                return 'color: gray'

            gosterilecek_df = df_portfoy.drop(columns=["Brut_Yatirilan"])
            st.dataframe(
                gosterilecek_df.style.format({
                    "Lot": "{:,.2f}",
                    "Maliyet": "{:,.2f} ₺",
                    "Anlık Fiyat": "{:,.2f} ₺",
                    "Toplam Değer": "{:,.2f} ₺",
                    "K/Z (%)": "% {:,.2f}",
                    "K/Z (Tutar)": "{:,.2f} ₺"
                }).map(renk_ver, subset=['K/Z (%)', 'K/Z (Tutar)']),
                use_container_width=True, 
                hide_index=True
            )

    with col_grafik:
        st.subheader("🥧 Portföy Dağılımı")
        if not df_portfoy.empty and sum(toplam_degerler) > 0:
            fig = px.pie(df_portfoy, values='Toplam Değer', names='Hisse', hole=0.4)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("⚡ Anlık Bildirimler ve Analizler (Gemini AI)")
    st.caption("Sadece portföyünüzdeki hisselere ait önemli piyasa olayları")
    
    ornek_haberler = [
        {"hisse": "ASELS", "tip": "olumlu", "mesaj": "15 Milyon dolarlık yeni savunma sanayi sözleşmesi imzalandı."},
        {"hisse": "ASTOR", "tip": "notr", "mesaj": "Genel kurul toplantı tarihi 15 Ağustos 2026 olarak duyuruldu."},
        {"hisse": "TUPRS", "tip": "olumsuz", "mesaj": "Küresel petrol fiyatlarındaki düşüş sebebiyle marjlarda daralma sinyali."}
    ]
    
    for haber in ornek_haberler:
        if haber["tip"] == "olumlu": st.success(f"🟢 **{haber['hisse']}** - {haber['mesaj']}")
        elif haber["tip"] == "olumsuz": st.error(f"🔴 **{haber['hisse']}** - {haber['mesaj']}")
        else: st.info(f"⚪ **{haber['hisse']}** - {haber['mesaj']}")

with tab_hisse_detay:
    st.subheader("🔍 Hisse Röntgeni ve İşlem Geçmişi")
    
    if df_islem_defteri.empty:
        st.info("Sistemde incelenecek hisse işlemi bulunmuyor.")
    else:
        secilen_hisse = st.selectbox("İncelemek istediğiniz hisseyi seçin:", df_islem_defteri["Hisse"].unique())
        hisse_gecmisi = df_islem_defteri[df_islem_defteri["Hisse"] == secilen_hisse]
        
        # O hissenin temettülerini toplarken floata çevir
        hisse_ozel_temettu = sum(float(str(val).replace(',', '.')) for val in hisse_gecmisi[hisse_gecmisi["İşlem_Tipi"] == "Temettü"]["Fiyat_Tutar"])
        
        st.markdown(f"### 📖 {secilen_hisse} İşlem Özeti")
        if hisse_ozel_temettu > 0:
            st.info(f"💰 **BİLGİ:** {secilen_hisse} hissesinden bugüne kadar toplam **{hisse_ozel_temettu:,.2f} ₺** nakit temettü geliri elde ettiniz.")
        
        st.dataframe(hisse_gecmisi, use_container_width=True, hide_index=False)
        
        st.markdown("---")
        st.markdown("### 🗑️ Hatalı İşlemi Sil")
        with st.form("tekil_silme_formu"):
            st.write("Silmek istediğiniz işlemin detaylarını aşağıdan seçin:")
            silinecek_secenekler = []
            for idx, row in hisse_gecmisi.iterrows():
                etiket = f"ID: {idx} | {row['Tarih']} - {row['İşlem_Tipi']} - {row['Lot']} Lot"
                silinecek_secenekler.append(etiket)
                
            secilen_silinecek = st.selectbox("Silinecek İşlem:", silinecek_secenekler)
            tek_sil_butonu = st.form_submit_button("Seçili İşlemi Kalıcı Olarak Sil")
            
            if tek_sil_butonu and secilen_silinecek:
                silinecek_id = int(secilen_silinecek.split("|")[0].replace("ID:", "").strip())
                df_islem_defteri = df_islem_defteri.drop(index=silinecek_id)
                veritabani_guncelle(df_islem_defteri)
                st.success("İşlem Excel'den başarıyla silindi!")
                st.rerun()
