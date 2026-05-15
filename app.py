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
        min-width:1100px;
        height:720px;
        background:#e9e9e9;
        border:2px solid #999;
        margin:auto;
        overflow:Auto;
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

        <div class="tank" data-tank="1DarkRedA"
            style="left:270px;top:252px;width:80px;height:35px;background:darkred;">
            1.DarkRed
        </div>

        <div class="tank vertical" data-tank="7Pink"
            style="left:380px;top:210px;width:85px;height:130px;background:magenta;">
            7.Pink
        </div>

        <div class="tank" data-tank="HotSealH60"
            style="left:540px;top:190px;width:85px;height:130px;background:#777;">
            HotSeal
        </div>

        <div class="tank vertical" data-tank="11Gold"
            style="left:540px;top:325px;width:85px;height:120px;background:#d4af00;color:black;">
            11.Gold
        </div>

        <!-- RIGHT -->

        <div class="tank" data-tank="1DarkRedB"
            style="left:785px;top:200px;width:65px;height:55px;background:darkred;">
            1.DarkRed
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

        <div class="tank" data-tank="13DarkTitanium"
            style="left:310px;top:120px;width:80px;height:40px;background:#666;">
            13.DarkTitanium
        </div>

        <div class="tank"
            style="left:390px;top:120px;width:80px;height:40px;background:#666;">
        </div>

        <!-- ORANGE OIL -->

        <div class="tank" data-tank="18OrangeOil"
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

        if is_sealer:
            st.info(f"💡 บ่อ {clicked_tank_name}: บันทึกเฉพาะค่า **Temperature**")
        else:
            st.info(f"💡 บ่อ {clicked_tank_name}: บันทึกค่า **Temp, pH และ Density**")

        with st.form("dialog_chemical_log_form", clear_on_submit=True):
            temp_val = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")

            ph_val = None
            den_val = None

            if not is_sealer:
                ph_val = st.number_input("ค่า pH", step=0.01, format="%.2f")
                den_val = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f")

            if st.form_submit_button("💾 บันทึกข้อมูล"):
                payload = {
                "tank_id": chemical_tanks[clicked_tank_name],
                "tank_name_snapshot": clicked_tank_name,
                "temperature": temp_val,
                "recorded_at": datetime.now(ICT).isoformat()
            }

                if not is_sealer:
                    payload["ph_value"] = ph_val
                    payload["density"] = den_val
                else:
                    payload["ph_value"] = 0.0
                    payload["density"] = 0.0

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
                product_code = st.text_input("รหัสสินค้า", value=p.get("product_code", ""))
                product_name = st.text_input("ชื่อสินค้า", value=p.get("product_name", ""))
                surface_finish = st.text_input("พื้นผิว", value=p.get("surface_finish", ""))

                col_save, col_delete = st.columns(2)
                if col_save.form_submit_button("💾 บันทึกสินค้า"):
                    try:
                        update_row("products", "product_id", p["product_id"], {
                            "product_code": product_code,
                            "product_name": product_name,
                            "surface_finish": surface_finish
                        })
                        st.success("บันทึกข้อมูลสินค้าแล้ว")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")

                if col_delete.form_submit_button("🗑️ ลบสินค้า"):
                    try:
                        delete_row("products", "product_id", p["product_id"])
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
                total_pcs_in_jig = st.number_input("จำนวนชิ้นในจิ๊ก", min_value=0, value=int(j.get("total_pcs_in_jig") or 0))

                col_save, col_delete = st.columns(2)
                if col_save.form_submit_button("💾 บันทึกจิ๊ก"):
                    try:
                        update_row("jigs", "jig_id", j["jig_id"], {
                            "jig_model_code": jig_model_code,
                            "lot_no": lot_no,
                            "total_pcs_in_jig": total_pcs_in_jig
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
        # 1. กำหนดช่วงเวลาเริ่มและจบของวันที่เลือก (ISO Format สำหรับ timestamptz)
        start_of_day = f"{filter_date_str}T00:00:00+07:00"
        end_of_day = f"{filter_date_str}T23:59:59+07:00"

        st.subheader(f"⚡ รายการบันทึกจิ๊กของวันที่ {filter_date.strftime('%d/%m/%Y')}")
        
        # 2. แก้ไข Filter จาก .eq เป็น .gte และ .lte
        logs = supabase.table("jig_usage_log")\
            .select("*, products(product_code), jigs(jig_model_code)")\
            .gte("recorded_date", start_of_day)\
            .lte("recorded_date", end_of_day)\
            .order("recorded_date", desc=True).execute().data or []

        if not logs:
            st.warning(f"📅 ไม่มีข้อมูลบันทึกงานจิ๊กในวันที่ {filter_date}")
        else:
            # 1. เตรียมข้อมูล Log ที่จะแก้ไข
            log_map = {}
            for l in logs:
                dt_ict = datetime.fromisoformat(l.get('recorded_date').replace('Z', '+00:00')).astimezone(ICT)
                time_str = dt_ict.strftime("%H:%M")
                j_code = l.get('jigs', {}).get('jig_model_code', 'N/A')
                p_code = l.get('products', {}).get('product_code', 'N/A')
                label = f"⏰ {time_str} | จิ๊ก: {j_code} | สินค้าเดิม: {p_code}"
                log_map[label] = l
            
            selected_label = st.selectbox("เลือกรายการที่ต้องการจัดการ", list(log_map.keys()), key="edit_jiglog_sel")
            log = log_map[selected_label]
            id_col, id_val = get_pk(log, ["log_id", "id", "jig_usage_log_id"])

            # 2. ดึงรายชื่อสินค้าทั้งหมด เพื่อใช้เป็นตัวเลือกใหม่
            all_products = supabase.table("products").select("product_id, product_code, product_name").order("product_code").execute().data or []
            prod_options = {f"{p['product_code']} | {p['product_name']}": p['product_id'] for p in all_products}
            
            # หาตำแหน่ง (index) ของสินค้าเดิมในลิสต์ใหม่ เพื่อให้ Selectbox เริ่มที่ค่าเดิม
            current_prod_id = log.get('product_id')
            current_index = 0
            option_list = list(prod_options.keys())
            for i, label in enumerate(option_list):
                if prod_options[label] == current_prod_id:
                    current_index = i
                    break

            # 3. ฟอร์มการแก้ไข
            with st.form("edit_jiglog_form_v2"):
                st.markdown("### 🔄 เปลี่ยนชิ้นงานและแก้ไขจำนวน")
                
                # แสดงชื่อสินค้าเดิมเพื่อให้อ้างอิงง่าย
                old_p_code = log.get('products', {}).get('product_code', 'N/A')
                old_p_name = log.get('products', {}).get('product_name', 'N/A')
                st.text_input("ชิ้นงานเดิม (อ่านเท่านั้น)", value=f"{old_p_code} - {old_p_name}", disabled=True)
                
                # เลือกชิ้นงานใหม่
                new_product_id = st.selectbox(
                    "เลือกชิ้นงานใหม่ (หากต้องการเปลี่ยน)", 
                    options=option_list, 
                    index=current_index
                )
                selected_prod_id = prod_options[new_product_id]

                col1, col2, col3 = st.columns(3)
                pcs_per_row = col1.number_input("จำนวนต่อแถว", min_value=0, value=int(log.get("pcs_per_row") or 0))
                rows_filled = col2.number_input("แถวที่เต็ม", min_value=0, value=int(log.get("rows_filled") or 0))
                partial_pieces = col3.number_input("เศษ", min_value=0, value=int(log.get("partial_pieces") or 0))

                total_pieces = (pcs_per_row * rows_filled) + partial_pieces
                st.info(f"🔢 จำนวนรวมใหม่: {total_pieces} ชิ้น")

                col_save, col_delete = st.columns(2)
                
                if col_save.form_submit_button("💾 บันทึกการเปลี่ยนแปลง"):
                    try:
                        update_row("jig_usage_log", id_col, id_val, {
                            "product_id": selected_prod_id, # บันทึก ID ชิ้นงานใหม่ลงไป
                            "pcs_per_row": pcs_per_row,
                            "rows_filled": rows_filled,
                            "partial_pieces": partial_pieces,
                            "total_pieces": total_pieces
                        })
                        st.success("อัปเดตข้อมูลและเปลี่ยนชิ้นงานเรียบร้อยแล้ว!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")

                if col_delete.form_submit_button("🗑️ ลบบันทึกนี้"):
                    try:
                        delete_row("jig_usage_log", id_col, id_val)
                        st.success("ลบบันทึกงานจิ๊กแล้ว")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"ลบไม่สำเร็จ: {e}")

    with tab_color:
        st.subheader(f"🎨 บันทึกบ่อสีวันที่ {filter_date.strftime('%d/%m/%Y')}")
    
        start_dt = f"{filter_date_str}T00:00:00"
        end_dt = f"{filter_date_str}T23:59:59"
    
        color_logs = supabase.table("color_tank_logs")\
            .select("*")\
            .gte("recorded_at", start_dt)\
            .lte("recorded_at", end_dt)\
            .order("recorded_at", desc=True)\
            .execute().data or []
    
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
                "เลือกบ่อสารเคมี",
                chem_tanks,
                key="chem_tank_filter"
            )
    
            chem_df = df_chem[
                df_chem["tank_name"] == selected_chem
            ].copy()
    
            is_sealer = (
                "seal" in selected_chem.lower()
                or "sealer" in selected_chem.lower()
            )
    
            # ===== ตาราง =====
            if is_sealer:
    
                show_df = chem_df[[
                    "เวลา",
                    "temperature"
                ]].rename(columns={
                    "temperature": "Temp"
                })
    
            else:
    
                show_df = chem_df[[
                    "เวลา",
                    "ph_value",
                    "temperature",
                    "density"
                ]].rename(columns={
                    "ph_value": "pH",
                    "temperature": "Temp",
                    "density": "Density"
                })
    
            st.dataframe(
                show_df,
                use_container_width=True,
                hide_index=True
            )
    
            st.markdown("---")
            st.subheader("✏️ แก้ไขข้อมูล")
    
            for idx, row in chem_df.iterrows():
    
                with st.expander(f"⏰ {row['เวลา']}"):
    
                    with st.form(f"edit_chem_{idx}"):
    
                        temperature = st.number_input(
                            "Temperature",
                            value=float(row["temperature"] or 0),
                            step=0.1,
                            format="%.1f"
                        )
    
                        if not is_sealer:
    
                            ph_value = st.number_input(
                                "pH",
                                value=float(row["ph_value"] or 0),
                                step=0.01,
                                format="%.2f"
                            )
    
                            density = st.number_input(
                                "Density",
                                value=float(row["density"] or 0),
                                step=0.001,
                                format="%.3f"
                            )
    
                        col1, col2 = st.columns(2)
    
                        if col1.form_submit_button("💾 บันทึก"):
    
                            payload = {
                                "temperature": temperature
                            }
    
                            if not is_sealer:
                                payload["ph_value"] = ph_value
                                payload["density"] = density
    
                            update_row(
                                "anodize_tank_logs",
                                "id",
                                row["id"],
                                payload
                            )
    
                            st.success("บันทึกสำเร็จ")
                            time.sleep(1)
                            st.rerun()
    
                        if col2.form_submit_button("🗑️ ลบ"):
    
                            delete_row(
                                "anodize_tank_logs",
                                "id",
                                row["id"]
                            )
    
                            st.success("ลบสำเร็จ")
                            time.sleep(1)
                            st.rerun()

