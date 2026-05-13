import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import math
from plotly.subplots import make_subplots
import time
import streamlit as st
from streamlit_javascript import st_javascript
from streamlit_js_eval import streamlit_js_eval



# 1. ตั้งค่า Timezone (UTC +7)
ICT = timezone(timedelta(hours=7))
st.set_page_config(page_title="Gissco Production Line and Dashboard", layout="wide")

# --- Configuration ---
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

# --- เชื่อมต่อ Supabase ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        return None

supabase = init_connection()

# --- Helper Functions ---
def get_hex_from_name(name):
    sorted_colors = sorted(COLOR_HEX_MAP.keys(), key=len, reverse=True)
    name_lower = str(name).lower()
    for color_name in sorted_colors:
        if color_name.lower() in name_lower:
            return COLOR_HEX_MAP[color_name]
    return "#CCCCCC"

def render_color_bar(name):
    hex_code = get_hex_from_name(name)
    st.markdown(f"""
        <div style="background-color:{hex_code}; width:100%; height:20px; border-radius:5px; border: 1px solid #ccc; margin-bottom: 10px;"></div>
    """, unsafe_allow_html=True)

def get_options(table, id_col, name_col, filter_col=None, filter_val=None):
    if not supabase: return {}
    try:
        query = supabase.table(table).select(f"{id_col}, {name_col}")
        if filter_col and filter_val:
            query = query.eq(filter_col, filter_val)
        response = query.execute()
        return {item[name_col]: item[id_col] for item in response.data}
    except Exception:
        return {}

def get_status_icon(value, min_val, max_val, warn_margin=0.1):
    if value is None:
        return "⚪"
    if value < min_val or value > max_val:
        return "🔴"
    elif value < (min_val + warn_margin) or value > (max_val - warn_margin):
        return "🟡"
    return "🟢"

def get_quarter_range(year, quarter):
    # ไตรมาส 1: ม.ค. - มี.ค., 2: เม.ย. - มิ.ย., ...
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    # สร้างวันที่เริ่มต้นและสิ้นสุดของไตรมาส
    start_date = datetime(year, start_month, 1)
    if end_month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, end_month + 1, 1) - timedelta(days=1)
    return start_date, end_date


