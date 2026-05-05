import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import math
from plotly.subplots import make_subplots

# 1. ตั้งค่า Timezone (UTC +7)
ICT = timezone(timedelta(hours=7))
st.set_page_config(page_title="SCADA Dashboard", layout="wide")

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

st.set_page_config(page_title="Production Log System", layout="wide")

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
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต"])

# ================= DASHBOARD (FULL SYSTEM VIEW) =================
if menu == "Dashboard":
    st.title("📊 Production Dashboard (System Overview)")

    # ================= STANDARD =================
    PH_MIN, PH_MAX = 5.0, 6.0
    TEMP_COLOR_MIN, TEMP_COLOR_MAX = 30, 40
    PH_ANO_MIN, PH_ANO_MAX = 1, 1.5       # <--- เพิ่มบรรทัดนี้ (ปรับค่าตามมาตรฐานจริงของคุณ)
    TEMP_ANO_MIN, TEMP_ANO_MAX = 18, 22     # มาตรฐานอุณหภูมิ บ่ออโนไดซ์
    DEN_ANO_MIN, DEN_ANO_MAX = 0.5, 1.5  #เพิ่มค่ามาตรฐาน Density (ปรับตัวเลขตาม Spec ของสารเคมีที่โรงงานใช้)

    # ================= CACHE & DATA LOADING =================
    @st.cache_data(ttl=10)
    def load_color_logs():
        return supabase.table("color_tank_logs").select("*").order("recorded_at", desc=True).limit(200).execute().data

    @st.cache_data(ttl=10)
    def load_anodize_logs():
        return supabase.table("anodize_tank_logs").select("*").order("recorded_at", desc=True).limit(200).execute().data

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
        if not latest.empty:
            # สร้าง Subplots แบบ 2 แกน Y (ซ้าย pH, ขวา Temp)
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # 1. กราฟแท่ง pH (แกนซ้าย)
            fig.add_trace(
                go.Bar(
                    x=latest["tank_name"],
                    y=latest["ph_value"],
                    name="ค่า pH (Std: 5.0-6.0)",
                    marker_color="#98FB98",
                    text=latest["ph_value"],
                    textposition='auto',
                    offsetgroup=1, # จัดกลุ่มที่ 1
                ),
                secondary_y=False,
            )

            # 2. กราฟแท่ง อุณหภูมิ (แกนขวา)
            fig.add_trace(
                go.Bar(
                    x=latest["tank_name"],
                    y=latest["temperature"],
                    name="อุณหภูมิ (Std: 30-40 °C)",
                    marker_color="#AFEEEE",
                    text=latest["temperature"],
                    textposition='auto',
                    offsetgroup=2, # จัดกลุ่มที่ 2 (ทำให้แท่งวางข้างกัน)
                ),
                secondary_y=True,
            )

            # --- ตั้งค่าแกน Y ---
            fig.update_yaxes(
                title_text="<b>ค่า pH</b>", 
                secondary_y=False, 
                range=[0, 14], 
                dtick=1,
                title_font=dict(color="#22c55e"),
                tickfont=dict(color="#22c55e"),
                gridcolor='rgba(34, 197, 94, 0.1)' # เส้นกริดจางๆ ตามสีแกน
            )
            
            fig.update_yaxes(
                title_text="<b>อุณหภูมิ (°C)</b>", 
                secondary_y=True, 
                range=[0, 100],
                title_font=dict(color="#3b82f6"),
                tickfont=dict(color="#3b82f6"),
                showgrid=False # ปิดกริดฝั่งขวาเพื่อไม่ให้ลายตา
            )

            # --- เพิ่มเส้น Threshold (เส้นเกณฑ์มาตรฐาน) ---
            # เส้น pH
            fig.add_hline(y=PH_MIN, line_dash="dash", line_color="#166534", secondary_y=False)
            fig.add_hline(y=PH_MAX, line_dash="dash", line_color="#166534", secondary_y=False)
            
            # เส้น Temp
            fig.add_hline(y=TEMP_COLOR_MIN, line_dash="dot", line_color="#1d4ed8", secondary_y=True)
            fig.add_hline(y=TEMP_COLOR_MAX, line_dash="dot", line_color="#1d4ed8", secondary_y=True)

            # การตั้งค่า Layout
            fig.update_layout(
                title=dict(text="เปรียบเทียบค่า pH และอุณหภูมิ (ล่าสุดรายบ่อ)", x=0.5),
                xaxis_title="ชื่อบ่อสี",
                barmode="group", # คำสั่งสำคัญที่ทำให้แท่งวางคู่กัน
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=500,
                margin=dict(t=100) # เพิ่มพื้นที่ด้านบนให้ Legend
            )

            st.plotly_chart(fig, use_container_width=True)

    st.subheader("🚨 ตารางแจ้งเตือนบ่อสี")

    alert_data = []

    for _, row in latest.iterrows():
        tank = row["tank_name"]

        ph = row["ph_value"]
        temp = row["temperature"]

        alert_data.append({
            "Tank": tank,
            "pH": f"{get_status_icon(ph, PH_MIN, PH_MAX)} {ph:.2f}",
            "Temp (°C)": f"{get_status_icon(temp, TEMP_COLOR_MIN, TEMP_COLOR_MAX)} {temp:.1f}"
    })

    alert_df = pd.DataFrame(alert_data)

    st.dataframe(alert_df, use_container_width=True)
    # =========================================================
    # ================= INDIVIDUAL TANK VIEW =================
    # =========================================================
    st.markdown("---")
    st.subheader("🔍 วิเคราะห์ข้อมูลรายบ่อ (Individual Tank Analysis)")

    # ดึงรายชื่อบ่อสีที่มีใน logs มาให้เลือก
    if logs:
        df_all = pd.DataFrame(logs)
        df_all["recorded_at"] = pd.to_datetime(df_all["recorded_at"])
        
        # สร้าง Mapping ชื่อบ่อ
        tank_map = load_tanks()
        inv_map = {v: k for k, v in tank_map.items()}
        df_all["tank_name"] = df_all["tank_id"].map(inv_map)
        
        # ตัวเลือกบ่อ
        available_tanks = sorted(df_all["tank_name"].unique())
        selected_tank = st.selectbox("เลือกบ่อที่ต้องการดูรายละเอียด", available_tanks)

        # กรองข้อมูลเฉพาะบ่อที่เลือก
        tank_df = df_all[df_all["tank_name"] == selected_tank].sort_values("recorded_at")

        if not tank_df.empty:
            # สร้าง Column สำหรับกราฟ 2 ฝั่ง (pH และ Temp)
            g1, g2 = st.columns(2)

            with g1:
                fig_ph = go.Figure()
                fig_ph.add_trace(go.Scatter(
                    x=tank_df["recorded_at"],
                    y=tank_df["ph_value"],
                    mode='lines+markers',
                    name='pH Value',
                    line=dict(color='#22c55e', width=3),
                    marker=dict(size=8)
                ))
                # เพิ่มเส้นขอบเขตมาตรฐาน
                fig_ph.add_hrect(y0=PH_MIN, y1=PH_MAX, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Standard Range")
                
                fig_ph.update_layout(
                    title=f"แนวโน้มค่า pH: {selected_tank}",
                    xaxis_title="เวลาที่บันทึก",
                    yaxis_title="pH",
                    hovermode="x unified"
                )
                st.plotly_chart(fig_ph, use_container_width=True)

            with g2:
                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(
                    x=tank_df["recorded_at"],
                    y=tank_df["temperature"],
                    mode='lines+markers',
                    name='Temperature',
                    line=dict(color='#22c55e', width=3),
                    marker=dict(size=8)
                ))
                # เพิ่มเส้นขอบเขตมาตรฐาน
                fig_temp.add_hrect(y0=TEMP_COLOR_MIN, y1=TEMP_COLOR_MAX, fillcolor="orange", opacity=0.1, line_width=0, annotation_text="Standard Range")
                
                fig_temp.update_layout(
                    title=f"แนวโน้มอุณหภูมิ: {selected_tank}",
                    xaxis_title="เวลาที่บันทึก",
                    yaxis_title="อุณหภูมิ (°C)",
                    hovermode="x unified"
                )
                st.plotly_chart(fig_temp, use_container_width=True)
            
            # แสดงตารางข้อมูลล่าสุดของบ่อนี้
            with st.expander(f"ดูประวัติข้อมูลดิบของ {selected_tank}"):
                st.dataframe(tank_df[["recorded_at", "ph_value", "temperature"]].sort_values("recorded_at", ascending=False), use_container_width=True)

