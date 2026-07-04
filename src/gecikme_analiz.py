import pandas as pd
import geopandas as gpd
import seaborn as sns
import matplotlib.pyplot as plt

# ============================================================
# 1. DOSYALARI OKU (5'ten 8'e çıkarıldı)
# ============================================================
customers = pd.read_csv("data/olist_customers_dataset.csv")
orders = pd.read_csv("data/olist_orders_dataset.csv")
order_items = pd.read_csv("data/olist_order_items_dataset.csv")
products = pd.read_csv("data/olist_products_dataset.csv")
category_trans = pd.read_csv("data/product_category_name_translation.csv")

# --- YENİ EKLENEN 3 VERİ SETİ ---
geolocation = pd.read_csv("data/olist_geolocation_dataset.csv")
sellers = pd.read_csv("data/olist_sellers_dataset.csv")
reviews = pd.read_csv("data/olist_order_reviews_dataset.csv")

# ============================================================
# 2. BİRLEŞTİRMELER
# ============================================================
df = pd.merge(customers, orders, on="customer_id")
df_items = pd.merge(df, order_items, on="order_id")
df_items = pd.merge(df_items, products, on="product_id")
df_items = pd.merge(df_items, category_trans, on="product_category_name")

# Satıcı bilgisini ekle (seller_state, seller_city, seller_zip_code_prefix gelir)
df_items = pd.merge(df_items, sellers, on="seller_id", how="left")

# Değerlendirme (review) bilgisini ekle -> bir siparişte birden fazla review olabilir, ilkini al
reviews_unique = reviews.drop_duplicates(subset="order_id", keep="first")
df_items = pd.merge(
    df_items, reviews_unique[["order_id", "review_score"]], on="order_id", how="left"
)

# ============================================================
# 3. TARİH SÜTUNLARINI ÇEVİR
# ============================================================
df_items["order_purchase_timestamp"] = pd.to_datetime(df_items["order_purchase_timestamp"])
df_items["order_delivered_customer_date"] = pd.to_datetime(df_items["order_delivered_customer_date"])
df_items["order_estimated_delivery_date"] = pd.to_datetime(df_items["order_estimated_delivery_date"])

# ============================================================
# 4. SADECE TESLİM EDİLMİŞ SİPARİŞLER
# ============================================================
df_teslim = df_items[df_items["order_status"] == "delivered"].copy()

# ============================================================
# 5. GECİKME HESAPLAMALARI
# ============================================================
df_teslim["gercek_teslimat"] = (
    df_teslim["order_delivered_customer_date"] - df_teslim["order_purchase_timestamp"]
).dt.days
df_teslim["tahmini_teslimat"] = (
    df_teslim["order_estimated_delivery_date"] - df_teslim["order_purchase_timestamp"]
).dt.days
df_teslim["gecikme_gun"] = df_teslim["gercek_teslimat"] - df_teslim["tahmini_teslimat"]
df_teslim["gecikti_mi"] = df_teslim["gecikme_gun"] > 0

# ============================================================
# 6. EYALET BAZINDA GECİKME (mevcut analiz)
# ============================================================
eyalet_gecikme = df_teslim.groupby("customer_state")["gecikti_mi"].agg(
    toplam_siparis="count",
    geciken="sum",
    gecikme_orani="mean"
).sort_values("gecikme_orani", ascending=False)

eyalet_gecikme["gecikme_orani"] = (eyalet_gecikme["gecikme_orani"] * 100).round(1)

en_kotu = eyalet_gecikme.head(10).reset_index().sort_values("gecikme_orani")
plt.figure()
sns.barplot(data=en_kotu, x="gecikme_orani", y="customer_state", color="tomato")
plt.title("En Yüksek Gecikme Oranlı 10 Eyalet (%)")
plt.tight_layout()
plt.savefig("reports/grafikler/eyalet_gecikme_sns.png")
plt.close()
print("Bar grafik kaydedildi.")

eyalet_teslimat = df_teslim.groupby("customer_state")["gercek_teslimat"].agg(
    ortalama_gun="mean", en_hizli="min", en_yavas="max"
).round(1).reset_index()

kategori_gecikme = df_teslim.groupby("product_category_name_english")["gecikti_mi"].agg(
    toplam="count",
    geciken="sum",
    gecikme_orani="mean"
).round(3)
kategori_gecikme["gecikme_orani"] = (kategori_gecikme["gecikme_orani"] * 100).round(1)
kategori_gecikme = kategori_gecikme.sort_values("gecikme_orani", ascending=False).reset_index()

print("\n=== KATEGORİYE GÖRE GECİKME ===")
print(kategori_gecikme.head(10))

# ============================================================
# 7. YENİ ANALİZ: SATICI (SELLER) EYALETİNE GÖRE GECİKME
# ============================================================
satici_gecikme = df_teslim.groupby("seller_state")["gecikti_mi"].agg(
    toplam_siparis="count",
    geciken="sum",
    gecikme_orani="mean"
).round(3)
satici_gecikme["gecikme_orani"] = (satici_gecikme["gecikme_orani"] * 100).round(1)
satici_gecikme = satici_gecikme.sort_values("gecikme_orani", ascending=False).reset_index()

print("\n=== SATICI EYALETİNE GÖRE GECİKME ===")
print(satici_gecikme.head(10))

# ============================================================
# 8. YENİ ANALİZ: GECİKME İLE MEMNUNİYET (REVIEW) İLİŞKİSİ
# ============================================================
review_gecikme = df_teslim.groupby("gecikti_mi")["review_score"].agg(
    ortalama_puan="mean",
    adet="count"
).round(2).reset_index()
review_gecikme["gecikti_mi"] = review_gecikme["gecikti_mi"].map({True: "Geciken", False: "Zamanında"})

