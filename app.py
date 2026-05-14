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
    components.html(html, height=750, scrolling=False)


# ================= 3. EDIT DATA (ปรับให้โชว์ รหัส + ชื่อสินค้า) =================
def show_data_editor():
    st.title("🛠️ จัดการและแก้ไขข้อมูลย้อนหลัง")
    
    edit_mode = st.radio("เลือกสิ่งที่ต้องการแก้ไข", ["📦 ข้อมูลสินค้า (Products)", "📜 ประวัติงานจิ๊ก (Jig Logs)"], horizontal=True)

    if edit_mode == "📦 ข้อมูลสินค้า (Products)":
        st.subheader("แก้ไขข้อมูลสินค้าแบบละเอียด")
        res = supabase.table("products").select("*").execute()
        if res.data:
            prod_options = {f"{p['product_code']} | {p['product_name']}": p for p in res.data}
            selected_p_label = st.selectbox("เลือกสินค้าที่ต้องการแก้ไข", list(prod_options.keys()))
            p_data = prod_options[selected_p_label]
            
            # --- ส่วนสำคัญ: ย้าย Selectbox เลือกทรงออกมานอก Form เพื่อให้ UI เปลี่ยนตามทันที ---
            current_shape_in_db = p_data.get('shape', 'สี่เหลี่ยม')
            shapes = ["สี่เหลี่ยม", "ทรงกระบอกทึบ", "ทรงกระบอกกลวง"]
            
            # ใช้ st.selectbox ตรงนี้เพื่อให้แอป Rerun เมื่อเปลี่ยนค่า
            new_shape = st.selectbox("เปลี่ยนรูปทรง", shapes, index=shapes.index(current_shape_in_db) if current_shape_in_db in shapes else 0)
            
            # หลังจากเลือกทรงแล้ว ค่อยเข้าสู่ฟอร์มแก้ไขข้อมูลที่เหลือ
            with st.form("edit_product_form_v3"):
                col1, col2 = st.columns(2)
                new_code = col1.text_input("รหัสสินค้า", value=p_data['product_code'])
                new_name = col1.text_input("ชื่อสินค้า", value=p_data['product_name'])
                new_finish = col2.text_input("พื้นผิว (Surface)", value=p_data.get('surface_finish', '-'))

                st.divider()
                st.write(f"📏 **แก้ไขสัดส่วนชิ้นงาน (ทรง: {new_shape})**")
                
                c_a, c_b, c_c = st.columns(3)
                # ดึงค่าเดิมมาเป็นค่าเริ่มต้น (Default Value)
                h = c_a.number_input("ความสูง/ยาว (H) [mm]", min_value=0.0, value=float(p_data.get('height', 0)))
                
                u_vol, w, t, od, id_inner = 0.0, 0.0, 0.0, 0.0, 0.0

                # เงื่อนไขการโชว์ช่องกรอก จะเปลี่ยนตาม new_shape ที่เลือกไว้นอกฟอร์ม
                if new_shape == "สี่เหลี่ยม":
                    w = c_b.number_input("กว้าง [mm]", min_value=0.0, value=float(p_data.get('width', 0)))
                    t = c_c.number_input("หนา [mm]", min_value=0.0, value=float(p_data.get('thickness', 0)))
                    u_vol = h * w * t
                elif new_shape == "ทรงกระบอกทึบ":
                    od = c_b.number_input("เส้นผ่านศูนย์กลาง (OD) [mm]", min_value=0.0, value=float(p_data.get('outer_diameter', 0)))
                    u_vol = math.pi * ((od/2)**2) * h
                elif new_shape == "ทรงกระบอกกลวง":
                    od = c_b.number_input("OD [mm]", min_value=0.0, value=float(p_data.get('outer_diameter', 0)))
                    t_wall = c_c.number_input("ความหนาเนื้อ [mm]", min_value=0.0, value=float(p_data.get('thickness', 0)))
                    id_inner = max(0.0, od - (2 * t_wall))
                    u_vol = math.pi * ((od/2)**2 - (id_inner/2)**2) * h
                    t = t_wall 

                st.info(f"💡 ปริมาตรที่คำนวณใหม่: **{u_vol:,.2f} mm³**")
                
                if st.form_submit_button("💾 บันทึกการเปลี่ยนแปลงสินค้า"):
                    try:
                        supabase.table("products").update({
                            "product_code": new_code,
                            "product_name": new_name,
                            "shape": new_shape,
                            "unit_volume": u_vol,
                            "height": h,
                            "width": w,
                            "thickness": t,
                            "outer_diameter": od,
                            "inner_diameter": id_inner,
                            "surface_finish": new_finish
                        }).eq("product_id", p_data['product_id']).execute()
                        
                        st.success("✅ อัปเดตข้อมูลสำเร็จ!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")

    elif edit_mode == "📜 ประวัติงานจิ๊ก (Jig Logs)":
        st.subheader("แก้ไขประวัติการบันทึกงานแบบละเอียด")
        
        # 1. คัดกรองวันที่
        col_f1, col_f2 = st.columns([1, 2])
        filter_date = col_f1.date_input("📅 เลือกวันที่", datetime.now(ICT))
        
        start_dt = filter_date.strftime("%Y-%m-%d 00:00:00")
        end_dt = filter_date.strftime("%Y-%m-%d 23:59:59")
        
        logs_res = supabase.table("jig_usage_log")\
            .select("*, products(*), jigs(jig_model_code)")\
            .gte("recorded_date", start_dt)\
            .lte("recorded_date", end_dt)\
            .order("recorded_date", desc=True).execute()
        
        if logs_res.data:
            # ปรับตรงนี้: ให้แสดงชื่อสินค้าในรายการ Log ด้วย
            log_options = {
                f"🕒 {l['recorded_date'][11:16]}น. | จิ๊ก: {l['jigs']['jig_model_code']} | สินค้า: {l['products']['product_code']} - {l['products']['product_name']}": l 
                for l in logs_res.data
            }
            selected_log_label = st.selectbox(f"รายการวันที่ {filter_date}", list(log_options.keys()))
            l_data = log_options[selected_log_label]
            
            with st.form("edit_log_detailed_form"):
                st.markdown(f"### 📝 แก้ไขข้อมูลจิ๊ก: `{l_data['jigs']['jig_model_code']}`")
                
                c1, c2 = st.columns(2)
                # ดึงรายการสินค้าทั้งหมด และปรับให้โชว์ รหัส | ชื่อ ในเมนูแก้ไข
                all_prods = supabase.table("products").select("product_id, product_code, product_name").execute().data
                prod_list_display = {f"{p['product_code']} | {p['product_name']}": p['product_id'] for p in all_prods}
                
                # หาค่า Default สำหรับเมนูเลือกสินค้า
                current_p_label = f"{l_data['products']['product_code']} | {l_data['products']['product_name']}"
                
                new_p_label = c1.selectbox("เปลี่ยนสินค้า", list(prod_list_display.keys()), 
                                           index=list(prod_list_display.keys()).index(current_p_label) if current_p_label in prod_list_display else 0)
                
                color_list = sorted(list(set(TANK_COLOR_MAP.values())))
                current_color = l_data.get('color', color_list[0])
                new_color = c2.selectbox("เปลี่ยนสี", color_list, 
                                         index=color_list.index(current_color) if current_color in color_list else 0)
                
                st.divider()
                
                col_a, col_b, col_c = st.columns(3)
                new_pcs_per_row = col_a.number_input("จำนวนต่อแถว", min_value=0, value=int(l_data.get('pcs_per_row', 0)))
                new_rows = col_b.number_input("จำนวนแถวที่เต็ม", min_value=0, value=int(l_data.get('rows_filled', 0)))
                new_partial = col_c.number_input("เศษ (ชิ้น)", min_value=0, value=int(l_data.get('partial_pieces', 0)))
                
                new_total_pcs = (new_rows * new_pcs_per_row) + new_partial
                
                # ดึงค่าปริมาตรจากสินค้าตัวที่เลือกใหม่
                selected_prod_id = prod_list_display[new_p_label]
                selected_prod_info = supabase.table("products").select("unit_volume").eq("product_id", selected_prod_id).single().execute().data
                u_vol = selected_prod_info['unit_volume'] or 0
                new_total_vol = new_total_pcs * u_vol
                
                st.info(f"📊 **สรุปยอดใหม่:** จำนวนรวม **{new_total_pcs}** ชิ้น | ปริมาตรรวม **{new_total_vol:,.2f}** mm³")
                
                if st.form_submit_button("💾 ยืนยันการแก้ไขข้อมูลทั้งหมด"):
                    try:
                        supabase.table("jig_usage_log").update({
                            "product_id": selected_prod_id,
                            "color": new_color,
                            "pcs_per_row": new_pcs_per_row,
                            "rows_filled": new_rows,
                            "partial_pieces": new_partial,
                            "total_pieces": new_total_pcs,
                            "total_volume": new_total_vol
                        }).eq("log_id", l_data['log_id']).execute()
                        
                        st.success("✅ แก้ไขข้อมูลเรียบร้อยแล้ว!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
        else:
            st.warning(f"❌ ไม่พบประวัติในวันที่ {filter_date}")

#=================================================================   
menu = st.sidebar.radio("เมนู", ["Dashboard","บันทึกข้อมูลการผลิต", "🛠️ จัดการและแก้ไขข้อมูล"])

# ================= DASHBOARD (COMPACT & FIXED VERSION) =================
if menu == "Dashboard":
    st.title("📊 Production Dashboard")

    # --- 1. Global Filter (Sidebar) ---
    st.sidebar.subheader("📅 Filter Setting")
    time_unit = st.sidebar.selectbox("มุมมองเวลา", ["รายวัน (ปฏิทิน)", "รายเดือน", "รายไตรมาส", "รายปี"])
    
    # *** แก้ NameError: ประกาศค่าเริ่มต้นไว้ก่อน ***
    now_ict = datetime.now(ICT)
    g_start_dt = now_ict.replace(hour=0, minute=0, second=0, microsecond=0)
    g_end_dt = now_ict.replace(hour=23, minute=59, second=59, microsecond=999)

    if time_unit == "รายวัน (ปฏิทิน)":
        selected_date = st.sidebar.date_input("เลือกวันที่", now_ict)
        g_start_dt = datetime.combine(selected_date, datetime.min.time()).replace(tzinfo=ICT)
        g_end_dt = datetime.combine(selected_date, datetime.max.time()).replace(tzinfo=ICT)
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
        c_logs = supabase.table("color_tank_logs").select("*").order("recorded_at", desc=True).limit(500).execute().data
        a_logs = supabase.table("anodize_tank_logs").select("*").order("recorded_at", desc=True).limit(500).execute().data
        tanks = get_options("tanks", "tank_id", "tank_name")
        return c_logs, a_logs, tanks

    c_logs, a_logs, tank_map = load_dashboard_data()
    inv_tank_map = {v: k for k, v in tank_map.items()}

    # --- Helper: Alert Table (Compact) ---
    def show_alert_table_mini(df, p_min, p_max, t_min, t_max):
        alerts = []
        for _, row in df.iterrows():
            status = []
            if "ph_value" in row and pd.notnull(row["ph_value"]):
                if row["ph_value"] < p_min or row["ph_value"] > p_max: status.append("❌pH")
                elif row["ph_value"] <= p_min+0.2 or row["ph_value"] >= p_max-0.2: status.append("⚠️pH")
            if "temperature" in row and pd.notnull(row["temperature"]):
                if row["temperature"] < t_min or row["temperature"] > t_max: status.append("❌T")
                elif row["temperature"] <= t_min+2 or row["temperature"] >= t_max-2: status.append("⚠️T")
            if status: alerts.append({"บ่อ": row["tank_name"], "สถานะ": " ".join(status), "เวลา": row["recorded_at"].strftime('%H:%M')})
        if alerts: st.dataframe(pd.DataFrame(alerts), hide_index=True, height=120)
        else: st.caption("✅ ปกติ")

    # --- 1. Color Tanks ---
    st.subheader("🎨 Color Tanks")
    col1, col2 = st.columns([1, 2.5])
    if c_logs:
        df_c = pd.DataFrame(c_logs)
        df_c["recorded_at"] = pd.to_datetime(df_c["recorded_at"]).dt.tz_convert(ICT)
        df_c["tank_name"] = df_c["tank_id"].map(inv_tank_map)
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
        f_df_a = df_a[(df_a["recorded_at"] >= g_start_dt) & (df_a["recorded_at"] <= g_end_dt)]
        
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
            f_df_c = df_c[(df_c["recorded_at"] >= g_start_dt) & (df_c["recorded_at"] <= g_end_dt)]
            if not f_df_c.empty and sel_tanks:
                fig_mix = make_subplots(specs=[[{"secondary_y": True}]])
                colors = ["#1abc9c", "#3498db", "#9b59b6", "#f1c40f", "#e67e22"]
                for i, t_name in enumerate(sel_tanks):
                    t_data = f_df_c[f_df_c["tank_name"] == t_name].sort_values("recorded_at")
                    clr = colors[i % len(colors)]
                    fig_mix.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["ph_value"], name=f"pH:{t_name}", line_color=clr), secondary_y=False)
                    fig_mix.add_trace(go.Scatter(x=t_data["recorded_at"], y=t_data["temperature"], name=f"T:{t_name}", line=dict(color=clr, dash='dot')), secondary_y=True)
                fig_mix.update_layout(height=250, margin=dict(l=5,r=5,t=10,b=5), legend=dict(font_size=9), yaxis_showgrid=False, yaxis2_showgrid=False)
                st.plotly_chart(fig_mix, use_container_width=True)
