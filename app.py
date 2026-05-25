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
import json

# 1. ตั้งค่า Timezone (UTC +7)
ICT = timezone(timedelta(hours=7))
st.set_page_config(page_title="Gissco Production Line and Dashboard", layout="wide")

# --- Configuration ---
COLOR_HEX_MAP = {
    # ===== COLOR TANK =====
    "Black": "#1E1E1E",
    "Red": "#DC2626",
    "Dark Red": "#7F1D1D",
    "Violet": "#7C3AED",
    "Green": "#16A34A",
    "Banana leaf Green": "#84CC16",
    "Gold": "#EAB308",
    "Orange": "#F97316",
    "Light Blue": "#38BDF8",
    "Blue": "#2563EB",
    "Dark Blue": "#1D4ED8",
    "Pink": "#EC4899",
    "Copper": "#B45309",
    "Titanium": "#6B7280",
    "Dark Titanium": "#4B5563",
    "Rose Gold": "#BE6D6D",

    # ===== CHEMICAL =====
    "Nitric": "#FDE68A",      # ส้มอ่อนจาง
    "Sealer": "#94A3B8",      # เทาอมฟ้า
    "Anodize": "#67E8F9",     # ฟ้า cyan อ่อน
    "Sodium": "#FDE68A", 
    # ===== UTILITY =====
    "RO": "#F3F4F6",          # เทาจางเกือบขาว
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
def normalize_text(text):
    return str(text).lower().replace(" ", "").replace("_", "")

def get_hex_from_name(name):

    name_clean = normalize_text(name)

    # เรียงชื่อสีจากยาว -> สั้น
    sorted_colors = sorted(
        COLOR_HEX_MAP.keys(),
        key=lambda x: len(normalize_text(x)),
        reverse=True
    )

    for color_name in sorted_colors:

        color_clean = normalize_text(color_name)

        if color_clean in name_clean:
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
#=============================================================================
@st.cache_data(ttl=30)
def load_products():
    try:
        return supabase.table("products") \
            .select("product_id, product_code, product_name") \
            .execute().data or []
    except:
        return []

#================================================================================
def lighten_color(hex_color, factor=0.45):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)

    return f"rgb({r},{g},{b})"
#=================================================================================
@st.cache_data(ttl=60)
def load_tank_color_map():
    try:
        rows = supabase.table("tanks") \
            .select("tank_name, color_name") \
            .execute().data or []

        return {
            row["tank_name"]: row["color_name"]
            for row in rows
        }

    except Exception as e:
        st.error(f"โหลดสีบ่อไม่สำเร็จ: {e}")
        return {}

tank_color_map = load_tank_color_map()
#===================================================================================
# =============================================================================
# 📊 ฟังก์ชันสำหรับสร้างตารางสรุป แดชบอร์ดบ่อสี ประจำวันที่เลือก
# =============================================================================
def render_color__table(target_date_str):
    st.markdown("#### 🎨 ตารางสรุปค่าล่าสุด บ่อสี (Color Tanks)")
    
    start_dt = f"{target_date_str}T00:00:00"
    end_dt = f"{target_date_str}T23:59:59"

    # เกณฑ์มาตรฐานของบ่อสี
    COLOR_PH_MIN, COLOR_PH_MAX = 4.5, 6.5
    COLOR_TEMP_MIN, COLOR_TEMP_MAX = 20.0, 35.0

    # ดึงข้อมูลบันทึกในวันนั้น
    color_logs = supabase.table("color_tank_logs")\
        .select("*")\
        .gte("recorded_at", start_dt)\
        .lte("recorded_at", end_dt)\
        .order("recorded_at", desc=True)\
        .execute().data or []

    if not color_logs:
        st.info("📅 ดึงข้อมูลแดชบอร์ด: ไม่มีบันทึกข้อมูลบ่อสีในวันที่เลือก")
        return

    df_logs = pd.DataFrame(color_logs)
    df_logs["recorded_at"] = pd.to_datetime(df_logs["recorded_at"]).dt.tz_convert(ICT)
    df_logs["เวลา"] = df_logs["recorded_at"].dt.strftime("%H:%M")

    # ยุบข้อมูลเลือกเอาเฉพาะรายการ "ล่าสุดของแต่ละบ่อ" ประจำวันนั้น
    latest_per_tank = df_logs.sort_values("recorded_at").groupby("tank_name_snapshot").last().reset_index()

    display_rows = []
    for _, row in latest_per_tank.iterrows():
        t_name = row["tank_name_snapshot"]
        v_time = row["เวลา"]
        v_ph = float(row["ph_value"] or 0)
        v_temp = float(row["temperature"] or 0)

        # 🔴 เช็คเงื่อนไขทำตัวหนังสือสีแดงหนาถ้าหลุดเกณฑ์
        ph_style = "color: #DC2626; font-weight: bold;" if (v_ph < COLOR_PH_MIN or v_ph > COLOR_PH_MAX) else ""
        temp_style = "color: #DC2626; font-weight: bold;" if (v_temp < COLOR_TEMP_MIN or v_temp > COLOR_TEMP_MAX) else ""

        display_rows.append({
            "ชื่อบ่อสี": t_name,
            "เวลาอัปเดตล่าสุด": v_time,
            "ค่า pH": f"<span style='{ph_style}'>{v_ph:.2f}</span>" if ph_style else f"{v_ph:.2f}",
            "อุณหภูมิ (°C)": f"<span style='{temp_style}'>{v_temp:.1f}</span>" if temp_style else f"{v_temp:.1f}"
        })

    df_display = pd.DataFrame(display_rows)
    # แสดงผลตารางผ่าน HTML เพื่อให้ CSS สีแดงทำงานได้
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


