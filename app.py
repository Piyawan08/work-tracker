import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time, timedelta, date
import io
import base64
import urllib.parse
from icalendar import Calendar, Event
from streamlit_calendar import calendar

# ----------------------------------------------------
# 1. การตั้งค่าหน้าเว็บ
# ----------------------------------------------------
st.set_page_config(
    page_title="Daily Work Log Tracker",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. ฟังก์ชันจัดการ Google Sheets
# ----------------------------------------------------
@st.cache_resource
def init_gsheet_connection():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    client = gspread.authorize(credentials)
    sheet = client.open(st.secrets["spreadsheet_name"]).worksheet("Tasks")
    return sheet

def load_data():
    try:
        sheet = init_gsheet_connection()
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "Task_ID", "Date", "Start_Time", "End_Time", 
                "Task_Name", "Category", "Details", "Attachment_URL", "Created_At"
            ])
        else:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก Google Sheets: {e}")
        return pd.DataFrame()

def append_multiple_tasks(task_list):
    try:
        sheet = init_gsheet_connection()
        rows = []
        for task_dict in task_list:
            rows.append([
                task_dict["Task_ID"],
                str(task_dict["Date"]),
                task_dict["Start_Time"],
                task_dict["End_Time"],
                task_dict["Task_Name"],
                task_dict["Category"],
                task_dict["Details"],
                task_dict["Attachment_URL"],
                task_dict["Created_At"]
            ])
        sheet.append_rows(rows)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"ไม่สามารถบันทึกลง Google Sheets ได้: {e}")
        return False

# ----------------------------------------------------
# 3. ฟังก์ชันปฏิทิน & แปลงไฟล์รูปภาพ
# ----------------------------------------------------
def generate_google_calendar_url(title, date_val, start_t, end_t, details):
    start_dt = datetime.combine(date_val, start_t)
    end_dt = datetime.combine(date_val, end_t)
    dates_fmt = f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
    
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": dates_fmt,
        "details": details,
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

def create_ics_file(title, date_val, start_t, end_t, details):
    cal = Calendar()
    cal.add('prodid', '-//Daily Work Tracker//TH//')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', title)
    event.add('dtstart', datetime.combine(date_val, start_t))
    event.add('dtend', datetime.combine(date_val, end_t))
    event.add('description', details)
    event.add('dtstamp', datetime.now())
    
    cal.add_component(event)
    return cal.to_ical()

def convert_image_to_base64(uploaded_file):
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        mime_type = uploaded_file.type
        b64_str = base64.b64encode(file_bytes).decode()
        return f"data:{mime_type};base64,{b64_str}"
    return ""

# ----------------------------------------------------
# 4. ส่วน Sidebar: ฟอร์มบันทึกงานใหม่
# ----------------------------------------------------
st.sidebar.title("✍️ บันทึกงานใหม่")

with st.sidebar.form("task_form", clear_on_submit=False):
    task_name = st.text_input("ชื่องาน / กิจกรรม *", placeholder="เช่น ประชุมชี้แจงแนวทางการปฏิบัติงาน")
    category = st.selectbox(
        "หมวดหมู่", 
        ["ประชุม/ประสานงาน", "งานเอกสาร/สารบรรณ", "วิเคราะห์ข้อมูล/สถิติ", "พัฒนาระบบ/ไอที", "อื่นๆ"]
    )
    
    st.markdown("**🗓️ รูปแบบวันที่**")
    date_mode = st.radio("ประเภทการจัดงาน", ["วันเดียว", "หลายวันติดต่อกัน (ช่วงวันที่)"], horizontal=True)
    
    if date_mode == "วันเดียว":
        single_date = st.date_input("วันที่ปฏิบัติงาน", datetime.now().date())
        date_range = [single_date, single_date]
    else:
        date_range = st.date_input("เลือกช่วงวันที่เริ่มต้น - สิ้นสุด", [datetime.now().date(), datetime.now().date() + timedelta(days=1)])
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.time_input("เวลาเริ่ม", time(9, 0))
    with col_t2:
        end_time = st.time_input("เวลาสิ้นสุด", time(16, 30))
        
    details = st.text_area("รายละเอียด / ระเบียบวาระ", placeholder="พิมพ์โน้ต วาระการประชุม หรือบันทึกข้อความ...")
    
    st.markdown("**📎 ไฟล์แนบ / รูปภาพ**")
    uploaded_file = st.file_uploader("อัปโหลดรูปภาพหรือไฟล์เอกสาร", type=["png", "jpg", "jpeg", "pdf"])
    attachment_url = st.text_input("หรือแนบลิงก์ Google Drive (ถ้ามี)", placeholder="https://drive.google.com/...")
    
    submit_btn = st.form_submit_button("💾 บันทึกลง Google Sheets", use_container_width=True)

