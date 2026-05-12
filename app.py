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
import streamlit.components.v1 as components
import streamlit_javascript as stjs


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
#============================================================================================
def render_tank_map():
    # Helper สำหรับสร้างแต่ละบ่อ
    def t_div(name, top, left, w, h, bg, extra=""):
        return f"""
        <div class="tank {extra}" 
             onclick="window.parent.postMessage({{type: 'tank_click', name: '{name}'}}, '*')"
             style="left:{left}px;top:{top}px;width:{w}px;height:{h}px;background:{bg};cursor:pointer;">
            {name}
        </div>"""

    # HTML และ CSS ผังบ่อ
    html_code = f"""
    <style>
        .plant-map {{ position:relative; width:1100px; height:720px; background:#fff; border:2px solid #ccc; margin:auto; overflow:hidden; font-family: sans-serif; }}
        .tank {{ position:absolute; color:white; font-weight:bold; font-size:12px; border-radius:2px; display:flex; align-items:center; justify-content:center; text-align:center; border:1px solid #444; box-sizing:border-box; transition: 0.2s; }}
        .tank:hover {{ opacity: 0.7; border: 3px solid yellow !important; transform: scale(1.05); z-index: 100; }}
        .vertical {{ writing-mode:vertical-rl; text-orientation:mixed; font-size:16px; }}
        .ro {{ background:#d7ffff !important; color:black !important; }}
    </style>
    <div class="plant-map">
        {t_div("5Black", 10, 10, 70, 70, "#111")}
        {t_div("2Red", 10, 140, 65, 70, "red")}
        {t_div("3Violet", 10, 205, 65, 70, "purple")}
        {t_div("8Green", 10, 290, 65, 70, "green")}
        {t_div("17Black", 10, 355, 65, 70, "#222")}
        {t_div("15Gold", 10, 440, 65, 70, "#d4af00")}
        {t_div("9Orange", 10, 505, 65, 70, "orange")}
        {t_div("10LightBlue", 10, 600, 65, 70, "cyan", "color:black;")}
        {t_div("6BananaLeafGreen", 10, 665, 65, 70, "#7fff00", "color:black;")}
        {t_div("16Blue", 10, 760, 65, 70, "blue")}
        {t_div("4DarkBlue", 10, 825, 65, 70, "darkblue")}
        {t_div("20Black", 245, 260, 75, 45, "#111")}
        {t_div("1DarkRedA", 295, 260, 75, 45, "darkred")}
        {t_div("7Pink", 245, 360, 80, 160, "magenta", "vertical")}
        {t_div("HotSealH60", 250, 520, 80, 160, "#666")}
        {t_div("11Gold", 415, 520, 80, 160, "#cc9900", "vertical")}
        {t_div("AnodizedPPool1", 660, 860, 130, 230, "#ccc", "vertical; color:black;")}
    </div>
    """
    components.html(html_code, height=750)

    # --- ส่วนที่เกิด Error อยู่ตรงนี้ (จัดย่อหน้าใหม่ให้ตรงกัน) ---
    js_key = st.session_state.get('js_key', 0)
    clicked_name = st_javascript("""
        new Promise((resolve) => {
            window.addEventListener('message', function(event) {
                if (event.data.type === 'tank_click') {
                    resolve(event.data.name);
                }
            }, { once: true });
        });
    """, key=f"tank_clicker_{js_key}")
    
    return clicked_name