# =============================================================================
# 🧪 ฟังก์ชันสำหรับสร้างตารางสรุป แดชบอร์ดบ่อเคมี ประจำวันที่เลือก
# =============================================================================
def render_chemical__table(target_date_str):
    st.markdown("#### 🧪 ตารางสรุปค่าล่าสุด บ่อสารเคมี (Chemical Tanks)")
    
    start_dt = f"{target_date_str}T00:00:00"
    end_dt = f"{target_date_str}T23:59:59"

    # เกณฑ์มาตรฐานบ่อเคมีทั่วไป
    CHEM_PH_MIN, CHEM_PH_MAX = 1.0, 3.5
    CHEM_TEMP_MIN, CHEM_TEMP_MAX = 15.0, 35.0
    CHEM_DEN_MIN, CHEM_DEN_MAX = 1.000, 1.150

    chem_logs = supabase.table("anodize_tank_logs")\
        .select("*, tanks(tank_name)")\
        .gte("recorded_at", start_dt)\
        .lte("recorded_at", end_dt)\
        .order("recorded_at", desc=True)\
        .execute().data or []

    if not chem_logs:
        st.info("📅 ดึงข้อมูลแดชบอร์ด: ไม่มีบันทึกข้อมูลบ่อสารเคมีในวันที่เลือก")
        return

    df_chem = pd.DataFrame(chem_logs)
    df_chem["recorded_at"] = pd.to_datetime(df_chem["recorded_at"]).dt.tz_convert(ICT)
    df_chem["tank_name"] = df_chem["tanks"].apply(lambda x: x.get("tank_name") if isinstance(x, dict) else "-")
    df_chem["เวลา"] = df_chem["recorded_at"].dt.strftime("%H:%M")

    # ดึงค่าบันทึกล่าสุดรายบ่อ
    latest_chem = df_chem.sort_values("recorded_at").groupby("tank_name").last().reset_index()

    chem_display_rows = []
    for _, row in latest_chem.iterrows():
        t_name = row["tank_name"]
        v_time = row["เวลา"]
        v_ph = float(row["ph_value"] or 0)
        v_temp = float(row["temperature"] or 0)
        v_den = float(row["density"] or 0)

        # แยกประเภทบ่อซีล (Seal / Sealer)
        is_seal = "seal" in t_name.lower() or "sealer" in t_name.lower()

        # ตรวจสอบอุณหภูมิ (ตรวจทุกบ่อ)
        temp_style = "color: #DC2626; font-weight: bold;" if (v_temp < CHEM_TEMP_MIN or v_temp > CHEM_TEMP_MAX) else ""
        
        if is_seal:
            # 💡 บ่อซีล ให้ตรวจสอบและดึงค่า pH ขึ้นมาเช็คสีแดงด้วยตามข้อกำหนดใหม่ (ส่วน Density บ่อซีลให้เป็นขีดแดชไว้)
            ph_style = "color: #DC2626; font-weight: bold;" if (v_ph < CHEM_PH_MIN or v_ph > CHEM_PH_MAX) else ""
            den_text = "<span style='color: #94A3B8;'>-</span>"
        else:
            # บ่อเคมีปกติ เช็คทั้ง pH และ Density 
            ph_style = "color: #DC2626; font-weight: bold;" if (v_ph < CHEM_PH_MIN or v_ph > CHEM_PH_MAX) else ""
            den_style = "color: #DC2626; font-weight: bold;" if (v_den < CHEM_DEN_MIN or v_den > CHEM_DEN_MAX) else ""
            den_text = f"<span style='{den_style}'>{v_den:.3f}</span>" if den_style else f"{v_den:.3f}"

        ph_text = f"<span style='{ph_style}'>{v_ph:.2f}</span>" if ph_style else f"{v_ph:.2f}"
        t_text = f"<span style='{temp_style}'>{v_temp:.1f}</span>" if temp_style else f"{v_temp:.1f}"

        chem_display_rows.append({
            "ชื่อบ่อสารเคมี": t_name,
            "เวลาอัปเดตล่าสุด": v_time,
            "ค่า pH": ph_text,
            "อุณหภูมิ (Temp °C)": t_text,
            "ความหนาแน่น (Density)": den_text
        })

    df_chem_display = pd.DataFrame(chem_display_rows)
    st.write(df_chem_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
#====================================================================================
def render_tank_map(selected_tank_name=None):
    selected_tank_name = selected_tank_name or ""

    html = """
    <style>
    body{
        margin:0;
        padding:0;
    }

    .plant-map{
        position:relative;
        width:100%;
        min-width:1150px;
        height:760px;
        background:#eef1f4;
        border:2px solid #999;
        margin:auto;
        overflow:auto;
        border-radius:12px;
    }

    .tank{
        position:absolute;
        color:white;
        font-weight:bold;
        font-size:13px;
        border-radius:8px;
        padding:4px;
        text-align:center;
        border:1px solid rgba(0,0,0,0.25);
        box-sizing:border-box;
        font-family:Arial;
        box-shadow:0 2px 5px rgba(0,0,0,0.15);
    }

    .vertical{
        writing-mode:vertical-rl;
        text-orientation:mixed;
    }
    .circle-tank{
    border-radius:50% !important;
    display:flex;
    align-items:center;
    justify-content:center;
    }

    .ro{
        background:#d7ffff !important;
        color:black !important;
    }

    .tank.clickable{
        cursor:pointer;
        transition:transform .12s ease, box-shadow .12s ease, outline .12s ease;
    }

    .tank.clickable:hover{
        transform:translateY(-2px);
        box-shadow:0 8px 18px rgba(0,0,0,.25);
        z-index:5;
    }

    .tank.selected{
        outline:4px solid #ffeb3b;
        box-shadow:0 0 0 3px rgba(0,0,0,.35), 0 10px 22px rgba(0,0,0,.35);
        z-index:10;
    }
    </style>

    <div class="plant-map">

        <!-- TOP ROW -->

        <div class="tank" data-tank="5Black"
            style="left:0px;top:0px;width:80px;height:80px;background:#111;">
            5.Black
        </div>

        <div class="tank" data-tank="2Red"
            style="left:140px;top:0px;width:70px;height:80px;background:red;">
            2.Red
        </div>

        <div class="tank" data-tank="3Violet"
            style="left:210px;top:0px;width:60px;height:80px;background:purple;">
            3.Violet
        </div>

        <div class="tank" data-tank="8Green"
            style="left:295px;top:0px;width:70px;height:80px;background:green;">
            8.Green
        </div>

        <div class="tank" data-tank="17Black"
            style="left:365px;top:0px;width:65px;height:80px;background:#222;">
            17.Black
        </div>

        <div class="tank" data-tank="15Gold"
            style="left:455px;top:0px;width:70px;height:80px;background:#d4af00;color:black;">
            15.Gold
        </div>

        <div class="tank" data-tank="9Orange"
            style="left:525px;top:0px;width:65px;height:80px;background:orange;">
            9.Orange
        </div>

        <div class="tank" data-tank="10LightBlue"
            style="left:620px;top:0px;width:70px;height:80px;background:cyan;color:black;">
            10.Light Blue
        </div>

        <div class="tank" data-tank="6BananaLeafGreen"
            style="left:690px;top:0px;width:70px;height:80px;background:#7fff00;color:black;">
            6.Banana
        </div>

        <div class="tank" data-tank="16Blue"
            style="left:785px;top:0px;width:70px;height:80px;background:blue;">
            16.Blue
        </div>

        <div class="tank" data-tank="4DarkBlue"
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

        <div class="tank vertical" data-tank="AlmiteSealer"
            style="left:0px;top:180px;width:60px;height:275px;background:#777;">
            AlmiteSealerLiquid
        </div>

        <div class="tank" data-tank="20Black"
            style="left:270px;top:200px;width:80px;height:50px;background:#111;">
            20.Black
        </div>

        <div class="tank" data-tank="1DarkRedB"
            style="left:270px;top:252px;width:80px;height:35px;background:darkred;">
            1.DarkRedB
        </div>

        <div class="tank vertical" data-tank="7Pink"
            style="left:380px;top:210px;width:85px;height:130px;background:magenta;">
            7.Pink
        </div>

        <div class="tank" data-tank="HotSealH60"
            style="left:540px;top:190px;width:85px;height:125px;background:#777;">
            HotSeal
        </div>
        <div class="tank vertical" data-tank="11Gold"
            style="left:540px;top:320px;width:85px;height:125px;background:#d4af00;color:black;">
            11.Gold
        </div>

        <!-- RIGHT -->

        <div class="tank" data-tank="1DarkRedA"
            style="left:785px;top:200px;width:65px;height:55px;background:darkred;">
            1.DarkRedA
        </div>

        <div class="tank" data-tank="19Copper"
            style="left:785px;top:257px;width:65px;height:55px;background:#d9a27f;color:black;">
            19.Copper
        </div>

        <div class="tank" data-tank="12Titanium"
            style="left:785px;top:314px;width:65px;height:55px;background:#777;">
            12.Titanium
        </div>

        <div class="tank" data-tank="14RoseGold"
            style="left:785px;top:371px;width:65px;height:55px;background:plum;">
            14.RoseGold
        </div>

        <!-- ANODIZE -->

        <div class="tank vertical" data-tank="Anodize Tank 1"
            style="left:890px;top:520px;width:140px;height:190px;background:#ccc;color:black;">
            AnodizedPPool1
        </div>

        <!-- DARK TITANIUM -->

        <div class="tank circle-tank" data-tank="13DarkTitanium"
            style="left:295px;top:110px;width:70px;height:70px;background:#666;">
            13.DarkTitanium
        </div>
        
        <div class="tank circle-tank"
            style="left:370px;top:110px;width:70px;height:70px;background:#666;">
        </div>

        <!-- ORANGE OIL -->

        <div class="tank circle-tank" data-tank="18OrangeOil"
            style="left:620px;top:110px;width:70px;height:70px;background:#dd6600;">
            18.OrangeOil
        </div>
        
        <div class="tank circle-tank"
            style="left:690px;top:110px;width:70px;height:70px;background:#dd6600;">
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

    <script>
    const selectedTank = "__SELECTED_TANK__";
    
    function selectTank(tankName) {
        const payload = JSON.stringify({
            tank: tankName,
            updatedAt: Date.now()
        });
    
        try {
            window.parent.localStorage.setItem("selected_tank_payload", payload);
        } catch (error) {
            localStorage.setItem("selected_tank_payload", payload);
        }
    
        document.querySelectorAll(".tank[data-tank]").forEach((item) => {
            item.classList.toggle("selected", item.dataset.tank === tankName);
        });
    }
    
    document.querySelectorAll(".tank[data-tank]").forEach((tank) => {
        tank.classList.add("clickable");
        tank.setAttribute("role", "button");
        tank.setAttribute("tabindex", "0");
        tank.title = "คลิกเพื่อกรอกข้อมูลบ่อ " + tank.dataset.tank;
    
        if (tank.dataset.tank === selectedTank) {
            tank.classList.add("selected");
        }
    
        tank.addEventListener("click", () => selectTank(tank.dataset.tank));
        tank.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectTank(tank.dataset.tank);
            }
        });
    });
    </script>
    """

    html = html.replace("__SELECTED_TANK__", selected_tank_name)
    components.html(html, height=750, scrolling=True)

#-----------------------------------------------------------------------
@st.dialog("บันทึกข้อมูลบ่อ")
def tank_record_dialog(clicked_tank_name, color_tanks, chemical_tanks):
    if clicked_tank_name in color_tanks:
        st.subheader(f"🎨 บ่อสี: {clicked_tank_name}")

        detected_color = tank_color_map.get(clicked_tank_name, "Gray")
        render_color_bar(detected_color)

        with st.form("dialog_color_log_form", clear_on_submit=True):
            ph = st.number_input("ค่า pH", step=0.1, format="%.2f")
            temp = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")

            if st.form_submit_button("บันทึกค่า"):
                supabase.table("color_tank_logs").insert({
                "tank_id": color_tanks[clicked_tank_name],
                "tank_name_snapshot": clicked_tank_name,
                "ph_value": ph,
                "temperature": temp,
                "recorded_at": datetime.now(ICT).isoformat()
            }).execute()

                st.success("✅ บันทึกข้อมูลบ่อสีสำเร็จ")
                st.session_state["open_tank_dialog"] = False
                time.sleep(1)
                st.rerun()

    elif clicked_tank_name in chemical_tanks:
        st.subheader(f"🧪 บ่อสารเคมี: {clicked_tank_name}")

        is_sealer = "sealer" in clicked_tank_name.lower() or "seal" in clicked_tank_name.lower()

        # ปรับการแจ้งเตือน
        if is_sealer:
            st.info(f"💡 บ่อ {clicked_tank_name}: บันทึกค่า **Temperature และ pH**")
        else:
            st.info(f"💡 บ่อ {clicked_tank_name}: บันทึกค่า **Temp, pH และ Density**")

        with st.form("dialog_chemical_log_form", clear_on_submit=True):
            temp_val = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")

            # แยกเงื่อนไข: บ่อ Sealer ให้เก็บ pH ได้ แต่ไม่ต้องเก็บ Density (ความหนาแน่น)
            if is_sealer:
                ph_val = st.number_input("ค่า pH", step=0.01, format="%.2f")
                den_val = 0.0  # บ่อ seal ไม่เก็บค่า density ให้เป็น 0.0 ไว้เหมือนเดิม
            else:
                ph_val = st.number_input("ค่า pH", step=0.01, format="%.2f")
                den_val = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f")

            if st.form_submit_button("💾 บันทึกข้อมูล"):
                payload = {
                    "tank_id": chemical_tanks[clicked_tank_name],
                    "tank_name_snapshot": clicked_tank_name,
                    "temperature": temp_val,
                    "ph_value": ph_val,    # บันทึกค่า pH ที่กรอกเข้าไป
                    "density": den_val,    # บันทึกค่า density ตามที่ระบุข้างต้น
                    "recorded_at": datetime.now(ICT).isoformat()
                }

                supabase.table("anodize_tank_logs").insert(payload).execute()
                st.success(f"✅ บันทึกข้อมูลบ่อ {clicked_tank_name} สำเร็จ")
                st.session_state["open_tank_dialog"] = False
                time.sleep(1)
                st.rerun()

    else:
        st.warning(
            f"ไม่พบบ่อ `{clicked_tank_name}` ในฐานข้อมูล tanks "
            "กรุณาเช็คชื่อ data-tank ให้ตรงกับ tank_name"
        )


#=========================================================================
def get_pk(row, candidates):
    for col in candidates:
        if col in row and row[col] is not None:
            return col, row[col]
    return None, None

def delete_row(table, id_col, id_val):
    return supabase.table(table).delete().eq(id_col, id_val).execute()

def update_row(table, id_col, id_val, payload):
    return supabase.table(table).update(payload).eq(id_col, id_val).execute()

# ================= 3. EDIT DATA (ปรับให้โชว์ รหัส + ชื่อสินค้า) =================
# --- ฟังก์ชันเสริมสำหรับระบบจัดการข้อมูล (วางไว้ก่อน show_data_editor หรือรวมไว้ที่เดียวกัน) ---
def get_pk(data, possible_keys):
    """ช่วยหา primary key จากข้อมูลที่ดึงมา"""
    for key in possible_keys:
        if key in data:
            return key, data[key]
    return None, None

def update_row(table, id_col, id_val, data):
    """ฟังก์ชันกลางสำหรับอัปเดตข้อมูล"""
    return supabase.table(table).update(data).eq(id_col, id_val).execute()

def delete_row(table, id_col, id_val):
    """ฟังก์ชันกลางสำหรับลบข้อมูล"""
    return supabase.table(table).delete().eq(id_col, id_val).execute()

# ================= 3. EDIT DATA (เวอร์ชันอัปเกรดแยก Tab) =================
def show_data_editor():
    st.title("🛠️ จัดการ แก้ไข และลบข้อมูล")

    # --- ส่วนตัวกรองวันที่ (ปรับให้จำค่า ICT ได้ถูกต้อง) ---
    st.info("💡 เลือกวันที่เพื่อดูรายการบันทึกของวันนั้นๆ")
    # ใช้ datetime.now(ICT) เพื่อให้วันที่เริ่มต้นเป็นวันที่ไทยปัจจุบันเสมอ
    filter_date = st.date_input("เลือกวันที่ต้องการแก้ไขข้อมูล", value=datetime.now(ICT).date())
    filter_date_str = filter_date.isoformat()

    tab_product, tab_jig, tab_jiglog, tab_color, tab_chemical = st.tabs([
        "สินค้า", "จิ๊ก", "บันทึกงานจิ๊ก", "บ่อสี", "บ่อสารเคมี"
    ])

    with tab_product:
        st.subheader("📦 แก้ไข / ลบสินค้า")
        try:
            products = supabase.table("products") \
                .select("*") \
                .order("product_code") \
                .execute().data or []
        
        except Exception as e:
            st.error(f"โหลดข้อมูลสินค้าไม่สำเร็จ: {e}")
            products = []

        if not products:
            st.info("ยังไม่มีข้อมูลสินค้า")
        else:
            product_map = {f"{p.get('product_code', '')} | {p.get('product_name', '')}": p for p in products}
            selected_label = st.selectbox("เลือกสินค้า", list(product_map.keys()), key="edit_product_select")
            p = product_map[selected_label]

            with st.form("edit_product_form"):

                # =====================================================
                # โหลดค่าปัจจุบัน
                # =====================================================
            
                current_shape = p.get("shape") or "สี่เหลี่ยม"
            
                shape_options = [
                    "สี่เหลี่ยม",
                    "ทรงกระบอกทึบ",
                    "ทรงกระบอกกลวง"
                ]
            
                if current_shape in shape_options:
                    shape_index = shape_options.index(current_shape)
                else:
                    shape_index = 0
            
                # =====================================================
                # ข้อมูลพื้นฐาน
                # =====================================================
            
                c1, c2 = st.columns(2)
            
                product_code = c1.text_input(
                    "รหัสสินค้า",
                    value=p.get("product_code", "")
                )
            
                product_name = c1.text_input(
                    "ชื่อสินค้า",
                    value=p.get("product_name", "")
                )
            
                surface_finish = c1.text_input(
                    "พื้นผิว",
                    value=p.get("surface_finish", "")
                )
            
                # =====================================================
                # เลือกรูปทรง
                # =====================================================
            
                shape = c1.selectbox(
                    "📐 เลือกรูปทรง",
                    shape_options,
                    index=shape_index,
                    key=f"edit_shape_{p['product_id']}"
                )
            
                # =====================================================
                # โหลดค่ามิติเดิม
                # =====================================================
            
                height = c2.number_input(
                    "ความยาว/ความสูง (H) [mm]",
                    min_value=0.0,
                    value=float(p.get("height") or 0)
                )
            
                width = 0.0
                thickness = 0.0
                od = 0.0
                id_inner = 0.0
            
                # =====================================================
                # สี่เหลี่ยม (ทรงบล็อกสี่เหลี่ยมมุมฉาก)
                # สูตรพื้นที่ผิวเดิม = 2*(กว้าง*ยาว + กว้าง*หนา + ยาว*หนา)
                # =====================================================
                if shape == "สี่เหลี่ยม":
                
                    width = c2.number_input(
                        "กว้าง [mm]",
                        min_value=0.0,
                        value=float(p.get("width") or 0)
                    )
                
                    thickness = c2.number_input(
                        "สูง/หนา [mm]",
                        min_value=0.0,
                        value=float(p.get("thickness") or 0)
                    )
                
                    # คำนวณพื้นที่ผิวรวมของกล่องสี่เหลี่ยม
                    unit_surface_area = 2 * ((width * height) + (width * thickness) + (height * thickness))
                
                # =====================================================
                # กระบอกทึบ
                # สูตรพื้นที่ผิว = (2 * pi * r * h) + (2 * pi * r^2)
                # =====================================================
                elif shape == "ทรงกระบอกทึบ":
                
                    od = c2.number_input(
                        "เส้นผ่านศูนย์กลาง (OD) [mm]",
                        min_value=0.0,
                        value=float(p.get("outer_diameter") or 0)
                    )
                
                    r_outer = od / 2
                    # พื้นที่ผิวข้าง + พื้นที่หน้าตัดหัวท้าย
                    unit_surface_area = (2 * math.pi * r_outer * height) + (2 * math.pi * (r_outer ** 2))
                
                # =====================================================
                # กระบอกกลวง (เช่น ท่อ)
                # สูตรพื้นที่ผิว = พื้นที่ผิวข้างนอก + พื้นที่ผิวข้างใน + พื้นที่หน้าตัดวงแหวนหัวท้าย 2 ฝั่ง
                # =====================================================
                else:
                
                    od = c2.number_input(
                        "เส้นผ่านศูนย์กลาง (OD) [mm]",
                        min_value=0.0,
                        value=float(p.get("outer_diameter") or 0)
                    )
                
                    thickness = c2.number_input(
                        "ความหนาของเนื้อชิ้นงาน [mm]",
                        min_value=0.0,
                        value=float(p.get("thickness") or 0)
                    )
                
                    id_inner = max(0.0, od - (2 * thickness))
                    
                    r_outer = od / 2
                    r_inner = id_inner / 2
                
                    # 1. พื้นที่ผิวข้างนอก = 2 * pi * R * H
                    side_outer = 2 * math.pi * r_outer * height
                    # 2. พื้นที่ผิวข้างใน = 2 * pi * r * H
                    side_inner = 2 * math.pi * r_inner * height
                    # 3. พื้นที่หน้าตัดวงแหวนหัวท้าย 2 ด้าน = 2 * pi * (R^2 - r^2)
                    base_rings = 2 * math.pi * ((r_outer ** 2) - (r_inner ** 2))
                
                    unit_surface_area = side_outer + side_inner + base_rings
                
                # =====================================================
                # แสดงพื้นที่ผิวรวม
                # =====================================================
                st.info(f"💡 พื้นที่ผิวใหม่: {unit_surface_area:,.2f} mm²")
            
                # =====================================================
                # แสดงปริมาตร
                # =====================================================
            
                st.info(f"💡 พื้นที่ผิวใหม่: {unit_surface_area:,.2f} mm²")
            
                # =====================================================
                # BUTTONS
                # =====================================================
            
                col_save, col_delete = st.columns(2)
            
                # =====================================================
                # SAVE
                # =====================================================
            
                if col_save.form_submit_button("💾 บันทึกสินค้า"):
            
                    try:
            
                        update_row(
                            "products",
                            "product_id",
                            p["product_id"],
                            {
                                "product_code": product_code,
                                "product_name": product_name,
                                "surface_finish": surface_finish,
                                "shape": shape,
                                "height": height,
                                "width": width,
                                "thickness": thickness,
                                "outer_diameter": od,
                                "inner_diameter": id_inner,
                                "unit_surface_area": unit_volume
                            }
                        )
            
                        st.success("บันทึกข้อมูลสินค้าแล้ว")
                        time.sleep(1)
                        st.rerun()
            
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")
            
                # =====================================================
                # DELETE
                # =====================================================
            
                if col_delete.form_submit_button("🗑️ ลบสินค้า"):
            
                    try:
            
                        delete_row(
                            "products",
                            "product_id",
                            p["product_id"]
                        )
            
                        st.success("ลบสินค้าแล้ว")
                        time.sleep(1)
                        st.rerun()
            
                    except Exception as e:
                        st.error(f"ลบไม่ได้ อาจมีข้อมูลอื่นอ้างอิงสินค้านี้อยู่: {e}")

    with tab_jig:
        st.subheader("🛠️ แก้ไข / ลบจิ๊ก")
        try:
            jigs = supabase.table("jigs") \
                .select("*") \
                .order("jig_model_code") \
                .execute().data or []
        
        except Exception as e:
            st.error(f"โหลดข้อมูลจิ๊กไม่สำเร็จ: {e}")
            jigs = []

        if not jigs:
            st.info("ยังไม่มีข้อมูลจิ๊ก")
        else:
            jig_map = {f"{j.get('jig_model_code', '')} | Lot: {j.get('lot_no', '')}": j for j in jigs}
            selected_label = st.selectbox("เลือกจิ๊ก", list(jig_map.keys()), key="edit_jig_select")
            j = jig_map[selected_label]

            with st.form("edit_jig_form"):
                jig_model_code = st.text_input("รหัสจิ๊ก", value=j.get("jig_model_code", ""))
                lot_no = st.text_input("Lot No.", value=j.get("lot_no", ""))

                col_save, col_delete = st.columns(2)
                if col_save.form_submit_button("💾 บันทึกจิ๊ก"):
                    try:
                        update_row("jigs", "jig_id", j["jig_id"], {
                            "jig_model_code": jig_model_code,
                            "lot_no": lot_no,
                        })
                        st.success("บันทึกข้อมูลจิ๊กแล้ว")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")

                if col_delete.form_submit_button("🗑️ ลบจิ๊ก"):
                    try:
                        delete_row("jigs", "jig_id", j["jig_id"])
                        st.success("ลบจิ๊กแล้ว")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"ลบไม่ได้ อาจมี log อ้างอิงอยู่: {e}")

    with tab_jiglog:

        start_of_day = f"{filter_date_str}T00:00:00+07:00"
        end_of_day = f"{filter_date_str}T23:59:59+07:00"

        st.subheader(f"⚡ รายการบันทึกจิ๊กของวันที่ {filter_date.strftime('%d/%m/%Y')}")

        logs = (
            supabase.table("jig_usage_log")
            .select("*, products(product_code, product_name), jigs(jig_model_code)")
            .gte("recorded_date", start_of_day)
            .lte("recorded_date", end_of_day)
            .order("recorded_date", desc=True)
            .execute()
            .data
            or []
        )

        if not logs:
            st.warning(f"📅 ไม่มีข้อมูลบันทึกงานจิ๊กในวันที่ {filter_date}")

        else:

            log_map = {}

            for l in logs:

                dt_ict = datetime.fromisoformat(
                    l.get("recorded_date").replace("Z", "+00:00")
                ).astimezone(ICT)

                time_str = dt_ict.strftime("%H:%M")

                j_code = l.get("jigs", {}).get("jig_model_code", "N/A")
                p_code = l.get("products", {}).get("product_code", "N/A")

                label = f"⏰ {time_str} | จิ๊ก: {j_code} | สินค้าเดิม: {p_code}"

                log_map[label] = l

            selected_label = st.selectbox(
                "เลือกรายการที่ต้องการจัดการ",
                list(log_map.keys()),
                key="edit_jiglog_sel"
            )

            log = log_map[selected_label]

            id_col, id_val = get_pk(
                log,
                ["log_id", "id", "jig_usage_log_id"]
            )

            # =====================================================
            # โหลดสินค้า
            # =====================================================

            all_products = (
                supabase.table("products")
                .select("product_id, product_code, product_name")
                .order("product_code")
                .execute()
                .data
                or []
            )

            prod_options = {
                f"{p['product_code']} | {p['product_name']}": p["product_id"]
                for p in all_products
            }

            option_list = list(prod_options.keys())

            current_prod_id = log.get("product_id")

            current_index = 0

            for i, label in enumerate(option_list):

                if prod_options[label] == current_prod_id:
                    current_index = i
                    break

            # =====================================================
            # โหลดบ่อสี
            # =====================================================

            tank_rows = (
                supabase.table("tanks")
                .select("tank_name")
                .execute()
                .data
                or []
            )

            tank_names = sorted([
                t["tank_name"]
                for t in tank_rows
                if t.get("tank_name")
            ])

            # =====================================================
            # FORM
            # =====================================================
            # =====================================================
            # เลือกสี (อยู่นอก form)
            # =====================================================
            
            color_options = [
                "Clear",
                "Black",
                "Red",
                "Blue",
                "Gold",
                "Green",
                "Orange",
                "Pink",
                "Titanium",
                "Dark Titanium"
            ]
            
            current_color = str(log.get("color") or "Clear").strip()
            
            if current_color in color_options:
                color_index = color_options.index(current_color)
            else:
                color_index = 0
            
            selected_color_name = st.selectbox(
                "เลือกสี",
                color_options,
                index=color_index,
                key=f"color_select_{id_val}"
            )
            
            # =====================================================
            # เลือกบ่อสี
            # =====================================================
            
            selected_tank_name = None
            
            if selected_color_name.strip().lower() != "clear":
            
                current_tank_name = str(
                    log.get("tank_name_snapshot") or ""
                ).strip()
            
                if current_tank_name in tank_names:
                    tank_index = tank_names.index(current_tank_name)
                else:
                    tank_index = 0
            
                selected_tank_name = st.selectbox(
                    "เลือกบ่อสี",
                    tank_names,
                    index=tank_index,
                    key=f"tank_select_{id_val}"
                )
            
            else:
            
                st.info("🪟 สี Clear ไม่ต้องเลือกบ่อสี")

            with st.form("edit_jiglog_form_v2"):

                st.markdown("### 🔄 เปลี่ยนชิ้นงานและแก้ไขจำนวน")

                old_p_code = log.get("products", {}).get("product_code", "N/A")
                old_p_name = log.get("products", {}).get("product_name", "N/A")

                st.text_input(
                    "ชิ้นงานเดิม",
                    value=f"{old_p_code} - {old_p_name}",
                    disabled=True
                )

                # =====================================================
                # เลือกสินค้า
                # =====================================================

                new_product_id = st.selectbox(
                    "เลือกชิ้นงานใหม่",
                    options=option_list,
                    index=current_index
                )

                selected_prod_id = prod_options[new_product_id]

                

                # =====================================================
                # จำนวน
                # =====================================================

                col1, col2, col3 = st.columns(3)

                pcs_per_row = col1.number_input(
                    "จำนวนต่อแถว",
                    min_value=0,
                    value=int(log.get("pcs_per_row") or 0)
                )

                rows_filled = col2.number_input(
                    "แถวที่เต็ม",
                    min_value=0,
                    value=int(log.get("rows_filled") or 0)
                )

                partial_pieces = col3.number_input(
                    "เศษ",
                    min_value=0,
                    value=int(log.get("partial_pieces") or 0)
                )

                total_pieces = (
                    (pcs_per_row * rows_filled)
                    + partial_pieces
                )

                st.info(f"🔢 จำนวนรวมใหม่: {total_pieces} ชิ้น")

                # =====================================================
                # BUTTONS
                # =====================================================

                col_save, col_delete = st.columns(2)

                with col_save:
                    save_btn = st.form_submit_button("💾 บันทึกการเปลี่ยนแปลง")

                with col_delete:
                    delete_btn = st.form_submit_button("🗑️ ลบบันทึกนี้")

                # =====================================================
                # SAVE
                # =====================================================

                if save_btn:
                    try:
                        # 1. ดึงข้อมูลสินค้า
                        product_info = (
                            supabase.table("products")
                            .select("*")
                            .eq("product_id", selected_prod_id)
                            .single()
                            .execute()
                            .data
                        )

                        # ดึงพื้นที่ผิวชิ้นงานเดี่ยว
                        surface_area_per_piece = float(product_info.get("unit_surface_area") or 0)

                        # คำนวณพื้นที่ผิวรวมของแถวนี้
                        log_total_surface_area = surface_area_per_piece * total_pieces

                        # 2. เตรียมข้อมูลอัปเดตตาราง jig_usage_log (เปลี่ยนคีย์เป็น total_surface_area แล้ว)
                        update_payload = {
                            "product_id": selected_prod_id,
                            "pcs_per_row": pcs_per_row,
                            "rows_filled": rows_filled,
                            "partial_pieces": partial_pieces,
                            "total_pieces": total_pieces,
                            "total_surface_area": log_total_surface_area, # 👈 เปลี่ยนจาก total_volume
                            "color": selected_color_name,
                            "tank_name_snapshot": selected_tank_name
                        }

                        update_row(
                            "jig_usage_log",
                            id_col,
                            id_val,
                            update_payload
                        )

                        # =====================================================
                        # รวม total surface area ของทั้งจิ๊ก
                        # =====================================================
                        jig_id = log.get("jig_id")

                        # ดึงข้อมูลมาบวกกัน (เปลี่ยนคำสั่ง select ให้ดึงคอลัมน์ใหม่ด้วย)
                        all_logs = (
                            supabase.table("jig_usage_log")
                            .select("total_surface_area") # 👈 เปลี่ยนดึงค่าจากคอลัมน์ใหม่
                            .eq("jig_id", jig_id)
                            .execute()
                            .data
                            or []
                        )

                        # รวมพื้นที่ผิวทั้งหมดบนโครงจิ๊กนี้
                        total_jig_surface_area = sum([
                            float(x.get("total_surface_area") or 0) # 👈 เปลี่ยนดึงค่าจากคอลัมน์ใหม่
                            for x in all_logs
                        ])

                        # อัปเดตยอดรวมพื้นที่ผิวลงตารางโครงจิ๊กหลัก (jigs) (เปลี่ยนคีย์เป็น total_surface_area)
                        update_row(
                            "jigs",
                            "jig_id",
                            jig_id,
                            {
                                "total_surface_area": total_jig_surface_area # 👈 เปลี่ยนจาก total_volume
                            }
                        )

                        st.success("อัปเดตข้อมูลเรียบร้อยแล้ว!")
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")
                # =====================================================
                # DELETE
                # =====================================================

                if delete_btn:

                    try:

                        delete_row(
                            "jig_usage_log",
                            id_col,
                            id_val
                        )

                        st.success("ลบบันทึกงานจิ๊กแล้ว")
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"ลบไม่สำเร็จ: {e}")

    with tab_color:
        st.subheader(f"🎨 บันทึกบ่อสีวันที่ {filter_date.strftime('%d/%m/%Y')}")
    
        start_dt = f"{filter_date_str}T00:00:00"
        end_dt = f"{filter_date_str}T23:59:59"
    
        color_logs = (
            supabase.table("color_tank_logs")
            .select("*")
            .gte("recorded_at", start_dt)
            .lte("recorded_at", end_dt)
            .order("recorded_at", desc=True)
            .execute()
            .data
            or []
        )
    
        if not color_logs:
            st.warning("📅 ไม่มีบันทึกบ่อสีในวันที่เลือก")
    
        else:
            df_color = pd.DataFrame(color_logs)
    
            df_color["recorded_at"] = pd.to_datetime(df_color["recorded_at"])\
                .dt.tz_convert(ICT)
    
            df_color["เวลา"] = df_color["recorded_at"].dt.strftime("%H:%M")
    
            # ===== เลือกบ่อ =====
            tank_list = sorted(df_color["tank_name_snapshot"].dropna().unique())
    
            selected_tank = st.selectbox(
                "เลือกบ่อสี",
                tank_list,
                key="color_tank_filter"
            )
    
            tank_df = df_color[
                df_color["tank_name_snapshot"] == selected_tank
            ].copy()
    
            show_df = tank_df[[
                "เวลา",
                "ph_value",
                "temperature"
            ]].rename(columns={
                "ph_value": "pH",
                "temperature": "Temp"
            })
    
            st.dataframe(
                show_df,
                use_container_width=True,
                hide_index=True
            )
    
            st.markdown("---")
            st.subheader("✏️ แก้ไขข้อมูล")
    
            for idx, row in tank_df.iterrows():
    
                with st.expander(f"⏰ {row['เวลา']}"):
    
                    with st.form(f"edit_color_{idx}"):
    
                        ph_value = st.number_input(
                            "pH",
                            value=float(row["ph_value"] or 0),
                            step=0.01,
                            format="%.2f"
                        )
    
                        temperature = st.number_input(
                            "Temperature",
                            value=float(row["temperature"] or 0),
                            step=0.1,
                            format="%.1f"
                        )
    
                        col1, col2 = st.columns(2)
    
                        if col1.form_submit_button("💾 บันทึก"):
    
                            update_row(
                                "color_tank_logs",
                                "id",
                                row["id"],
                                {
                                    "ph_value": ph_value,
                                    "temperature": temperature
                                }
                            )
    
                            st.success("บันทึกสำเร็จ")
                            time.sleep(1)
                            st.rerun()
    
                        if col2.form_submit_button("🗑️ ลบ"):
    
                            delete_row(
                                "color_tank_logs",
                                "id",
                                row["id"]
                            )
    
                            st.success("ลบสำเร็จ")
                            time.sleep(1)
                            st.rerun()

    with tab_chemical:
        st.subheader(f"🧪 บันทึกบ่อสารเคมีวันที่ {filter_date.strftime('%d/%m/%Y')}")
        start_dt = f"{filter_date_str}T00:00:00"
        end_dt = f"{filter_date_str}T23:59:59"
        chem_logs = supabase.table("anodize_tank_logs")\
            .select("*, tanks(tank_name)")\
            .gte("recorded_at", start_dt)\
            .lte("recorded_at", end_dt)\
            .order("recorded_at", desc=True)\
            .execute().data or []

        if not chem_logs:
            st.warning("📅 ไม่มีบันทึกบ่อสารเคมี")
        else:
            df_chem = pd.DataFrame(chem_logs)
            df_chem["recorded_at"] = pd.to_datetime(df_chem["recorded_at"])\
                .dt.tz_convert(ICT)
            df_chem["tank_name"] = df_chem["tanks"]\
                .apply(lambda x: x.get("tank_name") if isinstance(x, dict) else "-")
            df_chem["เวลา"] = df_chem["recorded_at"].dt.strftime("%H:%M")

            # ===== เลือกบ่อ =====
            chem_tanks = sorted(df_chem["tank_name"].dropna().unique())
            selected_chem = st.selectbox(
                "เลือกบ่อสารเคมี", chem_tanks, key="chem_tank_filter"
            )
            chem_df = df_chem[ df_chem["tank_name"] == selected_chem ].copy()
            is_sealer = ( "seal" in selected_chem.lower() or "sealer" in selected_chem.lower() )

            # ===== แสดงตารางข้อมูล =====
            # บ่อ Sealer: ให้แสดง เวลา, pH, Temp (ไม่ต้องแสดง Density)
            if is_sealer:
                show_df = chem_df[[ "เวลา", "ph_value", "temperature" ]].rename(columns={
                    "ph_value": "pH",
                    "temperature": "Temp"
                })
            else:
                show_df = chem_df[[ "เวลา", "ph_value", "temperature", "density" ]].rename(columns={
                    "ph_value": "pH",
                    "temperature": "Temp",
                    "density": "Density"
                })

            st.dataframe( show_df, use_container_width=True, hide_index=True )

            st.markdown("---")
            st.subheader("✏️ แก้ไขข้อมูลบ่อสารเคมี")

            # ===== ฟอร์มแก้ไขรายรายการ =====
            for idx, row in chem_df.iterrows():
                with st.expander(f"⏰ {row['เวลา']}"):
                    with st.form(f"edit_chem_{idx}"):
                        
                        # ทุกบ่อมีสิทธิ์แก้ไข Temp และ pH ได้เหมือนกัน
                        ph_value = st.number_input(
                            "pH", value=float(row["ph_value"] or 0), step=0.01, format="%.2f", key=f"ph_{idx}"
                        )
                        temperature = st.number_input(
                            "Temperature", value=float(row["temperature"] or 0), step=0.1, format="%.1f", key=f"temp_{idx}"
                        )

                        # บ่อสารเคมีอื่นๆ ที่ไม่ใช่บ่อ Seal ให้กรอก Density ได้
                        if not is_sealer:
                            density = st.number_input(
                                "Density", value=float(row["density"] or 0), step=0.001, format="%.3f", key=f"den_{idx}"
                            )
                        else:
                            density = 0.0

                        col1, col2 = st.columns(2)
                        
                        if col1.form_submit_button("💾 บันทึก"):
                            update_payload = {
                                "ph_value": ph_value,
                                "temperature": temperature,
                                "density": density
                            }
                            update_row("anodize_tank_logs", "log_id", row["log_id"], update_payload)
                            st.success("บันทึกสำเร็จ")
                            time.sleep(1)
                            st.rerun()

                        if col2.form_submit_button("🗑️ ลบ"):
                            delete_row("anodize_tank_logs", "id", row["id"])
                            st.success("ลบสำเร็จ")
                            time.sleep(1)
                            st.rerun()