# ตรวจสอบการส่งข้อมูล
if submit_btn:
    if not task_name:
        st.sidebar.error("กรุณาระบุชื่องาน")
    elif isinstance(date_range, (list, tuple)) and len(date_range) == 2 and date_range[0] > date_range[1]:
        st.sidebar.error("วันที่เริ่มต้นต้องไม่มากกว่าวันที่สิ้นสุด")
    elif start_time >= end_time:
        st.sidebar.error("เวลาเริ่มต้นต้องเกิดขึ้นก่อนเวลาสิ้นสุด")
    else:
        # จัดการช่วงวันที่
        if isinstance(date_range, (list, tuple)):
            start_d = date_range[0]
            end_d = date_range[1] if len(date_range) > 1 else date_range[0]
        else:
            start_d = date_range
            end_d = date_range

        days_count = (end_d - start_d).days + 1
        
        # จัดการไฟล์แนบ (ถ้ามีรูป ให้อ่านรูปเป็น Base64)
        final_attachment = attachment_url
        if uploaded_file is not None:
            image_data = convert_image_to_base64(uploaded_file)
            final_attachment = image_data

        tasks_to_create = []
        base_timestamp = int(datetime.now().timestamp())
        
        for i in range(days_count):
            curr_date = start_d + timedelta(days=i)
            # เติมคำระบุวันหากเป็นงานหลายวัน
            day_suffix = f" (วันที่ {i+1}/{days_count})" if days_count > 1 else ""
            
            tasks_to_create.append({
                "Task_ID": f"TSK-{base_timestamp}-{i+1}",
                "Date": curr_date,
                "Start_Time": start_time.strftime("%H:%M"),
                "End_Time": end_time.strftime("%H:%M"),
                "Task_Name": f"{task_name}{day_suffix}",
                "Category": category,
                "Details": details,
                "Attachment_URL": final_attachment,
                "Created_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        success = append_multiple_tasks(tasks_to_create)
        if success:
            st.session_state["last_saved_tasks"] = {
                "tasks": tasks_to_create,
                "start_time": start_time,
                "end_time": end_time,
                "details": details
            }
            st.sidebar.success(f"✅ บันทึกสำเร็จทั้งหมด {days_count} รายการ!")

# ----------------------------------------------------
# 5. แสดงผลปุ่มซิงก์ปฏิทินที่ Sidebar หากเพิ่งบันทึกงาน
# ----------------------------------------------------
if "last_saved_tasks" in st.session_state:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 เพิ่มงานล่าสุดลงปฏิทิน")
    last_info = st.session_state["last_saved_tasks"]
    
    for t_item in last_info["tasks"]:
        st.sidebar.caption(f"📌 {t_item['Task_Name']} ({t_item['Date']})")
        col_cal1, col_cal2 = st.sidebar.columns(2)
        
        with col_cal1:
            gcal_link = generate_google_calendar_url(
                t_item["Task_Name"], t_item["Date"], last_info["start_time"], last_info["end_time"], last_info["details"]
            )
            st.markdown(f'<a href="{gcal_link}" target="_blank"><button style="width:100%; border:none; border-radius:6px; background:#4285F4; color:white; padding:6px 0; font-size:12px; cursor:pointer;">Google Cal</button></a>', unsafe_allow_html=True)
            
        with col_cal2:
            ics_content = create_ics_file(
                t_item["Task_Name"], t_item["Date"], last_info["start_time"], last_info["end_time"], last_info["details"]
            )
            st.download_button(
                label="โหลด .ics",
                data=ics_content,
                file_name=f"{t_item['Task_Name']}.ics",
                mime="text/calendar",
                key=f"sidebar_ics_{t_item['Task_ID']}",
                use_container_width=True
            )

# ----------------------------------------------------
# 6. หน้าจอหลัก (Dashboard & Data View)
# ----------------------------------------------------
st.title("📋 Daily Work Log Tracker")

df = load_data()

if df.empty:
    st.info("ยังไม่มีข้อมูลงานในระบบ กรุณากรอกแบบฟอร์มด้านซ้ายเพื่อเริ่มต้นใช้งาน")
    st.stop()

# --- แถบตัวกรอง ---
with st.expander("🔍 ตัวกรองและค้นหาข้อมูล", expanded=True):
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_query = st.text_input("ค้นหาชื่องานหรือรายละเอียด", placeholder="พิมพ์คำค้นหา...")
    with col_f2:
        category_options = ["ทั้งหมด"] + sorted(list(df["Category"].dropna().unique()))
        selected_category = st.selectbox("กรองตามหมวดหมู่", category_options)
    with col_f3:
        df["YearMonth"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m")
        available_months = sorted(list(df["YearMonth"].unique()), reverse=True)
        selected_month = st.selectbox("เลือกเดือนสรุปผล", available_months)

filtered_df = df.copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df["Task_Name"].str.contains(search_query, case=False, na=False) |
        filtered_df["Details"].str.contains(search_query, case=False, na=False)
    ]
if selected_category != "ทั้งหมด":
    filtered_df = filtered_df[filtered_df["Category"] == selected_category]

# --- สรุปรายเดือน ---
month_df = df[df["YearMonth"] == selected_month]
total_month_tasks = len(month_df)
top_category = month_df["Category"].mode()[0] if not month_df.empty and not month_df["Category"].empty else "-"

st.markdown(f"#### 📊 ภาพรวมประจำเดือน ({selected_month})")
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("จำนวนงานทั้งหมด", f"{total_month_tasks} รายการ")
col_m2.metric("หมวดหมู่งานสูงสุด", top_category)
col_m3.metric("รายการที่ผ่านการกรอง", f"{len(filtered_df)} รายการ")

with col_m4:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ตัดข้อมูลรูปภาพ Base64 ออกจากคอลัมน์ Excel เพื่อไม่ให้ไฟล์หนักเกินไป
        export_df = filtered_df.drop(columns=["YearMonth"], errors="ignore").copy()
        export_df["Attachment_URL"] = export_df["Attachment_URL"].apply(lambda x: "[รูปภาพแนบในระบบ]" if str(x).startswith("data:image") else x)
        export_df.to_excel(writer, index=False, sheet_name="Work_Logs")
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 Export Excel (.xlsx)",
        data=excel_data,
        file_name=f"Work_Log_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

st.markdown("---")

# ----------------------------------------------------
# 7. แท็บแสดงผล: รายการตามวัน vs ปฏิทิน
# ----------------------------------------------------
tab_list, tab_calendar = st.tabs(["📝 รายการตามวัน (Daily List)", "📆 ปฏิทินรายเดือน (Calendar)"])

# === Tab 1: รายการตามวัน ===
with tab_list:
    if filtered_df.empty:
        st.write("ไม่พบรายการที่ตรงกับเงื่อนไขการค้นหา")
    else:
        sorted_dates = sorted(filtered_df["Date"].unique(), reverse=True)
        for date_entry in sorted_dates:
            day_tasks = filtered_df[filtered_df["Date"] == date_entry]
            today_label = " (วันนี้)" if date_entry == datetime.now().date() else ""
            st.markdown(f"##### 🗓️ {date_entry.strftime('%d/%m/%Y')}{today_label}")
            
            for _, row in day_tasks.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([1.5, 5, 2.5])
                    with c1:
                        st.caption(f"⏰ {row['Start_Time']} - {row['End_Time']}")
                        st.markdown(f"`{row['Category']}`")
                    with c2:
                        st.markdown(f"**{row['Task_Name']}**")
                        if row["Details"]:
                            st.write(row["Details"])
                        
                        # ตรวจสอบว่าไฟล์แนบเป็นรูปภาพ Base64 หรือเป็น URL ทั่วไป
                        attach = str(row["Attachment_URL"])
                        if attach.startswith("data:image"):
                            st.image(attach, caption="รูปภาพแนบ", width=250)
                        elif attach.startswith("http"):
                            st.markdown(f"📎 [เปิดไฟล์แนบ/เอกสาร]({attach})")
                            
                    with c3:
                        # ปุ่มปฏิทินของแต่ละรายการ
                        s_time = datetime.strptime(str(row['Start_Time']), "%H:%M").time()
                        e_time = datetime.strptime(str(row['End_Time']), "%H:%M").time()
                        
                        g_url = generate_google_calendar_url(row['Task_Name'], row['Date'], s_time, e_time, str(row['Details']))
                        st.markdown(f'<a href="{g_url}" target="_blank" style="text-decoration:none;"><button style="font-size:12px; padding:4px 10px; border:1px solid #4285F4; border-radius:4px; background:white; color:#4285F4; margin-bottom:4px; width:100px;">Google Cal</button></a>', unsafe_allow_html=True)
                        
                        item_ics = create_ics_file(row['Task_Name'], row['Date'], s_time, e_time, str(row['Details']))
                        st.download_button(
                            label="โหลด .ics",
                            data=item_ics,
                            file_name=f"{row['Task_Name']}.ics",
                            mime="text/calendar",
                            key=f"ics_list_{row['Task_ID']}"
                        )
                    st.divider()

# === Tab 2: ปฏิทินรายเดือน ===
with tab_calendar:
    calendar_events = []
    for _, row in df.iterrows():
        try:
            start_iso = f"{row['Date']}T{row['Start_Time']}:00"
            end_iso = f"{row['Date']}T{row['End_Time']}:00"
            
            calendar_events.append({
                "title": f"[{row['Category']}] {row['Task_Name']}",
                "start": start_iso,
                "end": end_iso,
                "extendedProps": {
                    "details": row["Details"]
                }
            })
        except Exception:
            continue

    calendar_options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,listMonth"
        },
        "initialView": "dayGridMonth",
        "selectable": True,
        "editable": False
    }

    calendar(events=calendar_events, options=calendar_options, key="monthly_work_calendar")