#=================================================================================
@st.dialog("บันทึกข้อมูลบ่อ")
def record_modal(tank_name):
    st.write(f"### 📍 บ่อ: {tank_name}")
    
    # 1. เช็คประเภทบ่อจากชื่อ
    is_anodize = "Anodized" in tank_name or "PPool" in tank_name
    
    # 2. เริ่มสร้างฟอร์ม (ใช้ชื่อฟอร์มเดียวเพื่อความง่าย หรือแยกตามประเภท)
    with st.form("modal_record_form", clear_on_submit=True):
        if not is_anodize:
            # --- ส่วนของบ่อสี ---
            ph = st.number_input("ค่า pH (Color)", step=0.01, format="%.2f", value=5.50)
            temp = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f", value=30.0)
            
            if st.form_submit_button("💾 บันทึกบ่อสี"):
                all_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
                if tank_name in all_tanks:
                    try:
                        supabase.table("color_tank_logs").insert({
                            "tank_id": all_tanks[tank_name],
                            "ph_value": ph,
                            "temperature": temp,
                            "recorded_at": datetime.now(ICT).isoformat()
                        }).execute()
                        
                        st.success("บันทึกบ่อสีสำเร็จ!")
                        st.session_state['js_key'] = st.session_state.get('js_key', 0) + 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error(f"ไม่พบชื่อบ่อ '{tank_name}' ในฐานข้อมูล (ประเภท Color)")

        else:
            # --- ส่วนของบ่ออโนไดซ์ ---
            ph_a = st.number_input("ค่า pH (Anodize)", step=0.01, format="%.2f", value=1.20)
            temp_a = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f", value=20.0)
            den_a = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f", value=1.000)
            
            if st.form_submit_button("💾 บันทึกอโนไดซ์"):
                all_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Anodize")
                if tank_name in all_tanks:
                    try:
                        supabase.table("anodize_tank_logs").insert({
                            "tank_id": all_tanks[tank_name],
                            "ph_value": ph_a,
                            "temperature": temp_a,
                            "density": den_a,
                            "recorded_at": datetime.now(ICT).isoformat()
                        }).execute()
                        
                        st.success("บันทึกอโนไดซ์สำเร็จ!")
                        st.session_state['js_key'] = st.session_state.get('js_key', 0) + 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error(f"ไม่พบชื่อบ่อ '{tank_name}' ในฐานข้อมูล (ประเภท Anodize)")
                    st.session_state.js_key += 1
            time.sleep(1)
            st.rerun()@st.dialog("บันทึกข้อมูลบ่อ")
def record_modal(tank_name):
    st.write(f"### 📍 บ่อ: {tank_name}")
    
    # 1. เช็คประเภทบ่อจากชื่อ
    is_anodize = "Anodized" in tank_name or "PPool" in tank_name
    
    # 2. เริ่มสร้างฟอร์ม
    with st.form("modal_record_form", clear_on_submit=True):
        if not is_anodize:
            # --- ส่วนของบ่อสี ---
            ph = st.number_input("ค่า pH (Color)", step=0.01, format="%.2f", value=5.50)
            temp = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f", value=30.0)
            
            submit = st.form_submit_button("💾 บันทึกบ่อสี")
            if submit:
                all_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
                if tank_name in all_tanks:
                    try:
                        supabase.table("color_tank_logs").insert({
                            "tank_id": all_tanks[tank_name],
                            "ph_value": ph,
                            "temperature": temp,
                            "recorded_at": datetime.now(ICT).isoformat()
                        }).execute()
                        
                        st.success("บันทึกบ่อสีสำเร็จ!")
                        st.session_state['js_key'] = st.session_state.get('js_key', 0) + 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error(f"ไม่พบชื่อบ่อ '{tank_name}' ในฐานข้อมูล (ประเภท Color)")

        else:
            # --- ส่วนของบ่ออโนไดซ์ ---
            ph_a = st.number_input("ค่า pH (Anodize)", step=0.01, format="%.2f", value=1.20)
            temp_a = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f", value=20.0)
            den_a = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f", value=1.000)
            
            submit_ano = st.form_submit_button("💾 บันทึกอโนไดซ์")
            if submit_ano:
                all_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Anodize")
                if tank_name in all_tanks:
                    try:
                        supabase.table("anodize_tank_logs").insert({
                            "tank_id": all_tanks[tank_name],
                            "ph_value": ph_a,
                            "temperature": temp_a,
                            "density": den_a,
                            "recorded_at": datetime.now(ICT).isoformat()
                        }).execute()
                        
                        st.success("บันทึกอโนไดซ์สำเร็จ!")
                        st.session_state['js_key'] = st.session_state.get('js_key', 0) + 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
                else:
                    st.error(f"ไม่พบชื่อบ่อ '{tank_name}' ในฐานข้อมูล (ประเภท Anodize)")
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