#=================================================================   
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต", "🛠️ จัดการและแก้ไขข้อมูล"])

if menu == "Dashboard":
    st.title("📊 Production Dashboard")

    # --- 1. Global Filter (Sidebar) ---
    st.sidebar.subheader("📅 Filter Setting")
    time_unit = st.sidebar.selectbox(
        "มุมมองเวลา",
        ["รายวัน (เลือกหลายวัน)", "รายเดือน", "รายไตรมาส", "รายปี"]
    )
    
    # *** ประกาศค่าเริ่มต้นไว้ก่อน ***
    now_ict = datetime.now(ICT)
    g_start_dt = now_ict.replace(hour=0, minute=0, second=0, microsecond=0)
    g_end_dt = now_ict.replace(hour=23, minute=59, second=59, microsecond=999)

    if time_unit == "รายวัน (เลือกหลายวัน)":
        date_options = list(
            pd.date_range(
                now_ict.date() - timedelta(days=30),
                now_ict.date()
            ).date
        )
        date_options.reverse()
        
        selected_dates = st.sidebar.multiselect(
            "เลือกวันที่",
            options=date_options,
            default=[now_ict.date()]
        )
        
        selected_dates = [
            pd.to_datetime(d).date()
            for d in selected_dates
        ]
    elif time_unit == "รายเดือน":
        m_month = st.sidebar.selectbox("เดือน", list(range(1, 13)), index=now_ict.month-1)
        m_year = st.sidebar.number_input("ปี (ค.ศ.)", value=now_ict.year, key="m_year")
        g_start_dt = datetime(m_year, m_month, 1).replace(tzinfo=ICT)
        next_m = m_month + 1 if m_month < 12 else 1
        next_y = m_year if m_month < 12 else m_year + 1
        g_end_dt = datetime(next_y, next_m, 1).replace(tzinfo=ICT) - timedelta(seconds=1)
    elif time_unit == "รายไตรมาส":
        q_year = st.sidebar.number_input("ปี (ค.ศ.)", value=now_ict.year, key="q_year")
        q_val = st.sidebar.selectbox("ไตรมาส", [1, 2, 3, 4])
        try:
            s_date, e_date = get_quarter_range(q_year, q_val)
            g_start_dt, g_end_dt = s_date.replace(tzinfo=ICT), e_date.replace(tzinfo=ICT)
        except: pass
    elif time_unit == "รายปี":
        y_year = st.sidebar.number_input("เลือกปี (ค.ศ.)", value=now_ict.year, key="y_year")
        g_start_dt = datetime(y_year, 1, 1).replace(tzinfo=ICT)
        g_end_dt = datetime(y_year, 12, 31, 23, 59, 59).replace(tzinfo=ICT)

    # --- Standard Values ---
    STD = {
        "COLOR_PH": [5.0, 6.0], "COLOR_TEMP": [30, 40],
        "ANO_PH": [1.0, 1.5], "ANO_TEMP": [18, 22], "ANO_DEN": [0.5, 1.5],
        "SEAL_PH": [5.5, 6.5], "SEAL_TEMP": [80, 98]
    }

    # --- Data Loading ---
    @st.cache_data(ttl=10)
    def load_dashboard_data():
        try:
            c_res = supabase.table("color_tank_logs") \
                .select("*") \
                .order("recorded_at", desc=True) \
                .limit(300) \
                .execute()
            c_logs = c_res.data if c_res.data else []
        except Exception as e:
            st.warning(f"โหลด Color Tank Logs ไม่สำเร็จ: {e}")
            c_logs = []

        try:
            a_res = supabase.table("anodize_tank_logs") \
                .select("*") \
                .order("recorded_at", desc=True) \
                .limit(300) \
                .execute()
            a_logs = a_res.data if a_res.data else []
        except Exception as e:
            st.warning(f"โหลด Anodize Logs ไม่สำเร็จ: {e}")
            a_logs = []

        try:
            tanks = get_options("tanks", "tank_id", "tank_name")
        except Exception as e:
            st.warning(f"โหลด Tanks ไม่สำเร็จ: {e}")
            tanks = {}

        return c_logs, a_logs, tanks

    c_logs, a_logs, tank_map = load_dashboard_data()
    inv_tank_map = {v: k for k, v in tank_map.items()}

    # --- Helper: Alert Table (Compact) ---
    def show_alert_table_mini(df, p_min, p_max, t_min, t_max):
        alerts = []
        for _, row in df.iterrows():
            ph_alert = ""
            temp_alert = ""

            if "ph_value" in row and pd.notnull(row["ph_value"]):
                ph_val = float(row["ph_value"])
                if ph_val < p_min or ph_val > p_max:
                    ph_alert = f"🔴 {ph_val:.2f}"
                elif ph_val <= p_min + 0.2 or ph_val >= p_max - 0.2:
                    ph_alert = f"⚠️ {ph_val:.2f}"

            if "temperature" in row and pd.notnull(row["temperature"]):
                temp_val = float(row["temperature"])
                if temp_val < t_min or temp_val > t_max:
                    temp_alert = f"🔴 {temp_val:.1f}"
                elif temp_val <= t_min + 2 or temp_val >= t_max - 2:
                    temp_alert = f"⚠️ {temp_val:.1f}"

            if ph_alert or temp_alert:
                alerts.append({
                    "บ่อ": row["tank_name"],
                    "pH": ph_alert,
                    "อุณหภูมิ": temp_alert,
                    "เวลา": row["recorded_at"].strftime('%d/%m %H:%M')
                })

        if alerts:
            alert_df = pd.DataFrame(alerts)
            st.dataframe(alert_df, hide_index=True, use_container_width=True, height=220)
        else:
            st.caption("✅ ทุกค่าอยู่ในเกณฑ์ปกติ")


    # --- เตรียมข้อมูลตาม Filter หลักของระบบ ---
    df_c_filtered = pd.DataFrame(c_logs) if c_logs else pd.DataFrame()
    df_a_filtered = pd.DataFrame(a_logs) if a_logs else pd.DataFrame()
    
    if not df_c_filtered.empty:
        df_c_filtered["recorded_at"] = pd.to_datetime(df_c_filtered["recorded_at"]).dt.tz_convert(ICT)
        df_c_filtered["tank_name"] = df_c_filtered["tank_name_snapshot"]
        if time_unit == "รายวัน (เลือกหลายวัน)":
            df_c_filtered = df_c_filtered[df_c_filtered["recorded_at"].dt.date.isin(selected_dates)]
        else:
            df_c_filtered = df_c_filtered[(df_c_filtered["recorded_at"] >= g_start_dt) & (df_c_filtered["recorded_at"] <= g_end_dt)]
            
    if not df_a_filtered.empty:
        df_a_filtered["recorded_at"] = pd.to_datetime(df_a_filtered["recorded_at"]).dt.tz_convert(ICT)
        df_a_filtered["tank_name"] = df_a_filtered["tank_id"].map(inv_tank_map)
        if time_unit == "รายวัน (เลือกหลายวัน)":
            df_a_filtered = df_a_filtered[df_a_filtered["recorded_at"].dt.date.isin(selected_dates)]
        else:
            df_a_filtered = df_a_filtered[(df_a_filtered["recorded_at"] >= g_start_dt) & (df_a_filtered["recorded_at"] <= g_end_dt)]


    # --- 1. Color Tanks (กราฟแสดงข้อมูลบ่อสี) ---
    st.subheader("🎨 กราฟเเท่งเเสดงค่าอุณหภูมิเเละ pH ของบ่อสีล่าสุด")
    col1, col2 = st.columns([1, 2.5])
    
    if not df_c_filtered.empty:
        latest_c = df_c_filtered.drop_duplicates("tank_id").sort_values("tank_name")
        
        with col1:
            st.caption("🚨 Alerts (ค่าที่หลุดเกณฑ์เป็นสีแดง)")
            show_alert_table_mini(latest_c, *STD["COLOR_PH"], *STD["COLOR_TEMP"])
            
        with col2:
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            
            ph_colors = ["#DC2626" if (val < STD["COLOR_PH"][0] or val > STD["COLOR_PH"][1]) else "#2ECC71" for val in latest_c["ph_value"]]
            temp_colors = ["#DC2626" if (val < STD["COLOR_TEMP"][0] or val > STD["COLOR_TEMP"][1]) else "#3498DB" for val in latest_c["temperature"]]

            fig1.add_trace(go.Bar(x=latest_c["tank_name"], y=latest_c["ph_value"], name="pH", marker_color=ph_colors, offsetgroup=1, text=latest_c["ph_value"], textposition='outside', textfont_size=9), secondary_y=False)
            fig1.add_trace(go.Bar(x=latest_c["tank_name"], y=latest_c["temperature"], name="T", marker_color=temp_colors, offsetgroup=2, text=latest_c["temperature"], textposition='outside', textfont_size=9), secondary_y=True)
            fig1.update_layout(height=250, margin=dict(l=5,r=5,t=20,b=5), barmode="group", showlegend=False, yaxis_showgrid=False, yaxis2_showgrid=False)
            st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("📅 ไม่มีข้อมูลบันทึกบ่อสีในช่วงวันที่เลือก")


    # --- 2. Anodize/Seal (ตารางแสดงประวัติบ่อเคมีตามวันที่เลือก + สกรอล์เมาส์ได้) ---
    st.markdown("---")
    st.subheader("📈 เเนวโน้มบ่อ Anodize เเละ บ่อ Seal")
    
    if not df_a_filtered.empty:
        c_sel1, c_sel2 = st.columns([1.4, 2.6])
        with c_sel1:
            sel_ano = st.selectbox("เลือกบ่อ", sorted(df_a_filtered["tank_name"].dropna().unique()), key="sb_ano")
            
            history_a_selected = df_a_filtered[df_a_filtered["tank_name"] == sel_ano].sort_values("recorded_at", ascending=False)
            
            st.markdown(f"**🧪 ประวัติบันทึกตามวันที่เลือก: {sel_ano}**")
            if not history_a_selected.empty:
                chem_rows = []
                for _, row in history_a_selected.iterrows():
                    t_name = str(row["tank_name"])
                    v_ph = float(row["ph_value"] or 0)
                    v_tmp = float(row["temperature"] or 0)
                    v_den = float(row["density"] or 0)
                    is_seal_t = "seal" in t_name.lower()
                    
                    if is_seal_t:
                        style_p = "color:#DC2626; font-weight:bold;" if (v_ph < STD["SEAL_PH"][0] or v_ph > STD["SEAL_PH"][1]) else ""
                        style_t = "color:#DC2626; font-weight:bold;" if (v_tmp < STD["SEAL_TEMP"][0] or v_tmp > STD["SEAL_TEMP"][1]) else ""
                        txt_p = f"<span style='{style_p}'>{v_ph:.2f}</span>" if style_p else f"{v_ph:.2f}"
                        txt_t = f"<span style='{style_t}'>{v_tmp:.1f}</span>" if style_t else f"{v_tmp:.1f}"
                        txt_d = "<span style='color:#94A3B8;'>-</span>"
                    else:
                        style_p = "color:#DC2626; font-weight:bold;" if (v_ph < STD["ANO_PH"][0] or v_ph > STD["ANO_PH"][1]) else ""
                        style_t = "color:#DC2626; font-weight:bold;" if (v_tmp < STD["ANO_TEMP"][0] or v_tmp > STD["ANO_TEMP"][1]) else ""
                        style_d = "color:#DC2626; font-weight:bold;" if (v_den < STD["ANO_DEN"][0] or v_den > STD["ANO_DEN"][1]) else ""
                        txt_p = f"<span style='{style_p}'>{v_ph:.2f}</span>" if style_p else f"{v_ph:.2f}"
                        txt_t = f"<span style='{style_t}'>{v_tmp:.1f}</span>" if style_t else f"{v_tmp:.1f}"
                        txt_d = f"<span style='{style_d}'>{v_den:.3f}</span>" if style_d else f"{v_den:.3f}"
                    
                    chem_rows.append({
                        "เวลาบันทึก": row["recorded_at"].strftime("%d/%m %H:%M"),
                        "pH": txt_p,
                        "Temp": txt_t,
                        "Density": txt_d
                    })
                
                # 🌟 แปลงตารางเป็น HTML และหุ้มด้วย div เพื่อให้สามารถเลื่อน Scroll เมาส์ได้ (ความสูงสูงสุด 260px) พร้อมคงหัวตารางตรึงไว้
                html_table_a = pd.DataFrame(chem_rows).to_html(escape=False, index=False)
                scrollable_table_a = f"""
                <div style="max-height: 260px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 4px;">
                    <style>
                        thead th {{ position: sticky; top: 0; background-color: #F8FAFC; z-index: 1; }}
                    </style>
                    {html_table_a}
                </div>
                """
                st.write(scrollable_table_a, unsafe_allow_html=True)
            else:
                st.caption("📅 ไม่มีข้อมูลประวัติในช่วงวันที่เลือก")
        
        with c_sel2:
            chart_df = df_a_filtered[df_a_filtered["tank_name"] == sel_ano].sort_values("recorded_at")
            if not chart_df.empty:
                is_seal = "seal" in sel_ano.lower()
                if is_seal:
                    tc1, tc2 = st.columns(2)
                    
                    fig_s_ph = go.Figure([go.Scatter(x=chart_df["recorded_at"], y=chart_df["ph_value"], mode='lines+markers', line_color="#8E44AD", marker_size=4)])
                    fig_s_ph.add_hrect(y0=STD["SEAL_PH"][0], y1=STD["SEAL_PH"][1], fillcolor="green", opacity=0.1, line_width=0)
                    fig_s_ph.update_layout(title=dict(text="ค่า pH บ่อซีล", font_size=11), height=160, margin=dict(l=5,r=5,t=30,b=5), yaxis_showgrid=False)
                    tc1.plotly_chart(fig_s_ph, use_container_width=True)
                    
                    fig_s_temp = go.Figure([go.Scatter(x=chart_df["recorded_at"], y=chart_df["temperature"], mode='lines+markers', line_color="#E74C3C", marker_size=4)])
                    fig_s_temp.add_hrect(y0=STD["SEAL_TEMP"][0], y1=STD["SEAL_TEMP"][1], fillcolor="green", opacity=0.1, line_width=0)
                    fig_s_temp.update_layout(title=dict(text="อุณหภูมิ (°C)", font_size=11), height=160, margin=dict(l=5,r=5,t=30,b=5), yaxis_showgrid=False)
                    tc2.plotly_chart(fig_s_temp, use_container_width=True)
                else:
                    tc1, tc2, tc3 = st.columns(3)
                    def plot_mini(title, col, std, color):
                        fig = go.Figure([go.Scatter(x=chart_df["recorded_at"], y=chart_df[col], mode='lines+markers', line_color=color, marker_size=4)])
                        fig.add_hrect(y0=std[0], y1=std[1], fillcolor="green", opacity=0.1, line_width=0)
                        fig.update_layout(title=dict(text=title, font_size=11), height=150, margin=dict(l=5,r=5,t=30,b=5), yaxis_showgrid=False, xaxis_showticklabels=False)
                        return fig
                    tc1.plotly_chart(plot_mini("pH", "ph_value", STD["ANO_PH"], "#8E44AD"), use_container_width=True)
                    tc2.plotly_chart(plot_mini("Temp", "temperature", STD["ANO_TEMP"], "#D35400"), use_container_width=True)
                    tc3.plotly_chart(plot_mini("Density", "density", STD["ANO_DEN"], "#2C3E50"), use_container_width=True)
            else:
                st.info("📅 ไม่มีข้อมูลบันทึกของบ่อนี้ในช่วงเวลาที่เลือก")
    else:
        st.info("📅 ไม่มีข้อมูลบ่อสารเคมีในช่วงวันที่เลือก")


    # --- 3. Compare ---
    st.markdown("---")
    st.subheader("🔍 กราฟเส้นเเนวโน้มค่า pH เเละอุณหภูมิบ่อสีรายบ่อ")
    if not df_c_filtered.empty:
        c_m1, c_m2 = st.columns([1, 3])
        with c_m1:
            sel_tanks = st.multiselect("เลือกบ่อสี", sorted(df_c_filtered["tank_name"].unique()), default=sorted(df_c_filtered["tank_name"].unique())[:1])
        with c_m2:
            if sel_tanks:
                fig_mix = make_subplots(specs=[[{"secondary_y": True}]])
                fig_mix.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=5, y1=6, fillcolor="#22C55E", opacity=0.05, layer="below", line_width=0)
                fig_mix.add_shape(type="rect", xref="paper", yref="y2", x0=0, x1=1, y0=30, y1=40, fillcolor="#F59E0B", opacity=0.04, layer="below", line_width=0)
                
                for t_name in sel_tanks:
                    t_data = df_c_filtered[df_c_filtered["tank_name"] == t_name].sort_values("recorded_at")
                    color_name = tank_color_map.get(t_name, "")
                    clr = get_hex_from_name(color_name)
                    temp_clr = lighten_color(clr)
                
                    fig_mix.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["ph_value"], name=f"{t_name} pH", mode="lines+markers", line=dict(color=clr, width=3), marker=dict(size=7, symbol="circle", color=clr)), secondary_y=False)
                    fig_mix.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["temperature"], name=f"{t_name} Temp", legendgroup=t_name, mode="lines+markers", line=dict(color=temp_clr, width=2, dash="dot"), marker=dict(size=6, line=dict(width=1, color="white"), symbol="square", color=temp_clr)), secondary_y=True)
                
                fig_mix.update_layout(height=420, margin=dict(l=5, r=5, t=10, b=5), legend=dict(font_size=9), yaxis_showgrid=False, yaxis2_showgrid=False, plot_bgcolor="#F8FAFC", paper_bgcolor="#F8FAFC")
                fig_mix.update_yaxes(title_text="pH", secondary_y=False)
                fig_mix.update_yaxes(title_text="Temperature (°C)", secondary_y=True)
                fig_mix.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.15)", secondary_y=False)
                fig_mix.update_yaxes(showgrid=False, secondary_y=True)
                st.plotly_chart(fig_mix, use_container_width=True)


    # --- 4. ตารางประวัติบันทึกข้อมูลของบ่อสีตามช่วงเวลาที่เลือก (อยู่ล่างสุด + สกรอล์เมาส์ได้) ---
    st.markdown("---")
    st.markdown("### 📋 ตารางประวัติบันทึกข้อมูลของบ่อสีตามช่วงเวลาที่เลือก")
    
    if not df_c_filtered.empty:
        all_c_records = df_c_filtered.sort_values("recorded_at", ascending=False)
        
        color_rows = []
        for _, row in all_c_records.iterrows():
            v_ph = float(row["ph_value"] or 0)
            v_tmp = float(row["temperature"] or 0)
            
            style_p = "color:#DC2626; font-weight:bold;" if (v_ph < STD["COLOR_PH"][0] or v_ph > STD["COLOR_PH"][1]) else ""
            style_t = "color:#DC2626; font-weight:bold;" if (v_tmp < STD["COLOR_TEMP"][0] or v_tmp > STD["COLOR_TEMP"][1]) else ""
            
            color_rows.append({
                "วันที่/เวลา บันทึก": row["recorded_at"].strftime("%d/%m/%Y %H:%M:%S"),
                "ชื่อบ่อสี": row["tank_name"],
                "ค่า pH": f"<span style='{style_p}'>{v_ph:.2f}</span>" if style_p else f"{v_ph:.2f}",
                "อุณหภูมิ (°C)": f"<span style='{style_t}'>{v_tmp:.1f}</span>" if style_t else f"{v_tmp:.1f}"
            })
            
        # 🌟 แปลงตารางเป็น HTML และหุ้มด้วย div เพื่อให้สามารถเลื่อน Scroll เมาส์ได้ (ความสูงสูงสุด 350px) พร้อมคงหัวตารางตรึงไว้
        html_table_c = pd.DataFrame(color_rows).to_html(escape=False, index=False)
        scrollable_table_c = f"""
        <div style="max-height: 350px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 4px;">
            <style>
                thead th {{ position: sticky; top: 0; background-color: #F8FAFC; z-index: 1; }}
            </style>
            {html_table_c}
        </div>
        """
        st.write(scrollable_table_c, unsafe_allow_html=True)
    else:
        st.caption("📅 ไม่มีข้อมูลบันทึกบ่อสีในวันที่และเวลาที่กำหนด")