def render_tank_map():

    html = """
    <style>

    body{
        margin:0;
        padding:0;
    }

    .plant-map{
        position:relative;
        width:1100px;
        height:720px;
        background:#e9e9e9;
        border:2px solid #999;
        margin:auto;
        overflow:hidden;
    }

    .tank{
        position:absolute;
        color:white;
        font-weight:bold;
        font-size:14px;
        border-radius:4px;
        padding:4px;
        text-align:center;
        border:1px solid #555;
        box-sizing:border-box;
        font-family:Arial;
    }

    .vertical{
        writing-mode:vertical-rl;
        text-orientation:mixed;
    }

    .ro{
        background:#d7ffff !important;
        color:black !important;
    }

    </style>

    <div class="plant-map">

        <!-- TOP ROW -->

        <div class="tank"
            style="left:0px;top:0px;width:80px;height:80px;background:#111;">
            5.Black
        </div>

        <div class="tank"
            style="left:140px;top:0px;width:70px;height:80px;background:red;">
            2.Red
        </div>

        <div class="tank"
            style="left:210px;top:0px;width:60px;height:80px;background:purple;">
            3.Violet
        </div>

        <div class="tank"
            style="left:295px;top:0px;width:70px;height:80px;background:green;">
            8.Green
        </div>

        <div class="tank"
            style="left:365px;top:0px;width:65px;height:80px;background:#222;">
            17.Black
        </div>

        <div class="tank"
            style="left:455px;top:0px;width:70px;height:80px;background:#d4af00;color:black;">
            15.Gold
        </div>

        <div class="tank"
            style="left:525px;top:0px;width:65px;height:80px;background:orange;">
            9.Orange
        </div>

        <div class="tank"
            style="left:620px;top:0px;width:70px;height:80px;background:cyan;color:black;">
            10.Light Blue
        </div>

        <div class="tank"
            style="left:690px;top:0px;width:70px;height:80px;background:#7fff00;color:black;">
            6.Banana
        </div>

        <div class="tank"
            style="left:785px;top:0px;width:70px;height:80px;background:blue;">
            16.Blue
        </div>

        <div class="tank"
            style="left:855px;top:0px;width:65px;height:80px;background:darkblue;">
            4.Dark Blue
        </div>

        <!-- RO -->

        <div class="tank ro"
            style="left:140px;top:82px;width:130px;height:65px;">
            RO
        </div>

        <div class="tank ro"
            style="left:455px;top:82px;width:130px;height:65px;">
            RO
        </div>

        <div class="tank ro"
            style="left:785px;top:82px;width:130px;height:65px;">
            RO
        </div>

        <!-- CENTER -->

        <div class="tank vertical"
            style="left:0px;top:180px;width:60px;height:275px;background:#777;">
            AlmiteSealerLiquid
        </div>

        <div class="tank"
            style="left:270px;top:200px;width:80px;height:50px;background:#111;">
            20.Black
        </div>

        <div class="tank"
            style="left:270px;top:252px;width:80px;height:35px;background:darkred;">
            1.DarkRed
        </div>

        <div class="tank vertical"
            style="left:380px;top:210px;width:85px;height:130px;background:magenta;">
            7.Pink
        </div>

        <div class="tank"
            style="left:540px;top:190px;width:85px;height:130px;background:#777;">
            HotSeal
        </div>

        <div class="tank vertical"
            style="left:540px;top:325px;width:85px;height:120px;background:#d4af00;color:black;">
            11.Gold
        </div>

        <!-- RIGHT -->

        <div class="tank"
            style="left:785px;top:200px;width:65px;height:55px;background:darkred;">
            1.DarkRed
        </div>

        <div class="tank"
            style="left:785px;top:257px;width:65px;height:55px;background:#d9a27f;color:black;">
            19.Copper
        </div>

        <div class="tank"
            style="left:785px;top:314px;width:65px;height:55px;background:#777;">
            12.Titanium
        </div>

        <div class="tank"
            style="left:785px;top:371px;width:65px;height:55px;background:plum;">
            14.RoseGold
        </div>

        <!-- ANODIZE -->

        <div class="tank vertical"
            style="left:890px;top:520px;width:140px;height:190px;background:#ccc;color:black;">
            AnodizedPPool1
        </div>

        <!-- DARK TITANIUM -->

        <div class="tank"
            style="left:310px;top:120px;width:80px;height:40px;background:#666;">
            13.DarkTitanium
        </div>
        
        <div class="tank"
            style="left:390px;top:120px;width:80px;height:40px;background:#666;">
        </div>
        
        <!-- ORANGE OIL -->
        
        <div class="tank"
            style="left:625px;top:120px;width:80px;height:40px;background:#dd6600;">
            18.OrangeOil
        </div>
        
        <div class="tank"
            style="left:705px;top:120px;width:80px;height:40px;background:#dd6600;">
        </div>
        
        <!-- RO CENTER -->
        
        <div class="tank ro"
            style="left:380px;top:355px;width:85px;height:90px;">
            RO
        </div>
        
        <div class="tank ro"
            style="left:625px;top:190px;width:90px;height:125px;">
            RO
        </div>
        
        <div class="tank ro"
            style="left:625px;top:320px;width:90px;height:125px;">
            RO
        </div>
        
        <!-- RO RIGHT -->
        
        <div class="tank ro"
            style="left:850px;top:200px;width:85px;height:110px;">
            RO
        </div>
        
        <div class="tank ro"
            style="left:850px;top:312px;width:85px;height:114px;">
            RO
        </div>
        
        <div class="tank ro"
            style="left:990px;top:215px;width:85px;height:80px;">
            RO
        </div>

    </div>
    """

    st.html(f"""
    <div style="height:750px; overflow:hidden;">
        {html}
    </div>
    """)
#=================================================================   
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต"])