# =========================================================
    # ================= ANODIZE TREND ANALYSIS ================
    # =========================================================
    st.markdown("---")
    st.subheader("📈 วิเคราะห์แนวโน้มบ่ออโนไดซ์ (Anodize Detailed Trend)")

    logs_a = load_anodize_logs()

    if logs_a:
        df_a = pd.DataFrame(logs_a)
        df_a["recorded_at"] = pd.to_datetime(df_a["recorded_at"])
        
        # Mapping ชื่อบ่อ
        tank_map = load_tanks()
        inv_map = {v: k for k, v in tank_map.items()}
        df_a["tank_name"] = df_a["tank_id"].map(inv_map)
            # ================= ALERT TABLE =================
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
        # กรองข้อมูล
        ano_filtered = df_a[df_a["tank_name"] == selected_ano].sort_values("recorded_at")

        if not ano_filtered.empty:
            # สร้าง 3 คอลัมน์สำหรับ 3 กราฟ
            g1, g2, g3 = st.columns(3)

            # --- กราฟที่ 1: pH ---
            with g1:
                fig_ph = go.Figure()
                fig_ph.add_trace(go.Scatter(
                    x=ano_filtered["recorded_at"], y=ano_filtered["ph_value"],
                    mode='lines+markers', name='pH',
                    line=dict(color='#22c55e', width=2), marker=dict(size=6)
                ))
                fig_ph.add_hrect(y0=PH_ANO_MIN, y1=PH_ANO_MAX, fillcolor="green", opacity=0.1, line_width=0)
                fig_ph.update_layout(title="แนวโน้ม pH", height=350, margin=dict(t=50, b=20, l=10, r=10))
                st.plotly_chart(fig_ph, use_container_width=True)

            # --- กราฟที่ 2: Temperature ---
            with g2:
                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(
                    x=ano_filtered["recorded_at"], y=ano_filtered["temperature"],
                    mode='lines+markers', name='Temp',
                    line=dict(color='#3b82f6', width=2), marker=dict(size=6)
                ))
                fig_temp.add_hrect(y0=TEMP_ANO_MIN, y1=TEMP_ANO_MAX, fillcolor="blue", opacity=0.1, line_width=0)
                fig_temp.update_layout(title="แนวโน้มอุณหภูมิ (°C)", height=350, margin=dict(t=50, b=20, l=10, r=10))
                st.plotly_chart(fig_temp, use_container_width=True)

            # --- กราฟที่ 3: Density ---
            with g3:
                fig_den = go.Figure()
                fig_den.add_trace(go.Scatter(
                    x=ano_filtered["recorded_at"], y=ano_filtered["density"],
                    mode='lines+markers', name='Density',
                    line=dict(color='#a855f7', width=2), marker=dict(size=6)
                ))
                # ถ้ามีค่ามาตรฐาน Density (เช่น 1.05 - 1.10) สามารถเพิ่ม hrect ได้เหมือน pH
                # ส่วนในกราฟ Density (g3)
                fig_den.add_hrect(y0=DEN_ANO_MIN, y1=DEN_ANO_MAX, fillcolor="purple", opacity=0.1, line_width=0)
                fig_den.update_layout(title="แนวโน้มความหนาแน่น", height=350, margin=dict(t=50, b=20, l=10, r=10))
                st.plotly_chart(fig_den, use_container_width=True)

            # --- ตาราง Log ข้อมูล ---
            with st.expander(f"📋 รายละเอียดข้อมูลบันทึก {selected_ano}"):
                log_display = ano_filtered[["recorded_at", "ph_value", "temperature", "density"]].copy()
                log_display = log_display.sort_values("recorded_at", ascending=False)
                # จัดฟอร์แมตตัวเลขให้สวยงาม
                st.dataframe(
                    log_display.style.format({
                        "ph_value": "{:.2f}",
                        "temperature": "{:.1f}",
                        "density": "{:.3f}"
                    }), 
                    use_container_width=True
                )
        else:
            st.warning("ไม่พบข้อมูลบันทึกสำหรับบ่อนี้")
    else:
        st.info("ไม่มีข้อมูลในระบบ Anodize")
    # ================= AUTO REFRESH =================
    try:
        st_autorefresh(interval=10000, key="refresh")
    except:
        pass


