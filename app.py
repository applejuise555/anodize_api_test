import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import math
from plotly.subplots import make_subplots
import time
import numpy as np

ICT = timezone(timedelta(hours=7))
st.set_page_config(page_title="Gissco Production Line and Dashboard", layout="wide")

# ================= CONFIG =================
COLOR_HEX_MAP = {
    "Black": "#000000", "Red": "#FF0000", "Dark Red": "#8B0000", 
    "Violet": "#9400D3", "Green": "#008000", "Banana leaf Green": "#90EE90", 
    "Gold": "#FFD700", "Orange": "#FFA500", "Light Blue": "#ADD8E6", 
    "Blue": "#0000FF", "Dark Blue": "#00008B", "Pink": "#FFC0CB", 
    "Copper": "#B87333", "Titanium": "#808080", "Dark Titanium": "#4A4E69", 
    "Rose Gold": "#B76E79"
}

TANK_COLOR_MAP = {
    "4DarkBlue": "Dark Blue", "16Blue": "Blue", "1DarkRedA": "Dark Red",
    "1DarkRedB": "Dark Red", "19Copper": "Copper", "12Titanium": "Titanium",
    "13DarkTitanium": "Dark Titanium", "14RoseGold": "Rose Gold",
    "6BananaLeafGreen": "Banana leaf Green", "10LightBlue": "Light Blue",
    "18OrangeOil": "Orange", "9Orange": "Orange", "15Gold": "Gold",
    "11Gold": "Gold", "17Black": "Black", "21Black": "Black",
    "5Black": "Black", "20Black": "Black", "7Pink": "Pink",
    "8Green": "Green", "3Violet": "Violet", "2Red": "Red",
    "HotSealH60": "Black"
}

# ================= DB =================
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# ================= NEW FUNCTIONS =================
def validate_color_input(ph, temp):
    if ph < 0 or ph > 14:
        st.error("❌ pH ต้อง 0-14")
        return False
    if temp < 0 or temp > 100:
        st.error("❌ Temp ผิดปกติ")
        return False
    return True

def validate_ano_input(ph, temp, den):
    if ph < 0 or ph > 5:
        st.error("❌ pH Anodize ผิดช่วง")
        return False
    if den < 0:
        st.error("❌ Density ห้ามติดลบ")
        return False
    return True

def add_trend(df, col):
    if len(df) < 3: return df
    x = np.arange(len(df))
    coef = np.polyfit(x, df[col], 1)
    df[col+"_trend"] = np.poly1d(coef)(x)
    return df

def insight(df, col, name):
    if len(df) < 5: return
    diff = df[col].diff().mean()
    if diff > 0.05:
        st.warning(f"📈 {name} เพิ่มขึ้น")
    elif diff < -0.05:
        st.info(f"📉 {name} ลดลง")

def export_csv(df, name):
    st.download_button("📥 Export CSV", df.to_csv(index=False), name)

def get_options(table, id_col, name_col, filter_col=None, filter_val=None):
    query = supabase.table(table).select(f"{id_col},{name_col}")
    if filter_col:
        query = query.eq(filter_col, filter_val)
    res = query.execute()
    return {i[name_col]: i[id_col] for i in res.data}

def get_status_icon(value, min_val, max_val):
    if value < min_val or value > max_val:
        return "🔴"
    return "🟢"

# ================= MENU =================
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต"])

# ================= DASHBOARD =================
if menu == "Dashboard":
    st.title("📊 Production Dashboard")

    PH_MIN, PH_MAX = 5, 6
    TEMP_MIN, TEMP_MAX = 30, 40

    @st.cache_data(ttl=10)
    def load_color():
        today = datetime.now(ICT).date().isoformat()
        return supabase.table("color_tank_logs")\
            .select("*").gte("recorded_at", today)\
            .order("recorded_at", desc=True).limit(200).execute().data

    logs = load_color()

    if logs:
        df = pd.DataFrame(logs)

        # KPI
        st.subheader("📊 KPI")
        col1, col2 = st.columns(2)
        col1.metric("จำนวน Log วันนี้", len(df))

        out_spec = df[(df["ph_value"]<PH_MIN)|(df["ph_value"]>PH_MAX)]
        percent = (len(out_spec)/len(df))*100
        col2.metric("% นอก Spec", f"{percent:.1f}%")

        # ALERT TABLE
        st.subheader("🚨 Alert")
        alert = []
        for _, r in df.iterrows():
            alert.append({
                "pH": f"{get_status_icon(r['ph_value'],PH_MIN,PH_MAX)} {r['ph_value']}"
            })
        alert_df = pd.DataFrame(alert)
        st.dataframe(alert_df)
        export_csv(alert_df, "alert.csv")

        # TREND
        st.subheader("📈 Trend")
        df = add_trend(df, "ph_value")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["recorded_at"], y=df["ph_value"], name="Actual"))
        fig.add_trace(go.Scatter(x=df["recorded_at"], y=df["ph_value_trend"], name="Trend"))
        st.plotly_chart(fig)

        insight(df, "ph_value", "pH")

# ================= RECORD =================
else:
    st.title("📝 บันทึกข้อมูล")

    ph = st.number_input("pH")
    temp = st.number_input("Temp")

    if st.button("บันทึก"):
        if validate_color_input(ph, temp):
            supabase.table("color_tank_logs").insert({
                "ph_value": ph,
                "temperature": temp,
                "recorded_at": datetime.now(ICT).isoformat()
            }).execute()
            st.success("บันทึกสำเร็จ")