# ================= DASHBOARD (FULL SYSTEM VIEW) =================
if menu == "Dashboard":
    st.title("📊 Production Dashboard (System Overview)")

    # ================= STANDARD =================
    PH_MIN, PH_MAX = 5.0, 6.0
    TEMP_COLOR_MIN, TEMP_COLOR_MAX = 30, 40
    PH_ANO_MIN, PH_ANO_MAX = 1, 1.5
    TEMP_ANO_MIN, TEMP_ANO_MAX = 18, 22
    DEN_ANO_MIN, DEN_ANO_MAX = 0.5, 1.5

    # ================= CACHE & DATA LOADING =================
    @st.cache_data(ttl=10)
    def load_color_logs():
        return supabase.table("color_tank_logs").select("*").order("recorded_at", desc=True).limit(200).execute().data

    @st.cache_data(ttl=10)
    def load_anodize_logs(limit_per_tank=10):
    # ดึงข้อมูลดิบมาทั้งหมดก่อน (หรือจำกัดจำนวนรวมที่เหมาะสม)
    # หมายเหตุ: PostgREST (Supabase) การทำ Limit per group ใน Query เดียวทำได้ยาก
    # เราจึงใช้การดึงข้อมูลล่าสุด 100-200 แถวมาพักไว้ก่อน
        return supabase.table("anodize_tank_logs") \
            .select("*") \
            .order("recorded_at", desc=True) \
            .limit(200) \
            .execute().data

    @st.cache_data(ttl=60)
    def load_tanks():
        return get_options("tanks", "tank_id", "tank_name")

    # ================= KPI SECTION =================
    col1, col2 = st.columns(2)
    active_jigs_res = supabase.table("jig_status").select("jig_id, current_tank_id").eq("status_type", "In-Process").execute()
    active_jigs_data = active_jigs_res.data if active_jigs_res.data else []
    
    production_count = len(active_jigs_data)
    active_tanks_set = {item["current_tank_id"] for item in active_jigs_data if item["current_tank_id"] is not None}
    active_tanks_count = len(active_tanks_set)

    col1.metric("🟢 กำลังผลิต (จิ๊ก)", production_count)
    col2.metric("🧪 บ่อที่กำลังใช้งาน", active_tanks_count)
    st.markdown("---")

    # --- Color Tank Analysis ---
    st.subheader("🎨 วิเคราะห์ข้อมูลบ่อสี (Color Tanks)")
    logs = load_color_logs()
    if logs:
        df = pd.DataFrame(logs)
        df["recorded_at"] = pd.to_datetime(df["recorded_at"])
        tank_map = load_tanks()
        inv_tank_map = {v: k for k, v in tank_map.items()}
        df["tank_name"] = df["tank_id"].map(inv_tank_map)
        latest = df.drop_duplicates("tank_id").copy()
        latest = latest.sort_values("tank_name") 
        if not latest.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Bar(
                    x=latest["tank_name"],
                    y=latest["ph_value"],
                    name="ค่า pH (Std: 5.0-6.0)",
                    marker_color="#98FB98",
                    text=latest["ph_value"],
                    textposition='auto',
                    offsetgroup=1,
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Bar(
                    x=latest["tank_name"],
                    y=latest["temperature"],
                    name="อุณหภูมิ (Std: 30-40 °C)",
                    marker_color="#AFEEEE",
                    text=latest["temperature"],
                    textposition='auto',
                    offsetgroup=2,
                ),
                secondary_y=True,
            )
            fig.update_yaxes(title_text="<b>ค่า pH</b>", secondary_y=False, range=[0, 14], dtick=1, title_font=dict(color="#22c55e"), tickfont=dict(color="#22c55e"), gridcolor='rgba(34, 197, 94, 0.1)')
            fig.update_yaxes(title_text="<b>อุณหภูมิ (°C)</b>", secondary_y=True, range=[0, 100], title_font=dict(color="#3b82f6"), tickfont=dict(color="#3b82f6"), showgrid=False)
            fig.add_hline(y=PH_MIN, line_dash="dash", line_color="#166534", secondary_y=False)
            fig.add_hline(y=PH_MAX, line_dash="dash", line_color="#166534", secondary_y=False)
            fig.add_hline(y=TEMP_COLOR_MIN, line_dash="dot", line_color="#1d4ed8", secondary_y=True)
            fig.add_hline(y=TEMP_COLOR_MAX, line_dash="dot", line_color="#1d4ed8", secondary_y=True)
            fig.update_layout(title=dict(text="เปรียบเทียบค่า pH และอุณหภูมิ (ล่าสุดรายบ่อ)", x=0.5), xaxis_title="ชื่อบ่อสี", barmode="group", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=500, margin=dict(t=100))
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("🚨 ตารางแจ้งเตือนบ่อสี")
        alert_data = []
        for _, row in latest.iterrows():
            alert_data.append({
                "Tank": row["tank_name"],
                "pH": f"{get_status_icon(row['ph_value'], PH_MIN, PH_MAX)} {row['ph_value']:.2f}",
                "Temp (°C)": f"{get_status_icon(row['temperature'], TEMP_COLOR_MIN, TEMP_COLOR_MAX)} {row['temperature']:.1f}"
            })
        st.dataframe(pd.DataFrame(alert_data), use_container_width=True)

        # ================= INDIVIDUAL TANK VIEW =================
        # ================= INDIVIDUAL TANK VIEW (MULTI-SELECT & TIME FILTER) =================
    st.markdown("---")
    st.subheader("🔍 วิเคราะห์ข้อมูลเชิงลึก (Multi-Tank Analysis)")
    
    if logs:
        df_all = pd.DataFrame(logs)
        df_all["recorded_at"] = pd.to_datetime(df_all["recorded_at"])
        tank_map = load_tanks()
        inv_tank_map = {v: k for k, v in tank_map.items()}
        df_all["tank_name"] = df_all["tank_id"].map(inv_tank_map)
        
        # --- ส่วนที่ 1: ตัวเลือกช่วงเวลา ---
        col_f1, col_f2, col_f3 = st.columns(3)
        
        time_unit = col_f1.selectbox("เลือกมุมมองเวลา", ["รายวัน (ปฏิทิน)", "รายเดือน", "รายไตรมาส", "รายปี"])
        
        filtered_df = df_all.copy()
        
        if time_unit == "รายวัน (ปฏิทิน)":
            selected_date = col_f2.date_input("เลือกวันที่", datetime.now(ICT))
            filtered_df = df_all[df_all["recorded_at"].dt.date == selected_date]
            
        elif time_unit == "รายเดือน":
            month_list = df_all["recorded_at"].dt.strftime('%m/%Y').unique()
            selected_month = col_f2.selectbox("เลือกเดือน/ปี", month_list)
            filtered_df = df_all[df_all["recorded_at"].dt.strftime('%m/%Y') == selected_month]
            
        elif time_unit == "รายไตรมาส":
            year_val = col_f2.number_input("ปี (ค.ศ.)", value=datetime.now().year)
            q_val = col_f3.selectbox("ไตรมาส", [1, 2, 3, 4])
            start_q, end_q = get_quarter_range(year_val, q_val)
            filtered_df = df_all[(df_all["recorded_at"] >= start_q) & (df_all["recorded_at"] <= end_q)]
            
        elif time_unit == "รายปี":
            year_list = sorted(df_all["recorded_at"].dt.year.unique(), reverse=True)
            selected_year = col_f2.selectbox("เลือกปี", year_list)
            filtered_df = df_all[df_all["recorded_at"].dt.year == selected_year]
    
        # --- ส่วนที่ 2: ตัวเลือกหลายบ่อพร้อมกัน ---
        available_tanks = sorted(df_all["tank_name"].unique())
        selected_tanks = st.multiselect("เลือกบ่อที่ต้องการเปรียบเทียบ", available_tanks, default=available_tanks[:1])
    
        if not filtered_df.empty and selected_tanks:
            # กรองตามบ่อที่เลือก
            final_df = filtered_df[filtered_df["tank_name"].isin(selected_tanks)].sort_values("recorded_at")
            
            g1, g2 = st.columns(2)
            
            with g1:
                fig_ph = go.Figure()
                for t_name in selected_tanks:
                    t_data = final_df[final_df["tank_name"] == t_name]
                    fig_ph.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["ph_value"], 
                                              mode='lines+markers', name=f"pH: {t_name}"))
                fig_ph.add_hrect(y0=PH_MIN, y1=PH_MAX, fillcolor="green", opacity=0.1, line_width=0)
                fig_ph.update_layout(title="แนวโน้มค่า pH (เปรียบเทียบ)", xaxis_title="เวลา", yaxis_title="pH")
                st.plotly_chart(fig_ph, use_container_width=True)
                
            with g2:
                fig_temp = go.Figure()
                for t_name in selected_tanks:
                    t_data = final_df[final_df["tank_name"] == t_name]
                    fig_temp.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["temperature"], 
                                                mode='lines+markers', name=f"Temp: {t_name}"))
                fig_temp.add_hrect(y0=TEMP_COLOR_MIN, y1=TEMP_COLOR_MAX, fillcolor="orange", opacity=0.1, line_width=0)
                fig_temp.update_layout(title="แนวโน้มอุณหภูมิ (เปรียบเทียบ)", xaxis_title="เวลา", yaxis_title="°C")
                st.plotly_chart(fig_temp, use_container_width=True)
                
            with st.expander("📊 ดูข้อมูลตารางที่กรองแล้ว"):
                st.dataframe(final_df[["recorded_at", "tank_name", "ph_value", "temperature"]].sort_values("recorded_at", ascending=False), use_container_width=True)
        else:
            st.warning("⚠️ ไม่พบข้อมูลในช่วงเวลาที่เลือก หรือยังไม่ได้เลือกบ่อ")
            tank_map = load_tanks()
            inv_map = {v: k for k, v in tank_map.items()}
            df_all["tank_name"] = df_all["tank_id"].map(inv_map)
            available_tanks = sorted(df_all["tank_name"].unique())
            selected_tank = st.selectbox("เลือกบ่อที่ต้องการดูรายละเอียด", available_tanks)
            tank_df = df_all[df_all["tank_name"] == selected_tank].sort_values("recorded_at")
    
            if not tank_df.empty:
                g1, g2 = st.columns(2)
                with g1:
                    fig_ph = go.Figure()
                    fig_ph.add_trace(go.Scatter(x=tank_df["recorded_at"], y=tank_df["ph_value"], mode='lines+markers', name='pH Value', line=dict(color='#22c55e', width=3), marker=dict(size=8)))
                    fig_ph.add_hrect(y0=PH_MIN, y1=PH_MAX, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Standard Range")
                    fig_ph.update_layout(title=f"แนวโน้มค่า pH: {selected_tank}", xaxis_title="เวลาที่บันทึก", yaxis_title="pH", hovermode="x unified")
                    st.plotly_chart(fig_ph, use_container_width=True)
                with g2:
                    fig_temp = go.Figure()
                    fig_temp.add_trace(go.Scatter(x=tank_df["recorded_at"], y=tank_df["temperature"], mode='lines+markers', name='Temperature', line=dict(color='#22c55e', width=3), marker=dict(size=8)))
                    fig_temp.add_hrect(y0=TEMP_COLOR_MIN, y1=TEMP_COLOR_MAX, fillcolor="orange", opacity=0.1, line_width=0, annotation_text="Standard Range")
                    fig_temp.update_layout(title=f"แนวโน้มอุณหภูมิ: {selected_tank}", xaxis_title="เวลาที่บันทึก", yaxis_title="อุณหภูมิ (°C)", hovermode="x unified")
                    st.plotly_chart(fig_temp, use_container_width=True)
                with st.expander(f"ดูประวัติข้อมูลดิบของ {selected_tank}"):
                    st.dataframe(tank_df[["recorded_at", "ph_value", "temperature"]].sort_values("recorded_at", ascending=False), use_container_width=True)
    
        # ================= ANODIZE TREND ANALYSIS ================
        st.markdown("---")
        st.subheader("📈 วิเคราะห์แนวโน้มบ่ออโนไดซ์ (Anodize Detailed Trend)")
        logs_a = load_anodize_logs()
        if logs_a:
            df_a = pd.DataFrame(logs_a)
            df_a["recorded_at"] = pd.to_datetime(df_a["recorded_at"])
            tank_map = load_tanks()
            inv_map = {v: k for k, v in tank_map.items()}
            df_a["tank_name"] = df_a["tank_id"].map(inv_map)
            
            st.subheader("🚨 ตารางแจ้งเตือนบ่ออโนไดซ์")
            latest_ano = df_a.sort_values("recorded_at").groupby("tank_name").tail(1)
            alert_ano = []
            for _, row in latest_ano.iterrows():
                alert_ano.append({
                    "Tank": row["tank_name"],
                    "pH": f"{get_status_icon(row['ph_value'], PH_ANO_MIN, PH_ANO_MAX)} {row['ph_value']:.2f}",
                    "Temp": f"{get_status_icon(row['temperature'], TEMP_ANO_MIN, TEMP_ANO_MAX)} {row['temperature']:.1f}",
                    "Density": f"{get_status_icon(row['density'], DEN_ANO_MIN, DEN_ANO_MAX)} {row['density']:.3f}"
                })
            st.dataframe(pd.DataFrame(alert_ano), use_container_width=True)
    
            available_ano_tanks = sorted(df_a["tank_name"].dropna().unique())
            selected_ano = st.selectbox("เลือกบ่ออโนไดซ์เพื่อดูแนวโน้ม", available_ano_tanks)
        
        # กรองข้อมูลเฉพาะบ่อที่เลือก -> เรียงใหม่ -> เอา 10 แถวบนสุด (ล่าสุด)
            ano_filtered = df_a[df_a["tank_name"] == selected_ano] \
                            .sort_values("recorded_at", ascending=False) \
                            .head(10)
        
        # เรียงกลับเป็น อดีต -> ปัจจุบัน เพื่อให้กราฟเดินจากซ้ายไปขวา
            ano_chart_df = ano_filtered.sort_values("recorded_at")
    
            if not ano_chart_df.empty:
                g1, g2, g3 = st.columns(3)
                with g1:
                    fig_ph = go.Figure()
                    fig_ph.add_trace(go.Scatter(
                        x=ano_chart_df["recorded_at"], 
                        y=ano_chart_df["ph_value"], 
                        mode='lines+markers', 
                        name='pH', 
                        line=dict(color='#22c55e', width=2)
                ))
                    fig_ph.add_hrect(y0=PH_ANO_MIN, y1=PH_ANO_MAX, fillcolor="green", opacity=0.1, line_width=0)
                    fig_ph.update_layout(title="แนวโน้ม pH (10 ครั้งล่าสุด)", height=350)
                    st.plotly_chart(fig_ph, use_container_width=True)
                with g2:
                    fig_temp = go.Figure()
                    fig_temp.add_trace(go.Scatter(x=ano_chart_df["recorded_at"], y=ano_filtered["temperature"], mode='lines+markers', name='Temp', line=dict(color='#3b82f6', width=2), marker=dict(size=6)))
                    fig_temp.add_hrect(y0=TEMP_ANO_MIN, y1=TEMP_ANO_MAX, fillcolor="blue", opacity=0.1, line_width=0)
                    fig_temp.update_layout(title="แนวโน้มอุณหภูมิ (°C)", height=350, margin=dict(t=50, b=20, l=10, r=10))
                    st.plotly_chart(fig_temp, use_container_width=True)
                with g3:
                    fig_den = go.Figure()
                    fig_den.add_trace(go.Scatter(x=ano_chart_df["recorded_at"], y=ano_filtered["density"], mode='lines+markers', name='Density', line=dict(color='#a855f7', width=2), marker=dict(size=6)))
                    fig_den.add_hrect(y0=DEN_ANO_MIN, y1=DEN_ANO_MAX, fillcolor="purple", opacity=0.1, line_width=0)
                    fig_den.update_layout(title="แนวโน้มความหนาแน่น", height=350, margin=dict(t=50, b=20, l=10, r=10))
                    st.plotly_chart(fig_den, use_container_width=True)
    
                with st.expander(f"📋 รายละเอียดข้อมูลบันทึก {selected_ano}"):
                    log_display = ano_chart_df[["recorded_at", "ph_value", "temperature", "density"]].sort_values("recorded_at", ascending=False)
                    st.dataframe(log_display.style.format({"ph_value": "{:.2f}", "temperature": "{:.1f}", "density": "{:.3f}"}), use_container_width=True)
            else:
                st.warning("ไม่พบข้อมูลบันทึกสำหรับบ่อนี้")
        else:
            st.info("ไม่มีข้อมูลในระบบ Anodize")
    
        try:
            st_autorefresh(interval=10000, key="refresh")
        except:
            pass

# 3. สร้าง Tab หลัก
tab_titles = [
    "🎨 บ่อสี (Color Bath)",
    "⚡ บ่ออโนไดซ์ (Anodize)",
    "📦 งานจิ๊ก (Jig System)"
]

tab_color, tab_ano, tab_jig = st.tabs(tab_titles)

# =========================================================
# TAB 1 : COLOR BATH
# =========================================================
with tab_color:
    try:
        color_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")

        if color_tanks:
            tank_list = list(color_tanks.keys())

            start_idx = (
                tank_list.index(clicked_tank)
                if clicked_tank in tank_list else 0
            )

            selected_tank_name = st.selectbox(
                "เลือกบ่อสี",
                tank_list,
                index=start_idx,
                key="sb_color_safe"
            )

            detected_color = TANK_COLOR_MAP.get(selected_tank_name, "Black")
            render_color_bar(detected_color)

            with st.form("form_color_safe", clear_on_submit=True):

                ph = st.number_input(
                    "ค่า pH",
                    step=0.1,
                    format="%.2f",
                    key="ph_c_safe"
                )

                temp = st.number_input(
                    "อุณหภูมิ (°C)",
                    step=0.1,
                    format="%.1f",
                    key="tp_c_safe"
                )

                if st.form_submit_button("บันทึกค่าบ่อสี"):

                    supabase.table("color_tank_logs").insert({
                        "tank_id": color_tanks[selected_tank_name],
                        "ph_value": ph,
                        "temperature": temp,
                        "recorded_at": datetime.now(ICT).isoformat()
                    }).execute()

                    st.success("✅ บันทึกสำเร็จ")

                    st.query_params.clear()
                    time.sleep(0.5)
                    st.rerun()

        else:
            st.info("ไม่พบข้อมูลบ่อสี")

    except Exception as e:
        st.error(f"ส่วนบ่อสีมีปัญหา: {e}")

# =========================================================
# TAB 2 : ANODIZE
# =========================================================
with tab_ano:
    try:
        ano_tanks = get_options(
            "tanks",
            "tank_id",
            "tank_name",
            "tank_type",
            "Anodize"
        )

        if ano_tanks:

            ano_list = list(ano_tanks.keys())

            start_idx_ano = (
                ano_list.index(clicked_tank)
                if clicked_tank in ano_list else 0
            )

            sel_ano = st.selectbox(
                "เลือกบ่ออโนไดซ์",
                ano_list,
                index=start_idx_ano,
                key="sb_ano_safe"
            )

            with st.form("form_ano_safe", clear_on_submit=True):

                ph_a = st.number_input(
                    "ค่า pH",
                    step=0.01,
                    format="%.2f",
                    key="ph_a_safe"
                )

                temp_a = st.number_input(
                    "อุณหภูมิ (°C)",
                    step=0.1,
                    format="%.1f",
                    key="tp_a_safe"
                )

                den_a = st.number_input(
                    "ความหนาแน่น",
                    step=0.001,
                    format="%.3f",
                    key="dn_a_safe"
                )

                if st.form_submit_button("บันทึกข้อมูลอโนไดซ์"):

                    supabase.table("anodize_tank_logs").insert({
                        "tank_id": ano_tanks[sel_ano],
                        "ph_value": ph_a,
                        "temperature": temp_a,
                        "density": den_a,
                        "recorded_at": datetime.now(ICT).isoformat()
                    }).execute()

                    st.success("✅ บันทึกสำเร็จ")

                    st.query_params.clear()
                    time.sleep(0.5)
                    st.rerun()

        else:
            st.info("ไม่พบข้อมูลบ่ออโนไดซ์")

    except Exception as e:
        st.error(f"ส่วนอโนไดซ์มีปัญหา: {e}")

# =========================================================
# TAB 3 : JIG SYSTEM
# =========================================================
with tab_jig:

    st.subheader("📦 ระบบจัดการงานจิ๊ก")

    jig_tabs = st.tabs([
        "📦 ลงทะเบียนสินค้า",
        "🛠️ ลงทะเบียนจิ๊ก",
        "⚡ บันทึกผลผลิต"
    ])

    # -----------------------------------------------------
    # PRODUCT REGISTER
    # -----------------------------------------------------
    with jig_tabs[0]:

        shape = st.selectbox(
            "📐 รูปทรง",
            ["สี่เหลี่ยม", "ทรงกระบอกทึบ", "ทรงกระบอกกลวง"],
            key="sh_j_safe"
        )

        with st.form("f_prod_safe", clear_on_submit=True):

            c1, c2 = st.columns(2)

            p_code = c1.text_input("รหัสสินค้า *")
            p_name = c1.text_input("ชื่อสินค้า")
            s_finish = c1.text_input("พื้นผิว", value="-")

            height = c2.number_input(
                "ความสูง/ยาว (H) [mm]",
                min_value=0.0
            )

            u_vol = 0.0
            width = 0.0
            thickness = 0.0
            od = 0.0
            id_inner = 0.0

            if shape == "สี่เหลี่ยม":

                width = c2.number_input(
                    "กว้าง [mm]",
                    min_value=0.0
                )

                thickness = c2.number_input(
                    "หนา [mm]",
                    min_value=0.0
                )

                u_vol = height * width * thickness

            elif shape == "ทรงกระบอกทึบ":

                od = c2.number_input(
                    "เส้นผ่านศูนย์กลาง (OD)",
                    min_value=0.0
                )

                u_vol = math.pi * ((od / 2) ** 2) * height

            else:

                od = c2.number_input(
                    "OD [mm]",
                    min_value=0.0
                )

                thickness = c2.number_input(
                    "ความหนาเนื้อ",
                    min_value=0.0
                )

                id_inner = max(0.0, od - (2 * thickness))

                u_vol = math.pi * (
                    ((od / 2) ** 2) -
                    ((id_inner / 2) ** 2)
                ) * height

            st.info(f"ปริมาตร: {u_vol:,.2f} mm³")

            if st.form_submit_button("➕ ลงทะเบียนสินค้า"):

                if p_code:

                    supabase.table("products").insert({
                        "product_code": p_code,
                        "product_name": p_name,
                        "unit_volume": u_vol,
                        "shape": shape
                    }).execute()

                    st.success("สำเร็จ")
                    st.rerun()

    # -----------------------------------------------------
    # JIG REGISTER
    # -----------------------------------------------------
    with jig_tabs[1]:

        with st.form("f_jig_safe", clear_on_submit=True):

            lot_n = st.text_input("Lot No.")

            j_qty = st.number_input(
                "จำนวนจิ๊ก",
                min_value=1,
                max_value=50,
                value=1
            )

            if st.form_submit_button("🚀 สร้างรหัสจิ๊ก"):

                if lot_n:

                    today = datetime.now(ICT).strftime("%Y%m%d")

                    res = supabase.table("jigs") \
                        .select("jig_model_code") \
                        .like("jig_model_code", f"{today}%") \
                        .order("jig_model_code", desc=True) \
                        .limit(1) \
                        .execute()

                    last = (
                        int(res.data[0]['jig_model_code'][-3:])
                        if res.data else 0
                    )

                    new_j = [
                        {
                            "jig_model_code": f"{today}{last+i:03d}",
                            "lot_no": lot_n
                        }
                        for i in range(1, j_qty + 1)
                    ]

                    supabase.table("jigs").insert(new_j).execute()

                    st.success("สำเร็จ")
                    st.rerun()

    # -----------------------------------------------------
    # PRODUCTION LOG
    # -----------------------------------------------------
    with jig_tabs[2]:

        try:

            prods = supabase.table("products") \
                .select("product_id, product_code") \
                .execute().data

            jigs = supabase.table("jigs") \
                .select("jig_id, jig_model_code, lot_no") \
                .execute().data

            if prods and jigs:

                j_map = {
                    f"Jig: {j['jig_model_code']} | Lot: {j['lot_no']}": j['jig_id']
                    for j in jigs
                }

                p_map = {
                    p['product_code']: p['product_id']
                    for p in prods
                }

                sel_j = st.selectbox(
                    "เลือกจิ๊ก",
                    list(j_map.keys()),
                    key="sj_safe"
                )

                sel_p = st.selectbox(
                    "เลือกสินค้า",
                    list(p_map.keys()),
                    key="sp_safe"
                )

                act = st.radio(
                    "สถานะ",
                    ["🔵 บันทึกงานต่อ", "🟢 เสร็จสิ้นงาน"],
                    horizontal=True
                )

                if act == "🔵 บันทึกงานต่อ":

                    with st.form("f_log_safe"):

                        total_pcs = st.number_input(
                            "จำนวนรวมชิ้นงาน",
                            min_value=1
                        )

                        if st.form_submit_button("💾 บันทึก"):

                            j_id = j_map[sel_j]

                            supabase.table("jig_status").upsert({
                                "jig_id": j_id,
                                "status_type": "In-Process",
                                "updated_at": datetime.now(ICT).isoformat()
                            }).execute()

                            st.success("บันทึกแล้ว")
                            st.rerun()

                else:

                    if st.button("🏁 ยืนยันเสร็จสิ้นงาน"):

                        supabase.table("jig_status").upsert({
                            "jig_id": j_map[sel_j],
                            "status_type": "Finished",
                            "updated_at": datetime.now(ICT).isoformat()
                        }).execute()

                        st.success("ปิดงานสำเร็จ")
                        st.rerun()

        except Exception as e:
            st.error(f"ส่วนบันทึกผลผลิตมีปัญหา: {e}")
