import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, time, timedelta
import io
import urllib.parse
from icalendar import Calendar, Event
from streamlit_calendar import calendar

# ----------------------------------------------------
# 1. การตั้งค่าหน้าเว็บ (Minimal & Clean Theme)
# ----------------------------------------------------
st.set_page_config(
    page_title="Daily Work Log Tracker",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS เพื่อหน้าตาเรียบหรูและปุ่มที่สบายตา
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
# 2. ฟังก์ชันเชื่อมต่อ Google Sheets
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

def append_task(task_dict):
    try:
        sheet = init_gsheet_connection()
        row = [
            task_dict["Task_ID"],
            str(task_dict["Date"]),
            task_dict["Start_Time"],
            task_dict["End_Time"],
            task_dict["Task_Name"],
            task_dict["Category"],
            task_dict["Details"],
            task_dict["Attachment_URL"],
            task_dict["Created_At"]
        ]
        sheet.append_row(row)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"ไม่สามารถบันทึกลง Google Sheets ได้: {e}")
        return False

# ----------------------------------------------------
# 3. ฟังก์ชันสร้างลิงก์และไฟล์ปฏิทิน
# ----------------------------------------------------
def generate_google_calendar_url(title, date_val, start_t, end_t, details):
    start_dt = datetime.combine(date_val, start_t)
    end_dt = datetime.combine(date_val, end_t)
    
    # รูปแบบ YYYYMMDDTHHMMSS
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

# ----------------------------------------------------
# 4. ส่วน Sidebar: ฟอร์มบันทึกงานใหม่
# ----------------------------------------------------
st.sidebar.title("✍️ บันทึกงานใหม่")

with st.sidebar.form("task_form", clear_on_submit=True):
    task_name = st.text_input("ชื่องาน *", placeholder="เช่น จัดทำรายงานสถิติประจำเดือน")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        task_date = st.date_input("วันที่ปฏิบัติงาน", datetime.now().date())
    with col_d2:
        category = st.selectbox(
            "หมวดหมู่", 
            ["งานเอกสาร/สารบรรณ", "วิเคราะห์ข้อมูล/สถิติ", "พัฒนาระบบ/ไอที", "ประชุม/ประสานงาน", "อื่นๆ"]
        )
        
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.time_input("เวลาเริ่ม", time(9, 0))
    with col_t2:
        end_time = st.time_input("เวลาสิ้นสุด", time(12, 0))
        
    details = st.text_area("รายละเอียดงาน", placeholder="สรุปเนื้อหา ขั้นตอน หรือบันทึกข้อความ...")
    attachment_url = st.text_input("ลิงก์ไฟล์แนบ (Google Drive / ลิงก์เอกสาร)", placeholder="https://drive.google.com/...")
    
    submit_btn = st.form_submit_button("💾 บันทึกลง Google Sheets", use_container_width=True)