# ================= RECORD PAGE =================
if menu == "บันทึกข้อมูลการผลิต":
    st.title("📝 ระบบบันทึกข้อมูลการผลิต")
    st.info("💡 คลิกที่ชื่อบ่อในแผนผังด้านล่างเพื่อบันทึกข้อมูล")
    
    if "js_key" not in st.session_state:
        st.session_state.js_key = 0

    # เรียกใช้แผนผัง
    clicked_name = render_tank_map()

    # ตรวจสอบการคลิก
    # ถ้า st_javascript คืนค่ากลับมา (ไม่เป็น None / 0 / False) ให้เปิด Modal
    if clicked_name:
        # เรียก Modal ทันที
        record_modal(clicked_name)
    st.markdown("---")
    
    st.subheader("🛠️ การจัดการจิ๊กและสินค้า")
    sub_prod, sub_jig, sub_log = st.tabs(["📦 1. ลงทะเบียนสินค้า", "🛠️ 2. ลงทะเบียนจิ๊ก", "⚡ 3. บันทึกผลผลิต"])
    with sub_prod:
        st.subheader("เพิ่มสินค้าใหม่ลงระบบ")
        shape = st.selectbox("📐 เลือกรูปทรง", ["สี่เหลี่ยม", "ทรงกระบอกทึบ", "ทรงกระบอกกลวง"], key="shape_sel")
        with st.form("add_prod_form_fixed", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_code = c1.text_input("รหัสสินค้า *")
            p_name = c1.text_input("ชื่อสินค้า")
            s_finish = c1.text_input("พื้นผิว *", value="-")
            height = c2.number_input("ความยาว/ความสูง (H) [mm]", min_value=0.0)
            width, thickness, od, u_vol, id_inner = 0.0, 0.0, 0.0, 0.0, 0.0
            if shape == "สี่เหลี่ยม":
                width = c2.number_input("กว้าง [mm]", min_value=0.0)
                thickness = c2.number_input("สูง/หนา [mm]", min_value=0.0)
                u_vol = height * width * thickness
            elif shape == "ทรงกระบอกทึบ":
                od = c2.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0)
                u_vol = math.pi * ((od/2)**2) * height
            else:
                od = c2.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0)
                thickness = c2.number_input("ความหนาของเนื้อชิ้นงาน [mm]", min_value=0.0)
                id_inner = max(0.0, od - (2*thickness))
                u_vol = math.pi * ((od/2)**2 - (id_inner/2)**2) * height

            st.info(f"💡 ปริมาตร: {u_vol:,.2f} mm³")
            if st.form_submit_button("➕ ลงทะเบียนสินค้า"):
                if p_code:
                    check_exist = supabase.table("products").select("product_code").eq("product_code", p_code).execute()
                    if check_exist.data:
                        st.error(f"❌ รหัสสินค้า '{p_code}' นี้มีอยู่ในระบบแล้ว")
                    else:
                        payload = {
                            "product_code": p_code, "product_name": p_name, "surface_finish": s_finish, 
                            "unit_volume": u_vol, "height": height, "width": width, "thickness": thickness, 
                            "depth": thickness, "shape": shape, "outer_diameter": od, "inner_diameter": id_inner
                        }
                        supabase.table("products").insert(payload).execute()
                        st.success(f"✅ ลงทะเบียนรหัส {p_code} สำเร็จ!")
                else: 
                    st.error("กรุณาระบุรหัสสินค้า")

    with sub_jig:
        st.subheader("📦 ลงทะเบียนจิ๊กชุดใหม่ (Bulk Registration)")
    
        # 1. ส่วนการตั้งค่า Prefix วันที่
        today_prefix = datetime.now(ICT).strftime("%Y%m%d")
    
        # ดึงข้อมูลล่าสุดมาดูว่าวันนี้รันไปถึงเลขไหนแล้ว
        jig_count_res = supabase.table("jigs") \
            .select("jig_model_code") \
            .like("jig_model_code", f"{today_prefix}%") \
            .order("jig_model_code", desc=True) \
            .limit(1) \
            .execute()
    
        # หาเลขลำดับเริ่มต้น (ถ้ายังไม่มีเลยให้เริ่มที่ 0)
        if jig_count_res.data:
            last_code = jig_count_res.data[0]['jig_model_code']
            last_number = int(last_code[-3:]) # ดึง 3 หลักสุดท้ายมาเป็นตัวเลข
        else:
            last_number = 0

        with st.form("bulk_jig_form", clear_on_submit=True):
            col_lot, col_qty = st.columns(2)
            lot_no_input = col_lot.text_input("หมายเลข Lot (Lot No.)", placeholder=" 1 ")
            jig_quantity = col_qty.number_input("จำนวนจิ๊กที่ต้องการสร้าง", min_value=1, max_value=50, value=1)
        
            st.info(f"💡 ระบบจะเริ่มรันรหัสตั้งแต่: **{today_prefix}{last_number + 1:03d}** ถึง **{today_prefix}{last_number + jig_quantity:03d}**")

            if st.form_submit_button("🚀 สร้างรหัสจิ๊กทั้งหมด"):
                if not lot_no_input:
                    st.error("❌ กรุณาระบุ Lot No. ก่อนสร้าง")
                else:
                    new_jigs = []
            # วนลูปสร้างข้อมูลตามจำนวนที่ระบุ
                    for i in range(1, jig_quantity + 1):
                        new_code = f"{today_prefix}{last_number + i:03d}"
                        new_jigs.append({
                            "jig_model_code": new_code,
                            "lot_no": lot_no_input,
                            "total_pcs_in_jig": 0
                        })
                
                    try:
                # บันทึกข้อมูลแบบก้อนเดียว (Bulk Insert) เพื่อความรวดเร็ว
                        supabase.table("jigs").insert(new_jigs).execute()
                        st.success(f"✅ สำเร็จ! สร้างจิ๊กจำนวน {jig_quantity} อัน ลงใน Lot {lot_no_input} เรียบร้อยแล้ว")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")