# ================= RECORD PAGE =================
if menu == "บันทึกข้อมูลการผลิต":
    st.title("📝 ระบบบันทึกข้อมูล (Interactive Map)")

    if "tank_read_round" not in st.session_state:
        st.session_state["tank_read_round"] = 0
    
    if "open_tank_dialog" not in st.session_state:
        st.session_state["open_tank_dialog"] = False
    
    if st.button("โหลดบ่อที่คลิก", key="load_clicked_tank_btn"):
        st.session_state["tank_read_round"] += 1
        st.session_state["open_tank_dialog"] = True
    
    clicked_tank_payload = streamlit_js_eval(
        js_expressions="localStorage.getItem('selected_tank_payload')",
        key=f"selected_tank_payload_reader_{st.session_state['tank_read_round']}",
        want_output=True
    )
    
    if clicked_tank_payload:
        try:
            payload = json.loads(clicked_tank_payload)
    
            if payload.get("tank"):
    
                st.session_state["clicked_tank_name"] = payload["tank"]
    
                # ===== ล้างค่าเก่าทันที =====
                streamlit_js_eval(
                    js_expressions="""
                    localStorage.removeItem('selected_tank_payload')
                    """,
                    key=f"clear_payload_{time.time()}",
                    want_output=False
                )
    
        except Exception as e:
            st.warning(e)
    
    clicked_tank_name = st.session_state.get("clicked_tank_name")
    

    color_tanks = get_options(
        "tanks",
        "tank_id",
        "tank_name",
        "tank_type",
        "Color"
    )
    all_tanks = get_options("tanks", "tank_id", "tank_name")
    
    chemical_tanks = {
        name: tid for name, tid in all_tanks.items()
        if any(keyword in name.lower() for keyword in ["anodize", "almite", "sealer", "seal"])
    }
    
    render_tank_map(clicked_tank_name)
    
    if clicked_tank_name:
        st.success(f"เลือกบ่อจากผัง: {clicked_tank_name}")
    
    if st.session_state.get("open_tank_dialog") and clicked_tank_name:
        tank_record_dialog(clicked_tank_name, color_tanks, chemical_tanks)