if submit_btn:
    if not task_name:
        st.sidebar.error("กรุณาระบุชื่องาน")
    elif start_time >= end_time:
        st.sidebar.error("เวลาเริ่มต้นต้องเกิดขึ้นก่อนเวลาสิ้นสุด")
    else:
        new_task = {
            "Task_ID": f"TSK-{int(datetime.now().timestamp())}",
            "Date": task_date,
            "Start_Time": start_time.strftime("%H:%M"),
            "End_Time": end_time.strftime("%H:%M"),
            "Task_Name": task_name,
            "Category": category,
            "Details": details,
            "Attachment_URL": attachment_url,
            "Created_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        success = append_task(new_task)
        if success:
            st.sidebar.success("✅ บันทึกข้อมูลสำเร็จ!")
            
            # สร้างตัวเลือกสำหรับซิงก์เข้า Calendar ทันทีหลังบันทึก
            st.sidebar.markdown("---")
            st.sidebar.markdown("**📅 ซิงก์งานนี้เข้าปฏิทินทันที:**")
            
            # ลิงก์ Google Calendar
            gcal_url = generate_google_calendar_url(task_name, task_date, start_time, end_time, details)
            st.sidebar.markdown(f'<a href="{gcal_url}" target="_blank"><button style="width:100%; border:none; border-radius:6px; background:#4285F4; color:white; padding:8px; cursor:pointer;">➕ ลง Google Calendar</button></a>', unsafe_allow_html=True)
            
            # ดาวน์โหลด .ics ลงเครื่อง
            ics_data = create_ics_file(task_name, task_date, start_time, end_time, details)
            st.sidebar.download_button(
                label="📥 โหลดไฟล์ .ics ลงปฏิทินเครื่อง (Apple/Windows)",
                data=ics_data,
                file_name=f"{task_name}.ics",
                mime="text/calendar",
                use_container_width=True
            )

# ----------------------------------------------------
# 5. โครงสร้างหน้าจอหลัก (Main Dashboard)
# ----------------------------------------------------
st.title("📋 Daily Work Log Tracker")

df = load_data()

if df.empty:
    st.info("ยังไม่มีข้อมูลงานในระบบ กรุณากรอกแบบฟอร์มด้านซ้ายเพื่อเริ่มต้นใช้งาน")
    st.stop()

# --- แถบตัวกรอง (Filters) ---
with st.expander("🔍 ตัวกรองและค้นหาข้อมูล", expanded=True):
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_query = st.text_input("ค้นหาชื่องานหรือรายละเอียด", placeholder="พิมพ์คำค้นหา...")
    with col_f2:
        category_options = ["ทั้งหมด"] + sorted(list(df["Category"].dropna().unique()))
        selected_category = st.selectbox("กรองตามหมวดหมู่", category_options)
    with col_f3:
        # กำหนดเดือนสำหรับ Dashboard
        df["YearMonth"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m")
        available_months = sorted(list(df["YearMonth"].unique()), reverse=True)
        selected_month = st.selectbox("เลือกเดือนที่ต้องการสรุปผล", available_months)

# ประมวลผลข้อมูลตามตัวกรอง
filtered_df = df.copy()

if search_query:
    filtered_df = filtered_df[
        filtered_df["Task_Name"].str.contains(search_query, case=False, na=False) |
        filtered_df["Details"].str.contains(search_query, case=False, na=False)
    ]
if selected_category != "ทั้งหมด":
    filtered_df = filtered_df[filtered_df["Category"] == selected_category]

# --- สรุปภาพรวมรายเดือน (Monthly Summary) ---
month_df = df[df["YearMonth"] == selected_month]
total_month_tasks = len(month_df)
top_category = month_df["Category"].mode()[0] if not month_df.empty and not month_df["Category"].empty else "-"

st.markdown(f"#### 📊 ภาพรวมประจำเดือน ({selected_month})")
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("จำนวนงานทั้งหมด", f"{total_month_tasks} รายการ")
col_m2.metric("หมวดหมู่งานสูงสุด", top_category)
col_m3.metric("รายการที่ผ่านการกรอง", f"{len(filtered_df)} รายการ")

# ปุ่ม Export Excel
with col_m4:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        filtered_df.drop(columns=["YearMonth"], errors="ignore").to_excel(writer, index=False, sheet_name="Work_Logs")
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
# 6. มุมมองการแสดงผล (Tabs: รายการตามวัน vs ปฏิทิน)
# ----------------------------------------------------
tab_list, tab_calendar = st.tabs(["📝 รายการตามวัน (Daily List)", "📆 ปฏิทินรายเดือน (Calendar)"])

# === Tab 1: รายการตามวัน ===
with tab_list:
    if filtered_df.empty:
        st.write("ไม่พบรายการที่ตรงกับเงื่อนไขการค้นหา")
    else:
        # จัดกลุ่มแสดงผลตามวันที่
        sorted_dates = sorted(filtered_df["Date"].unique(), reverse=True)
        for date_entry in sorted_dates:
            day_tasks = filtered_df[filtered_df["Date"] == date_entry]
            
            # Badge วันที่
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
                        if row["Attachment_URL"]:
                            st.markdown(f"📎 [เปิดไฟล์แนบ/เอกสาร]({row['Attachment_URL']})")
                    with c3:
                        # ปุ่มกดซิงก์ปฏิทินย้อนหลังรายไอเทม
                        s_time = datetime.strptime(row['Start_Time'], "%H:%M").time()
                        e_time = datetime.strptime(row['End_Time'], "%H:%M").time()
                        
                        g_url = generate_google_calendar_url(row['Task_Name'], row['Date'], s_time, e_time, str(row['Details']))
                        st.markdown(f'<a href="{g_url}" target="_blank" style="text-decoration:none;"><button style="font-size:12px; padding:3px 8px; border:1px solid #4285F4; border-radius:4px; background:white; color:#4285F4; margin-bottom:4px;">Google Cal</button></a>', unsafe_allow_html=True)
                        
                        item_ics = create_ics_file(row['Task_Name'], row['Date'], s_time, e_time, str(row['Details']))
                        st.download_button(
                            label="โหลด .ics",
                            data=item_ics,
                            file_name=f"{row['Task_Name']}.ics",
                            mime="text/calendar",
                            key=f"ics_{row['Task_ID']}"
                        )
                    st.divider()

# === Tab 2: ปฏิทินรายเดือน ===
with tab_calendar:
    calendar_events = []
    
    # แปลงข้อมูลใน DataFrame ให้ตรงกับ Format ของ FullCalendar
    for _, row in df.iterrows():
        try:
            start_iso = f"{row['Date']}T{row['Start_Time']}:00"
            end_iso = f"{row['Date']}T{row['End_Time']}:00"
            
            calendar_events.append({
                "title": f"[{row['Category']}] {row['Task_Name']}",
                "start": start_iso,
                "end": end_iso,
                "extendedProps": {
                    "details": row["Details"],
                    "attachment": row["Attachment_URL"]
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