# ส่วนเสริม: แสดงประวัติการสร้างของวันนี้
        with st.expander("📝 ดูรายการจิ๊กที่สร้างวันนี้"):
            today_jigs = supabase.table("jigs").select("*").like("jig_model_code", f"{today_prefix}%").order("jig_model_code", desc=True).execute()
            if today_jigs.data:
                st.dataframe(pd.DataFrame(today_jigs.data), use_container_width=True)
    #-------------------------------------------------------------------------------                       
    with sub_log:
        prods_res = supabase.table("products").select("product_id, product_code, product_name").execute().data
        if prods_res:
            display_options = {f"{p['product_code']} | {p['product_name']}": p['product_id'] for p in prods_res}
            jigs_data = supabase.table("jigs").select("jig_id, jig_model_code, lot_no").execute().data
        
    # --- 🟢 แก้ไขตรงนี้: ดึงสถานะจิ๊กทั้งหมดมาครั้งเดียว 🟢 ---
            status_all = supabase.table("jig_status").select("jig_id, status_type").execute().data
    # สร้าง Dictionary เพื่อให้หาได้เร็วขึ้น {jig_id: status_type}
            status_dict = {item["jig_id"]: item["status_type"] for item in (status_all or [])}

            available_jigs = []
            for j in (jigs_data or []):
        # เช็คสถานะจาก Dictionary ที่เราดึงมาพักไว้ (ไม่ต้องยิง Query ใหม่ในลูป)
                current_status = status_dict.get(j["jig_id"])
            
        # ถ้ายังไม่มีสถานะ หรือ สถานะไม่ใช่ Finished ให้ถือว่าใช้งานได้
                if current_status != "Finished":
                    available_jigs.append(j)
        # --- ------------------------------------------ ---

            if not available_jigs:
                st.warning("❌ ไม่มีจิ๊กที่ใช้งานได้")
            else:
                jig_map = {f"Jig: {j['jig_model_code']} | Lot: {j.get('lot_no', 'N/A')}": j['jig_id'] for j in available_jigs}
                color_tanks_all = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
                    
                if display_options and color_tanks_all:
                    sel_j = st.selectbox("เลือกจิ๊ก", list(jig_map.keys()), key="sel_j_log")
                    jig_id = jig_map[sel_j]
                    selected_display = st.selectbox("เลือกสินค้า (รหัส | ชื่อ)", options=list(display_options.keys()), key="sel_p_log")
                    selected_prod_id = display_options[selected_display]
                    p_info = supabase.table("products").select("*").eq("product_id", selected_prod_id).single().execute().data
                    action = st.radio("การทำงาน", ["🔵 บันทึกงานต่อ", "🟢 เสร็จสิ้นงาน"], key="action_radio")

                    if action == "🔵 บันทึกงานต่อ":
                        sel_c_new = st.selectbox("เลือกสี", sorted(set(TANK_COLOR_MAP.values())), key="sel_c_log")
                        filtered_tanks = {n: i for n, i in color_tanks_all.items() if TANK_COLOR_MAP.get(n) == sel_c_new}
                        if filtered_tanks:
                            sel_tank_name = st.selectbox("เลือกบ่อสี", list(filtered_tanks.keys()), key="sel_t_log")
                            with st.form("continue_form_fixed", clear_on_submit=True):
                                c1, c2 = st.columns(2)
                                pcs = c1.number_input("จำนวนต่อแถว", min_value=0)
                                rows = c1.number_input("แถวที่เต็ม", min_value=0)
                                partial = c1.number_input("เศษ", min_value=0)
                                total_pcs = (rows * pcs) + partial
                                unit_vol = p_info.get('unit_volume', 0)
                                total_vol = unit_vol * total_pcs
                                c2.metric("จำนวนรวม (Pcs)", total_pcs)
                                c2.metric("ปริมาตรรวม (mm³)", f"{total_vol:,.2f}")
                                if st.form_submit_button("💾 บันทึก"):
                                    try:
                                        # 1. บันทึกข้อมูลลงในตาราง Log (ประวัติการใช้งาน)
                                        supabase.table("jig_usage_log").insert({
                                            "product_id": selected_prod_id, 
                                            "jig_id": jig_id, 
                                            "color": sel_c_new, 
                                            "tank_id": filtered_tanks[sel_tank_name], 
                                            "total_pieces": total_pcs, 
                                            "total_volume": total_vol, 
                                            "recorded_date": datetime.now(ICT).isoformat(),
                                            "rows_filled": rows, 
                                            "partial_pieces": partial,
                                            "pcs_per_row": pcs
                                        }).execute()

                                        # 2. อัปเดตสถานะในตาราง jig_status (สำหรับ Dashboard)
                                        supabase.table("jig_status").upsert({
                                            "jig_id": jig_id, 
                                            "status_type": "In-Process", 
                                            "current_tank_id": filtered_tanks[sel_tank_name], 
                                            "updated_at": datetime.now(ICT).isoformat()
                                        }).execute()

                                        # --- ส่วนที่เพิ่มใหม่: 3. อัปเดตจำนวนชิ้นงานในตาราง jigs ---
                                        supabase.table("jigs").update({
                                            "total_pcs_in_jig": total_pcs
                                        }).eq("jig_id", jig_id).execute()

                                        st.success(f"✅ บันทึกสำเร็จ: อัปเดตจำนวน {total_pcs} ชิ้นลงในจิ๊กเรียบร้อย")
                                        time.sleep(1) # ให้ User เห็นข้อความ Success แป๊บหนึ่ง
                                        st.rerun()

                                    except Exception as e:
                                        st.error(f"เกิดข้อผิดพลาดในการบันทึก: {str(e)}")
                    elif action == "🟢 เสร็จสิ้นงาน":
                        try:
                            check_log = supabase.table("jig_usage_log").select("*").eq("jig_id", jig_id).limit(1).execute()
                        except Exception as e:
                            st.error(f"รายละเอียด Error: {e}") # ตรงนี้จะบอกชัดเจนว่าหาคอลัมน์ไม่เจอ หรือติด RLS
    
                        if not check_log.data:
                            st.warning("⚠️ ไม่สามารถปิดงานได้: จิ๊กนี้ยังไม่มีการบันทึกข้อมูลการผลิต (กรุณาบันทึกงานต่อก่อน)")
                        else:
                            if st.button("🏁 ยืนยันเสร็จสิ้นงาน"):
                                supabase.table("jig_status").upsert({
                                    "jig_id": jig_id, 
                                    "status_type": "Finished", 
                                    "current_tank_id": None, 
                                    "updated_at": datetime.now(ICT).isoformat()
                                }).execute()
                                st.success("งานเสร็จสิ้น")
                                time.sleep(1)
                                st.rerun()