print("\n=== GECİKME DURUMUNA GÖRE ORTALAMA PUAN ===")
print(review_gecikme)

# ============================================================
# 9. GEOPANDAS ISI HARİTASI #1 - EYALET BAZINDA GECİKME (CHOROPLETH)
# ============================================================
# NOT: Brezilya eyalet sınırlarını içeren bir GeoJSON dosyasına ihtiyacın var.
# Bir kere indirip data/ klasörüne "brazil_states.geojson" adıyla koyman yeterli:
# https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson
brazil_states = gpd.read_file("data/brazil_states.geojson")

# Bu GeoJSON'da eyalet kodu genelde "sigla" sütununda olur.
# Farklıysa brazil_states.columns ile kontrol edip burada değiştir.
harita_verisi = brazil_states.merge(
    eyalet_gecikme.reset_index(),
    left_on="sigla",
    right_on="customer_state",
    how="left"
)

fig, ax = plt.subplots(1, 1, figsize=(10, 10))
harita_verisi.plot(
    column="gecikme_orani",
    cmap="OrRd",
    linewidth=0.6,
    edgecolor="grey",
    legend=True,
    legend_kwds={"label": "Gecikme Oranı (%)"},
    ax=ax,
    missing_kwds={"color": "lightgrey"}
)
ax.set_title("Eyalet Bazında Teslimat Gecikme Oranı (%)", fontsize=14)
ax.axis("off")
plt.tight_layout()
plt.savefig("reports/grafikler/eyalet_gecikme_isi_haritasi.png", dpi=150)
plt.close()
print("Choropleth ısı haritası kaydedildi.")

# ============================================================
# 10. GEOPANDAS ISI HARİTASI #2 - NOKTA BAZLI GECİKME YOĞUNLUĞU
# ============================================================
# Her zip code prefix için ortalama koordinat çıkar (geolocation verisi burada devreye giriyor)
geo_ortalama = geolocation.groupby("geolocation_zip_code_prefix").agg(
    lat=("geolocation_lat", "mean"),
    lng=("geolocation_lng", "mean")
).reset_index()

musteri_konum = pd.merge(
    df_teslim,
    geo_ortalama,
    left_on="customer_zip_code_prefix",
    right_on="geolocation_zip_code_prefix",
    how="left"
).dropna(subset=["lat", "lng"])

# Brezilya için yaklaşık sınır kutusu dışındaki hatalı koordinatları temizle
musteri_konum = musteri_konum[
    musteri_konum["lat"].between(-35, 6) & musteri_konum["lng"].between(-75, -32)
]

gdf_noktalar = gpd.GeoDataFrame(
    musteri_konum,
    geometry=gpd.points_from_xy(musteri_konum["lng"], musteri_konum["lat"]),
    crs="EPSG:4326"
)

fig, ax = plt.subplots(1, 1, figsize=(10, 10))
brazil_states.boundary.plot(ax=ax, color="grey", linewidth=0.5)
hb = ax.hexbin(
    gdf_noktalar.geometry.x,
    gdf_noktalar.geometry.y,
    C=gdf_noktalar["gecikti_mi"].astype(int),
    reduce_C_function=lambda x: (sum(x) / len(x)) * 100 if len(x) > 0 else 0,
    gridsize=40,
    cmap="OrRd",
    mincnt=5
)
plt.colorbar(hb, ax=ax, label="Gecikme Oranı (%)")
ax.set_title("Sipariş Konumuna Göre Gecikme Yoğunluk Haritası", fontsize=14)
ax.axis("off")
plt.tight_layout()
plt.savefig("reports/grafikler/gecikme_yogunluk_haritasi.png", dpi=150)
plt.close()
print("Nokta bazlı yoğunluk haritası kaydedildi.")

# ============================================================
# 11. GENEL İSTATİSTİK ÖZETİ
# ============================================================
puan_zamaninda = review_gecikme.loc[review_gecikme["gecikti_mi"] == "Zamanında", "ortalama_puan"].values[0]
puan_geciken = review_gecikme.loc[review_gecikme["gecikti_mi"] == "Geciken", "ortalama_puan"].values[0]

genel_istatistik = pd.DataFrame({
    "Metrik": [
        "Toplam Sipariş",
        "Teslim Edilen",
        "Geciken Sipariş",
        "Gecikme Oranı (%)",
        "Ortalama Teslimat (Gün)",
        "Ortalama Puan (Zamanında Teslimat)",
        "Ortalama Puan (Geciken Teslimat)"
    ],
    "Değer": [
        len(df_items),
        len(df_teslim),
        int(df_teslim["gecikti_mi"].sum()),
        round(df_teslim["gecikti_mi"].mean() * 100, 1),
        round(df_teslim["gercek_teslimat"].mean(), 1),
        puan_zamaninda,
        puan_geciken
    ]
})

# ============================================================
# 12. EXCEL RAPORU (yeni sheet'lerle)
# ============================================================
with pd.ExcelWriter("reports/olist_rapor.xlsx") as writer:
    genel_istatistik.to_excel(writer, sheet_name="Genel Ozet", index=False)
    eyalet_gecikme.to_excel(writer, sheet_name="Eyalet Gecikme", index=True)
    eyalet_teslimat.to_excel(writer, sheet_name="Eyalet Teslimat", index=False)
    kategori_gecikme.to_excel(writer, sheet_name="Kategori Gecikme", index=False)
    satici_gecikme.to_excel(writer, sheet_name="Satici Gecikme", index=False)
    review_gecikme.to_excel(writer, sheet_name="Gecikme-Memnuniyet", index=False)

print("\nRapor ve tüm grafikler başarıyla oluşturuldu.")