#====================================================================================
    tab_main = st.tabs(["งานจิ๊ก (Jig System)"])

    with tab_main[0]:
        sub_prod, sub_jig, sub_log, sub_update, sub_finish = st.tabs([
            "📦 1. ลงทะเบียนสินค้า",
            "🛠️ 2. ลงทะเบียนจิ๊ก",
            "⚡ 3. บันทึกผลผลิต",
            "🎨 4. อัปเดตลงบ่อสี",
            "🏁 5. เสร็จสิ้นงาน"
        ])

        with sub_prod:
            st.subheader("เพิ่มสินค้าใหม่ลงระบบ")
            shape = st.selectbox("📐 เลือกรูปทรง", ["สี่เหลี่ยม", "ทรงกระบอกทึบ", "ทรงกระบอกกลวง"], key="shape_sel")
            with st.form("add_prod_form_fixed", clear_on_submit=True):
                c1, c2 = st.columns(2)
                p_code = c1.text_input("รหัสสินค้า *")
                p_name = c1.text_input("ชื่อสินค้า")
                s_finish = c1.text_input("พื้นผิว *", value="-")
                height = c2.number_input("ความยาว/ความสูง (H) [mm]", min_value=0.0)
                
                # เปลี่ยนชื่อตัวแปรจาก u_vol เป็น u_surf เพื่อความเข้าใจที่ถูกต้อง (Unit Surface Area)
                width, thickness, od, u_surf, id_inner = 0.0, 0.0, 0.0, 0.0, 0.0
                
                # =====================================================
                # 1. คำนวณพื้นที่ผิวตามรูปทรง (มิติระนาบ 2 มิติ mm²)
                # =====================================================
                if shape == "สี่เหลี่ยม":
                    width = c2.number_input("กว้าง [mm]", min_value=0.0)
                    thickness = c2.number_input("สูง/หนา [mm]", min_value=0.0)
                    # สูตรพื้นที่ผิวสี่เหลี่ยมกล่อง: 2 * ((กว้าง*ยาว) + (กว้าง*หนา) + (ยาว*หนา))
                    u_surf = 2 * ((width * height) + (width * thickness) + (height * thickness))
                    
                elif shape == "ทรงกระบอกทึบ":
                    od = c2.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0)
                    r_outer = od / 2
                    # สูตรพื้นที่ผิวทรงกระบอกทึบ: พื้นที่ผิวข้าง + พื้นที่หน้าตัดฝาบนล่าง 2 ฝั่ง
                    u_surf = (2 * math.pi * r_outer * height) + (2 * math.pi * (r_outer ** 2))
                    
                else: # ทรงกระบอกกลวง
                    od = c2.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0)
                    thickness = c2.number_input("ความหนาของเนื้อชิ้นงาน [mm]", min_value=0.0)
                    id_inner = max(0.0, od - (2 * thickness))
                    r_outer = od / 2
                    r_inner = id_inner / 2
                    
                    # สูตรพื้นที่ผิวทรงกระบอกกลวง: ผิวข้างนอก + ผิวข้างใน + พื้นที่หน้าตัดวงแหวนหัวท้าย 2 ฝั่ง
                    side_outer = 2 * math.pi * r_outer * height
                    side_inner = 2 * math.pi * r_inner * height
                    base_rings = 2 * math.pi * ((r_outer ** 2) - (r_inner ** 2))
                    u_surf = side_outer + side_inner + base_rings

                # เปลี่ยนข้อความแสดงผลให้แสดงหน่วยพื้นที่ผิว (mm²)
                st.info(f"💡 พื้นที่ผิวรวม: {u_surf:,.2f} mm²")
                
                if st.form_submit_button("➕ ลงทะเบียนสินค้า"):
                    if p_code:
                        check_exist = supabase.table("products").select("product_code").eq("product_code", p_code).execute()
                        if check_exist.data:
                            st.error(f"❌ รหัสสินค้า '{p_code}' นี้มีอยู่ในระบบแล้ว")
                        else:
                            # =====================================================
                            # 2. จัดเตรียมและนำส่ง Payload ข้อมูลเข้าฐานข้อมูล
                            # =====================================================
                            payload = {
                                "product_code": p_code,
                                "product_name": p_name,
                                "height": height,
                                "width": width,
                                "thickness": thickness,
                                "depth": 0,
                                "outer_diameter": od,
                                "inner_diameter": id_inner,
                                "surface_finish": s_finish,
                                "unit_surface_area": float(u_surf),  # 👈 นำค่าพื้นที่ผิวจริงที่คำนวณได้ใส่ลงฟิลด์นี้
                                "shape": shape
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
            try:
                prods_res = supabase.table("products") \
                    .select("product_id, product_code, product_name") \
                    .execute().data or []
            
            except Exception as e:
                st.error(f"โหลด products ไม่สำเร็จ: {e}")
                prods_res = []
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
                        # =====================================================
                        # FILTER รูปแบบสินค้า
                        # =====================================================
                        
                        shape_filter = st.selectbox(
                            "กรองรูปแบบสินค้า",
                            [
                                "ทั้งหมด",
                                "สี่เหลี่ยม",
                                "ทรงกระบอกทึบ",
                                "ทรงกระบอกกลวง"
                            ],
                            key="shape_filter_jig"
                        )
                        
                        # ===== โหลด products ทั้งหมด =====
                        all_products = supabase.table("products").select(
                            "product_id, product_code, product_name, shape"
                        ).execute().data or []
                        
                        # ===== filter ตาม shape =====
                        if shape_filter != "ทั้งหมด":
                        
                            filtered_products = [
                                p for p in all_products
                                if p.get("shape") == shape_filter
                            ]
                        
                        else:
                        
                            filtered_products = all_products
                        
                        # ===== display options =====
                        display_options = {
                            f"{p['product_code']} | {p['product_name']}": p["product_id"]
                            for p in filtered_products
                        }
                        
                        # ===== ถ้าไม่มีสินค้า =====
                        if not display_options:
                        
                            st.warning("❌ ไม่มีสินค้าในรูปแบบนี้")
                        
                        # ===== ถ้ามีสินค้า =====
                        else:
                        
                            selected_display = st.selectbox(
                                "เลือกสินค้า (รหัส | ชื่อ)",
                                options=list(display_options.keys()),
                                key="sel_p_log"
                            )
                        
                            selected_prod_id = display_options[selected_display]
                            p_info = supabase.table("products").select("*").eq("product_id", selected_prod_id).single().execute().data
                            action = st.radio("การทำงาน", ["🔵 บันทึกงานต่อ"], key="action_radio")

                            if action == "🔵 บันทึกงานต่อ":
    
                                # ===== เพิ่มตัวเลือกยังไม่ลงบ่อ =====
                                color_choices = ["⏳ ยังไม่ลงบ่อสี", "✨ สีใส (Clear)"] + sorted(
                                    set(tank_color_map.values())
                                )
                            
                                sel_c_new = st.selectbox(
                                    "เลือกสี",
                                    color_choices,
                                    key="sel_c_log"
                                )
                            
                                selected_tank_id = None
                                selected_tank_name = None
                                status_value = "pending"
                            
                                # =========================================================
                                # กรณียังไม่ลงบ่อ
                                # =========================================================
                                if sel_c_new == "⏳ ยังไม่ลงบ่อสี":
                                
                                    st.info("📌 งานนี้จะถูกบันทึกเป็น 'รอชุบ'")
                                
                                # =========================================================
                                # สีใส
                                # =========================================================
                                elif sel_c_new == "✨ สีใส (Clear)":
                                
                                    selected_tank_id = None
                                    selected_tank_name = "Clear"
                                    status_value = "processing"
                                
                                    st.success("✨ งานนี้จะถูกบันทึกเป็น สีใส (Clear)")
                            
                                # =========================================================
                                # กรณีเลือกสีจริง
                                # =========================================================
                                else:
                            
                                    filtered_tanks = {
                                        n: i
                                        for n, i in color_tanks_all.items()
                                        if tank_color_map.get(n) == sel_c_new
                                    }
                            
                                    if filtered_tanks:
                            
                                        sel_tank_name = st.selectbox(
                                            "เลือกบ่อสี",
                                            list(filtered_tanks.keys()),
                                            key="sel_t_log"
                                        )
                            
                                        selected_tank_id = filtered_tanks[sel_tank_name]
                                        selected_tank_name = sel_tank_name
                                        status_value = "processing"
                            
                                        render_color_bar(sel_tank_name)
                            
                                # =========================================================
                                # FORM
                                # =========================================================
                                with st.form("continue_form_fixed", clear_on_submit=True):
                            
                                    c1, c2 = st.columns(2)
                            
                                    pcs = c1.number_input(
                                        "จำนวนต่อแถว",
                                        min_value=0,
                                        max_value=1000,
                                        value=0
                                    )
                            
                                    rows = c1.number_input(
                                        "แถวที่เต็ม",
                                        min_value=0,
                                        max_value=100,
                                        value=0
                                    )
                            
                                    partial = c1.number_input(
                                        "เศษ",
                                        min_value=0,
                                        max_value=1000,
                                        value=0
                                    )
                            
                                    # ===== คำนวณ =====
                                    total_pcs = (rows * pcs) + partial
                            
                                    unit_vol = p_info.get("unit_volume", 0) if p_info else 0
                            
                                    total_vol = unit_vol * total_pcs
                            
                                    # ===== แสดงผล =====
                                    c2.metric(
                                        "จำนวนรวม (Pcs)",
                                        total_pcs
                                    )
                            
                                    c2.metric(
                                        "ปริมาตรรวม (mm³)",
                                        f"{total_vol:,.2f}"
                                    )
                            
                                    # =====================================================
                                    # SAVE
                                    # =====================================================
                                    if st.form_submit_button("💾 บันทึก"):
                            
                                        try:
                            
                                            supabase.table("jig_usage_log").insert({
                                                "product_id": selected_prod_id,
                                                "jig_id": jig_id,
                                                "color": (
                                                    None
                                                    if sel_c_new == "⏳ ยังไม่ลงบ่อสี"
                                                    else (
                                                        "clear"
                                                        if sel_c_new == "✨ สีใส (Clear)"
                                                        else sel_c_new
                                                    )
                                                ),
                                                "tank_id": selected_tank_id,
                                                "tank_name_snapshot": selected_tank_name,
                                                "status": status_value,
                                                "total_pieces": total_pcs,
                                                "total_volume": total_vol,
                                                "recorded_date": datetime.now(ICT).isoformat(),
                                                "rows_filled": rows,
                                                "partial_pieces": partial,
                                                "pcs_per_row": pcs
                                            }).execute()
                                            
                                            # ===== อัปเดต jig_status =====
                                            supabase.table("jig_status").upsert({
                                                "jig_id": int(jig_id),
                                                "status_type": (
                                                    "Waiting"
                                                    if status_value == "pending"
                                                    else "In-Process"
                                                ),
                                                "current_tank_id": (
                                                    int(selected_tank_id)
                                                    if selected_tank_id is not None
                                                    else None
                                                ),
                                                "updated_at": datetime.now(ICT).isoformat()
                                            }).execute()
                                            
                                            # 🛠️ จุดแก้ไขที่ 1: คำนวณหาผลรวมยอดสะสมทั้งหมดของโครงจิ๊กนี้ในปัจจุบัน
                                            all_active_logs = supabase.table("jig_usage_log").select("total_pieces, total_volume").eq("jig_id", jig_id).neq("status", "finished").execute().data or []
                                            sum_pcs = sum([int(x.get("total_pieces") or 0) for x in all_active_logs])
                                            sum_vol = sum([float(x.get("total_volume") or 0) for x in all_active_logs])

                                            # ===== อัปเดตข้อมูลรวมเข้าตาราง jigs หลัก =====
                                            supabase.table("jigs").update({
                                                "total_pcs_in_jig": sum_pcs,
                                                "total_volume": sum_vol
                                            }).eq("jig_id", jig_id).execute()
                                            
                                            st.success("✅ บันทึกสำเร็จ")
                                            time.sleep(1)
                                            st.rerun()
                                            
                                        except Exception as e:
                                            st.error(f"เกิดข้อผิดพลาดในการบันทึก: {str(e)}")

        # =========================================================
        # 🎨 TAB อัปเดตลงบ่อสี
        # =========================================================
        with sub_update:
        
            st.subheader("🎨 อัปเดตลงบ่อสี")
        
            try:
                pending_res = (
                    supabase.table("jig_usage_log")
                    .select("*")
                    .is_("tank_id", "null")
                    .neq("status", "finished")
                    .order("recorded_date", desc=True)
                    .execute()
                )
                pending_logs = pending_res.data or []
            except Exception as e:
                st.error(f"โหลดงานรอชุบไม่สำเร็จ: {e}")
                pending_logs = []
        
            if not pending_logs:
                st.success("✅ ไม่มีงานรออัปเดตบ่อสี")
            else:
                pending_df = pd.DataFrame(pending_logs)
                products = load_products()
        
                product_map = {
                    p["product_id"]: f"{p['product_code']} | {p['product_name']}"
                    for p in products
                }
        
                jig_rows = (
                    supabase.table("jigs")
                    .select("jig_id, jig_model_code")
                    .execute()
                    .data
                    or []
                )
        
                jig_map = {
                    j["jig_id"]: j["jig_model_code"]
                    for j in jig_rows
                }
        
                pending_df["display"] = pending_df.apply(
                    lambda row: (
                        f"{product_map.get(row['product_id'], 'Unknown')} "
                        f"| Jig: {jig_map.get(row['jig_id'], '-')}"
                        f"| Qty: {row.get('total_pieces',0)}"
                    ),
                    axis=1
                )
        
                selected_log_id = int(st.selectbox(
                    "เลือกงานที่ต้องการลงบ่อ",
                    options=[int(x) for x in pending_df["log_id"].tolist()],
                    format_func=lambda x: pending_df[pending_df["log_id"] == x]["display"].iloc[0]
                ))
        
                color_tanks = get_options("tanks", "tank_id", "tank_name", "tank_type", "Color")
                selected_tank = st.selectbox("เลือกบ่อสี", sorted(color_tanks.keys()), key="update_tank_name")
        
                render_color_bar(selected_tank)
        
                if st.button("💾 อัปเดตลงบ่อสี", use_container_width=True):
                    try:
                        selected_row = pending_df[pending_df["log_id"] == selected_log_id].iloc[0]
                        selected_tank_id = int(color_tanks[selected_tank])
                        real_color = str(tank_color_map.get(selected_tank, ""))
                        current_jig_id = int(selected_row["jig_id"])
        
                        # ===== update jig_usage_log =====
                        supabase.table("jig_usage_log").update({
                            "tank_id": selected_tank_id,
                            "tank_name_snapshot": str(selected_tank),
                            "color": real_color,
                            "status": "processing",
                            "started_dip_at": datetime.now(ICT).isoformat()
                        }).eq("log_id", int(selected_log_id)).execute()
                
                        # ===== update jig_status =====
                        supabase.table("jig_status").upsert({
                            "jig_id": current_jig_id,
                            "status_type": "In-Process",
                            "current_tank_id": selected_tank_id,
                            "updated_at": datetime.now(ICT).isoformat()
                        }).execute()

                        # 🛠️ จุดแก้ไขที่ 2: อัปเดตบ่อสีสะท้อนกลับไปที่ตารางโครงจิ๊กหลัก (jigs) ด้วย
                        all_active_logs = supabase.table("jig_usage_log").select("total_pieces, total_volume").eq("jig_id", current_jig_id).neq("status", "finished").execute().data or []
                        sum_pcs = sum([int(x.get("total_pieces") or 0) for x in all_active_logs])
                        sum_vol = sum([float(x.get("total_volume") or 0) for x in all_active_logs])

                        supabase.table("jigs").update({
                            "total_pcs_in_jig": sum_pcs,
                            "total_volume": sum_vol
                        }).eq("jig_id", current_jig_id).execute()
                
                        st.success("✅ อัปเดตบ่อสีสำเร็จ")
                        time.sleep(1)
                        st.rerun()
                
                    except Exception as e:
                        st.error(f"อัปเดตไม่สำเร็จ: {e}")

        # =========================================================
        # 🏁 TAB เสร็จสิ้นงาน
        # =========================================================
        with sub_finish:
        
            st.subheader("🏁 เสร็จสิ้นงาน")
        
            try:
                active_logs = (
                    supabase.table("jig_usage_log")
                    .select("*")
                    .neq("status", "finished")
                    .or_("tank_id.not.is.null,color.eq.clear")
                    .order("recorded_date", desc=True)
                    .execute()
                )
                active_jobs = active_logs.data or []
            except Exception as e:
                st.error(f"โหลดงานไม่สำเร็จ: {e}")
                active_jobs = []
        
            if not active_jobs:
                st.success("✅ ไม่มีงานที่ต้องปิด")
            else:
                active_df = pd.DataFrame(active_jobs)
                products = load_products()
        
                product_map = {
                    p["product_id"]: f"{p['product_code']} | {p['product_name']}"
                    for p in products
                }
        
                jig_rows = (
                    supabase.table("jigs")
                    .select("jig_id, jig_model_code")
                    .execute()
                    .data
                    or []
                )
        
                jig_map = {
                    j["jig_id"]: j["jig_model_code"]
                    for j in jig_rows
                }
        
                active_df["display"] = active_df.apply(
                    lambda row: (
                        f"{product_map.get(row['product_id'], 'Unknown')} "
                        f"| Jig: {jig_map.get(row['jig_id'], '-')}"
                        f"| Qty: {row.get('total_pieces',0)}"
                        f"| Tank: {row.get('tank_name_snapshot', '-')}"
                    ),
                    axis=1
                )
        
                close_count = st.number_input(
                    "จำนวนงานที่ต้องการปิด",
                    min_value=1,
                    max_value=len(active_df),
                    value=1
                )
        
                st.info(f"ระบบจะปิดงานล่าสุดจำนวน {close_count} รายการ")
        
                st.dataframe(
                    active_df[["display", "recorded_date"]].head(close_count),
                    use_container_width=True,
                    hide_index=True
                )
        
                if st.button("🏁 ยืนยันเสร็จสิ้นงาน", use_container_width=True):
                    try:
                        rows_to_close = active_df.head(close_count)
                        jigs_to_refresh = set()
        
                        for _, row in rows_to_close.iterrows():
                            current_jig_id = int(row["jig_id"])
                            jigs_to_refresh.add(current_jig_id)
        
                            # ===== update jig_usage_log =====
                            supabase.table("jig_usage_log").update({
                                "status": "finished"
                            }).eq("log_id", int(row["log_id"])).execute()
        
                            # ===== update jig_status =====
                            supabase.table("jig_status").upsert({
                                "jig_id": current_jig_id,
                                "status_type": "Finished",
                                "current_tank_id": None,
                                "updated_at": datetime.now(ICT).isoformat()
                            }).execute()
                        
                        # 🛠️ จุดแก้ไขที่ 3: คำนวณยอดคงเหลือใหม่สำหรับทุกจิ๊กที่พึ่งโดนปิดงานไป (ถ้าไม่มีงานค้าง ยอดต้องเป็น 0)
                        for target_jig_id in jigs_to_refresh:
                            remain_logs = supabase.table("jig_usage_log").select("total_pieces, total_volume").eq("jig_id", target_jig_id).neq("status", "finished").execute().data or []
                            remain_pcs = sum([int(x.get("total_pieces") or 0) for x in remain_logs])
                            remain_vol = sum([float(x.get("total_volume") or 0) for x in remain_logs])
                            
                            supabase.table("jigs").update({
                                "total_pcs_in_jig": remain_pcs,
                                "total_volume": remain_vol
                            }).eq("jig_id", target_jig_id).execute()
        
                        st.success(f"✅ ปิดงานสำเร็จ {close_count} รายการ")
                        time.sleep(1)
                        st.rerun()
        
                    except Exception as e:
                        st.error(f"ปิดงานไม่สำเร็จ: {e}")

elif menu == "🛠️ จัดการและแก้ไขข้อมูล":
    show_data_editor()