# ================= RECORD PAGE =================
if menu == "บันทึกข้อมูลการผลิต":
    st.title("📝 ระบบบันทึกข้อมูล (Interactive Map)")

    if "tank_read_round" not in st.session_state:
        st.session_state["tank_read_round"] = 0

    if st.button("โหลดบ่อที่คลิก", key="load_clicked_tank_btn"):
        st.session_state["tank_read_round"] += 1

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

    render_tank_map(clicked_tank_name)

    if clicked_tank_name:
        st.success(f"เลือกบ่อจากผัง: {clicked_tank_name}")
    else:
        st.info("กรุณาคลิกบ่อบนผัง แล้วกดโหลดบ่อที่คลิก")



    tab_main = st.tabs(["ฟอร์มบันทึกบ่อที่เลือก", "งานจิ๊ก (Jig System)"])

    with tab_main[0]:
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
    
        if not clicked_tank_name:
            st.info("กรุณาคลิกบ่อบนผัง แล้วกดโหลดบ่อที่คลิก")
    
        elif clicked_tank_name in color_tanks:
            selected_tank_name = clicked_tank_name
    
            st.subheader(f"🎨 บันทึกข้อมูลบ่อสี: {selected_tank_name}")
            detected_color = TANK_COLOR_MAP.get(selected_tank_name, "Black")
            render_color_bar(detected_color)
    
            with st.form("color_log_form", clear_on_submit=True):
                ph = st.number_input("ค่า pH", step=0.1, format="%.2f")
                temp = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")
    
                if st.form_submit_button("บันทึกค่า"):
                    supabase.table("color_tank_logs").insert({
                        "tank_id": color_tanks[selected_tank_name],
                        "ph_value": ph,
                        "temperature": temp,
                        "recorded_at": datetime.now(ICT).isoformat()
                    }).execute()
    
                    st.success("✅ บันทึกข้อมูลบ่อสีสำเร็จ")
                    time.sleep(1)
                    st.rerun()
    
        elif clicked_tank_name in chemical_tanks:
            sel_tank_name = clicked_tank_name
    
            st.subheader(f"🧪 บันทึกข้อมูลบ่อสารเคมี: {sel_tank_name}")
    
            is_sealer = "sealer" in sel_tank_name.lower() or "seal" in sel_tank_name.lower()
    
            if is_sealer:
                st.info(f"💡 บ่อ {sel_tank_name}: บันทึกเฉพาะค่า **Temperature**")
            else:
                st.info(f"💡 บ่อ {sel_tank_name}: บันทึกค่า **Temp, pH และ Density**")
    
            with st.form("chemical_log_form", clear_on_submit=True):
                temp_val = st.number_input("อุณหภูมิ (°C)", step=0.1, format="%.1f")
    
                ph_val = None
                den_val = None
    
                if not is_sealer:
                    ph_val = st.number_input("ค่า pH", step=0.01, format="%.2f")
                    den_val = st.number_input("ความหนาแน่น (Density)", step=0.001, format="%.3f")
    
                if st.form_submit_button("💾 บันทึกข้อมูล"):
                    try:
                        payload = {
                            "tank_id": chemical_tanks[sel_tank_name],
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
                        st.success(f"✅ บันทึกข้อมูลบ่อ {sel_tank_name} สำเร็จ")
                        time.sleep(1.2)
                        st.rerun()
    
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
    
        else:
            st.warning(
                f"ไม่พบบ่อ `{clicked_tank_name}` ในฐานข้อมูล `tanks` "
                "กรุณาเช็คชื่อ data-tank ให้ตรงกับ tank_name"
            )

    # --- Tab หลัก 3: ระบบงานจิ๊ก (Jig System) ---
    with tab_main[1]:
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

elif menu == "🛠️ จัดการและแก้ไขข้อมูล":
    show_data_editor()