#=================================================================   
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต", "🛠️ จัดการและแก้ไขข้อมูล"])

# ================= DASHBOARD (COMPACT & FIXED VERSION) =================
if menu == "Dashboard":
    st.title("📊 Production Dashboard")

    # --- 1. Global Filter (Sidebar) ---
    st.sidebar.subheader("📅 Filter Setting")
    time_unit = st.sidebar.selectbox(
        "มุมมองเวลา",
        ["รายวัน (เลือกหลายวัน)", "รายเดือน", "รายไตรมาส", "รายปี"]
    )
    
    # *** แก้ NameError: ประกาศค่าเริ่มต้นไว้ก่อน ***
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
        "SEAL_TEMP": [90, 98]
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
    
            tanks = get_options(
                "tanks",
                "tank_id",
                "tank_name"
            )
    
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
    
            # ===== pH =====
            if "ph_value" in row and pd.notnull(row["ph_value"]):
    
                ph_val = float(row["ph_value"])
    
                if ph_val < p_min or ph_val > p_max:
                    ph_alert = f"❌ {ph_val:.2f}"
    
                elif ph_val <= p_min + 0.2 or ph_val >= p_max - 0.2:
                    ph_alert = f"⚠️ {ph_val:.2f}"
    
            # ===== Temperature =====
            if "temperature" in row and pd.notnull(row["temperature"]):
    
                temp_val = float(row["temperature"])
    
                if temp_val < t_min or temp_val > t_max:
                    temp_alert = f"❌ {temp_val:.1f}"
    
                elif temp_val <= t_min + 2 or temp_val >= t_max - 2:
                    temp_alert = f"⚠️ {temp_val:.1f}"
    
            # ===== แสดงเฉพาะรายการที่มีแจ้งเตือน =====
            if ph_alert or temp_alert:
    
                alerts.append({
                    "บ่อ": row["tank_name"],
                    "pH": ph_alert,
                    "อุณหภูมิ": temp_alert,
                    "เวลา": row["recorded_at"].strftime('%d/%m %H:%M')
                })
    
        # ===== เรียงล่าสุดขึ้นก่อน =====
        if alerts:
    
            alert_df = pd.DataFrame(alerts)
    
            st.dataframe(
                alert_df,
                hide_index=True,
                use_container_width=True,
                height=220
            )
    
        else:
            st.caption("✅ ทุกค่าปกติ")

    # --- 1. Color Tanks ---
    st.subheader("🎨 Color Tanks")
    col1, col2 = st.columns([1, 2.5])
    if c_logs:
        df_c = pd.DataFrame(c_logs)
        df_c["recorded_at"] = pd.to_datetime(df_c["recorded_at"]).dt.tz_convert(ICT)
        df_c["tank_name"] = df_c["tank_name_snapshot"]
        latest_c = df_c.drop_duplicates("tank_id").sort_values("tank_name")
        with col1:
            st.caption("🚨 Alerts")
            show_alert_table_mini(latest_c, *STD["COLOR_PH"], *STD["COLOR_TEMP"])
        with col2:
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            fig1.add_trace(go.Bar(x=latest_c["tank_name"], y=latest_c["ph_value"], name="pH", marker_color="#2ECC71", offsetgroup=1, text=latest_c["ph_value"], textposition='outside', textfont_size=9), secondary_y=False)
            fig1.add_trace(go.Bar(x=latest_c["tank_name"], y=latest_c["temperature"], name="T", marker_color="#3498DB", offsetgroup=2, text=latest_c["temperature"], textposition='outside', textfont_size=9), secondary_y=True)
            fig1.update_layout(height=250, margin=dict(l=5,r=5,t=20,b=5), barmode="group", showlegend=False, yaxis_showgrid=False, yaxis2_showgrid=False)
            st.plotly_chart(fig1, use_container_width=True)

    # --- 2. Anodize/Seal ---
    st.markdown("---")
    st.subheader("📈 Anodize & Seal")
    if a_logs:
        df_a = pd.DataFrame(a_logs)
        df_a["recorded_at"] = pd.to_datetime(df_a["recorded_at"]).dt.tz_convert(ICT)
        df_a["tank_name"] = df_a["tank_id"].map(inv_tank_map)
        if time_unit == "รายวัน (เลือกหลายวัน)":

            f_df_a = df_a[
                df_a["recorded_at"].dt.date.isin(selected_dates)
            ]
        
        else:
        
            f_df_a = df_a[
                (df_a["recorded_at"] >= g_start_dt) &
                (df_a["recorded_at"] <= g_end_dt)
            ]
        
        c_sel1, c_sel2 = st.columns([1, 3])
        with c_sel1:
            sel_ano = st.selectbox("เลือกบ่อ", sorted(df_a["tank_name"].dropna().unique()), key="sb_ano")
            latest_a = df_a[df_a["tank_name"] == sel_ano].head(1)
            is_seal = "seal" in sel_ano.lower()
            if is_seal: show_alert_table_mini(latest_a, 0, 14, *STD["SEAL_TEMP"])
            else: show_alert_table_mini(latest_a, *STD["ANO_PH"], *STD["ANO_TEMP"])
        
        with c_sel2:
            chart_df = f_df_a[f_df_a["tank_name"] == sel_ano].sort_values("recorded_at")
            if not chart_df.empty:
                if is_seal:
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=chart_df["recorded_at"], y=chart_df["temperature"], mode='lines+markers', line_color="#E74C3C"))
                    fig_s.add_hrect(y0=STD["SEAL_TEMP"][0], y1=STD["SEAL_TEMP"][1], fillcolor="green", opacity=0.1, line_width=0)
                    fig_s.update_layout(height=180, margin=dict(l=5,r=5,t=10,b=5), yaxis_showgrid=False)
                    st.plotly_chart(fig_s, use_container_width=True)
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

    # --- 3. Compare ---
    st.markdown("---")
    st.subheader("🔍 Compare Trend")
    if c_logs:
        c_m1, c_m2 = st.columns([1, 3])
        with c_m1:
            sel_tanks = st.multiselect("เลือกบ่อสี", sorted(df_c["tank_name"].unique()), default=sorted(df_c["tank_name"].unique())[:1])
        with c_m2:
            if time_unit == "รายวัน (เลือกหลายวัน)":

                f_df_c = df_c[
                    df_c["recorded_at"].dt.date.isin(selected_dates)
                ]
            
            else:
            
                f_df_c = df_c[
                    (df_c["recorded_at"] >= g_start_dt) &
                    (df_c["recorded_at"] <= g_end_dt)
                ]
            if not f_df_c.empty and sel_tanks:
                fig_mix = make_subplots(specs=[[{"secondary_y": True}]])
                # ===== พื้นที่มาตรฐาน pH =====
                fig_mix.add_shape(
                    type="rect",
                    xref="paper",
                    yref="y",
                    x0=0,
                    x1=1,
                    y0=5,
                    y1=6,
                    fillcolor="#22C55E",
                    opacity=0.05,
                    layer="below",
                    line_width=0,
                )
                
                # ===== พื้นที่มาตรฐาน Temperature =====
                fig_mix.add_shape(
                    type="rect",
                    xref="paper",
                    yref="y2",
                    x0=0,
                    x1=1,
                    y0=30,
                    y1=40,
                    fillcolor="#F59E0B",
                    opacity=0.04,
                    layer="below",
                    line_width=0,
                )
                
                for t_name in sel_tanks:
                    t_data = f_df_c[f_df_c["tank_name"] == t_name].sort_values("recorded_at")
                
                    # หา "ชื่อสีจริง"
                    color_name = tank_color_map.get(t_name, "Gray")
                
                    # หา HEX จาก COLOR_HEX_MAP
                    clr = COLOR_HEX_MAP.get(color_name, "#666666")

                    temp_clr = lighten_color(clr)
                
                    # ===== pH =====
                    fig_mix.add_trace(
                        go.Scatter(
                            x=t_data["recorded_at"],
                            y=t_data["ph_value"],
                            name=f"pH : {t_name}",
                            mode="lines+markers",
                            line=dict(
                                color=clr,
                                width=3
                            ),
                            marker=dict(
                                size=7,
                                symbol="circle",
                                color=clr
                            )
                        ),
                        secondary_y=False
                    )
                
                    # ===== Temperature =====
                    fig_mix.add_trace(
                        go.Scatter(
                            x=t_data["recorded_at"],
                            y=t_data["temperature"],
                            name=f"Temp : {t_name}",
                            mode="lines+markers",
                            line=dict(
                                color=temp_clr,
                                width=2,
                                dash="dot"
                            ),
                            marker=dict(
                                size=6,
                                line=dict(width=1, color="white"),
                                symbol="square",
                                color=temp_clr
                            )
                        ),
                        secondary_y=True
                    )
                
                fig_mix.update_layout(
                    height=420,
                    margin=dict(l=5, r=5, t=10, b=5),
                    legend=dict(font_size=9),
                    yaxis_showgrid=False,
                    yaxis2_showgrid=False,
                    plot_bgcolor="#F8FAFC",
                    paper_bgcolor="#F8FAFC",
                )
                
                fig_mix.update_yaxes(title_text="pH", secondary_y=False)
                fig_mix.update_yaxes(title_text="Temperature (°C)", secondary_y=True)
                fig_mix.update_yaxes(
                    showgrid=True,
                    gridcolor="rgba(148,163,184,0.15)",
                    secondary_y=False
                )
                
                fig_mix.update_yaxes(
                    showgrid=False,
                    secondary_y=True
                )
                st.plotly_chart(fig_mix, use_container_width=True)
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
        except Exception:
            pass
    
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
                        selected_display = st.selectbox("เลือกสินค้า (รหัส | ชื่อ)", options=list(display_options.keys()), key="sel_p_log")
                        selected_prod_id = display_options[selected_display]
                        p_info = supabase.table("products").select("*").eq("product_id", selected_prod_id).single().execute().data
                        action = st.radio("การทำงาน", ["🔵 บันทึกงานต่อ", "🟢 เสร็จสิ้นงาน"], key="action_radio")

                        if action == "🔵 บันทึกงานต่อ":
                            sel_c_new = st.selectbox("เลือกสี", sorted(set(tank_color_map.values())), key="sel_c_log")
                            filtered_tanks = {n: i for n, i in color_tanks_all.items() if tank_color_map.get(n) == sel_c_new}
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

elif menu == "🛠️ จัดการและแก้ไขข้อมูล":
    show_data_editor()