# ================= RECORD PAGE =================
elif menu == "บันทึกข้อมูลการผลิต":
    st.title("📝 ระบบบันทึกข้อมูล")
    
    tab_main = st.tabs(["บ่อสี (Color Bath)", "บ่ออโนไดซ์ (Anodize)", "งานจิ๊ก (Jig System)"])

    # --- Tab 1: บ่อสี ---
    with tab_main[0]:
        st.header("🎨 บันทึกข้อมูลบ่อสี")
        color_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
        if color_tanks:
            selected_tank_name = st.selectbox("เลือกบ่อสี", list(color_tanks.keys()))
            detected_color = TANK_COLOR_MAP.get(selected_tank_name, "Black")
            render_color_bar(detected_color)
            
            with st.form("color_log_form"):
                ph = st.number_input("ค่า pH", step=0.1, format="%.2f")
                temp = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")
                if st.form_submit_button("บันทึกค่า"):
                    supabase.table("color_tank_logs").insert({
                        "tank_id": color_tanks[selected_tank_name], 
                        "ph_value": ph, "temperature": temp, 
                        "recorded_at": datetime.now(ICT).isoformat()
                    }).execute()
                    st.success("บันทึกข้อมูลบ่อสีสำเร็จ")

    # --- Tab 2: บ่ออโนไดซ์ ---
    with tab_main[1]:
        st.header("🧪 บันทึกข้อมูลบ่ออโนไดซ์")
        ano_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Anodize")
        if ano_tanks:
            sel_ano = st.selectbox("เลือกบ่ออโนไดซ์", list(ano_tanks.keys()))
            with st.form("ano_form"):
                ph_a = st.number_input("ค่า pH", step=0.01, format="%.2f")
                temp_a = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")
                den_a = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f")
                if st.form_submit_button("บันทึกข้อมูลอโนไดซ์"):
                    supabase.table("anodize_tank_logs").insert({
                        "tank_id": ano_tanks[sel_ano], "ph_value": ph_a,
                        "temperature": temp_a, "density": den_a,
                        "recorded_at": datetime.now(ICT).isoformat()
                    }).execute()
                    st.success("บันทึกข้อมูลอโนไดซ์สำเร็จ")

# --- Tab หลัก 3: ระบบงานจิ๊ก (Jig System) ---
    with tab_main[2]:
        sub_prod, sub_jig, sub_log = st.tabs(["📦 1. ลงทะเบียนสินค้า", "🛠️ 2. ลงทะเบียนจิ๊ก", "⚡ 3. บันทึกผลผลิต"])

        with sub_prod:
            st.subheader("เพิ่มสินค้าใหม่ลงระบบ")
            shape = st.selectbox("📐 เลือกรูปทรง", ["สี่เหลี่ยม", "ทรงกระบอกทึบ", "ทรงกระบอกกลวง"], key="shape_sel")
            with st.form("add_prod_form_fixed", clear_on_submit=True):
                c1, c2 = st.columns(2)
                p_code = c1.text_input("รหัสสินค้า *")
                p_name = c1.text_input("ชื่อสินค้า")
                s_finish = c1.text_input("พื้นผิว *", value="-")
                height = c2.number_input("ความยาว (H) [mm]", min_value=0.0)
                width, thickness, od, u_vol = 0.0, 0.0, 0.0, 0.0
                if shape == "สี่เหลี่ยม":
                    width = c2.number_input("กว้าง [mm]", min_value=0.0)
                    thickness = c2.number_input("หนา [mm]", min_value=0.0)
                    u_vol = height * width * thickness
                elif shape == "ทรงกระบอกทึบ":
                    od = c2.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0)
                    u_vol = math.pi * ((od/2)**2) * height
                else:
                    od = c2.number_input("OD [mm]", min_value=0.0)
                    thickness = c2.number_input("ความหนาเนื้อ [mm]", min_value=0.0)
                    id_inner = max(0.0, od - (2*thickness))
                    u_vol = math.pi * ((od/2)**2 - (id_inner/2)**2) * height

                st.info(f"💡 ปริมาตร: {u_vol:,.2f} mm³")
                if st.form_submit_button("➕ ลงทะเบียนสินค้า"):
                    if p_code:
                        # --- ส่วนตรวจสอบการซ้ำ ---
                        check_exist = supabase.table("products").select("product_code").eq("product_code", p_code).execute()
                        
                        if check_exist.data:
                            st.error(f"❌ รหัสสินค้า '{p_code}' นี้มีอยู่ในระบบแล้ว ไม่สามารถลงทะเบียนซ้ำได้")
                        else:
                            payload = {
                                "product_code": p_code, 
                                "product_name": p_name, 
                                "surface_finish": s_finish, 
                                "unit_volume": u_vol, 
                                "height": height, 
                                "width": width, 
                                "thickness": thickness, 
                                "depth": thickness, 
                                "shape": shape, 
                                "outer_diameter": od, 
                                "inner_diameter": id_inner if 'id_inner' in locals() else 0.0
                            }
                            supabase.table("products").insert(payload).execute()
                            st.success(f"✅ ลงทะเบียนรหัส {p_code} สำเร็จ!")
                    else: 
                        st.error("กรุณาระบุรหัสสินค้า")

        with sub_jig:
            st.subheader("เพิ่มรหัสจิ๊กใหม่")
            with st.form("add_jig_fixed", clear_on_submit=True):
                j_code = st.text_input("รหัสจิ๊ก(ตั้งรหัสเป็นปปปปดดววจิ๊กี่เท่าไหร่ เช่น 20260501001)", key="j_code_input").strip()
                if st.form_submit_button("ลงทะเบียนจิ๊ก"):
                    if j_code:
                        # --- ส่วนตรวจสอบการซ้ำ ---
                        check_jig = supabase.table("jigs").select("jig_model_code").eq("jig_model_code", j_code).execute()
                        
                        if check_jig.data:
                            st.error(f"❌ รหัสจิ๊ก '{j_code}' นี้มีอยู่ในระบบแล้ว")
                        else:
                            supabase.table("jigs").insert({"jig_model_code": j_code, "total_pcs_in_jig": 0}).execute()
                            st.success(f"✅ ลงทะเบียนจิ๊ก {j_code} สำเร็จ")
                    else: 
                        st.error("กรุณากรอกรหัสจิ๊ก")

        with sub_log:
            # 1. ดึงข้อมูลสินค้ามาทั้งหมด (เอาทั้ง ID, Code และ Name)
            prods_res = supabase.table("products").select("product_id, product_code, product_name").execute().data
            
            # 2. สร้าง Dictionary สำหรับ Mapping และ List สำหรับแสดงผลใน Selectbox
            if prods_res:
                # สร้างข้อความแสดงผล เช่น "P001 | อะลูมิเนียมเส้น"
                display_options = {
                    f"{p['product_code']} | {p['product_name']}": p['product_id'] 
                    for p in prods_res
                }
                
                jigs_data = supabase.table("jigs").select("jig_id, jig_model_code").execute().data
                available_jigs = []
                for j in (jigs_data or []):
                    status_res = supabase.table("jig_status").select("status_type").eq("jig_id", j["jig_id"]).order("updated_at", desc=True).limit(1).execute()
                    if not status_res.data or status_res.data[0]["status_type"] != "Finished":
                        available_jigs.append(j)

                if not available_jigs:
                    st.warning("❌ ไม่มีจิ๊กที่ใช้งานได้")
                else:
                    jig_map = {j['jig_model_code']: j['jig_id'] for j in available_jigs}
                    color_tanks_all = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
                    
                    if display_options and color_tanks_all:
                        sel_j = st.selectbox("เลือกจิ๊ก", list(jig_map.keys()), key="sel_j_log")
                        jig_id = jig_map[sel_j]
                        
                        # --- ส่วนที่เปลี่ยน: เลือกสินค้า ---
                        selected_display = st.selectbox(
                            "เลือกสินค้า (รหัส | ชื่อ)", 
                            options=list(display_options.keys()), 
                            key="sel_p_log"
                        )
                        # ดึง product_id จริงๆ ออกมาใช้งาน
                        selected_prod_id = display_options[selected_display]
                        
                        # ดึงข้อมูลสินค้าตัวที่เลือกมาเพื่อคำนวณปริมาตร
                        p_info = supabase.table("products").select("*").eq("product_id", selected_prod_id).single().execute().data
                        
                        action = st.radio("การทำงาน", ["🔵 บันทึกงานต่อ", "🟢 เสร็จสิ้นงาน"], key="action_radio")

                        if action == "🔵 บันทึกงานต่อ":
                            sel_c_new = st.selectbox("เลือกสี", sorted(set(TANK_COLOR_MAP.values())), key="sel_c_log")
                            filtered_tanks = {n: i for n, i in color_tanks_all.items() if TANK_COLOR_MAP.get(n) == sel_c_new}
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
                                    # ใช้ selected_prod_id ในการบันทึก
                                    supabase.table("jig_usage_log").insert({
                                        "product_id": selected_prod_id, 
                                        "jig_id": jig_id, 
                                        "color": sel_c_new, 
                                        "tank_id": filtered_tanks[sel_tank_name], 
                                        "total_pieces": total_pcs, 
                                        "total_volume": total_vol, 
                                        "recorded_date": datetime.now(ICT).isoformat()
                                    }).execute()
                                    
                                    supabase.table("jig_status").upsert({
                                        "jig_id": jig_id, 
                                        "status_type": "In-Process", 
                                        "current_tank_id": filtered_tanks[sel_tank_name], 
                                        "updated_at": datetime.now(ICT).isoformat()
                                    }).execute()
                                    
                                    st.success("บันทึกสำเร็จ")
                                    st.rerun()
                    elif action == "🟢 เสร็จสิ้นงาน":
                        if st.button("🏁 ยืนยันเสร็จสิ้นงาน"):
                            supabase.table("jig_status").upsert({"jig_id": jig_id, "status_type": "Finished", "current_tank_id": None, "updated_at": datetime.now(ICT).isoformat()}).execute()
                            st.success("งานเสร็จสิ้น")
                            st.rerun()
