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
import calendar as py_cal
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
# 4. ส่วน Sidebar: ฟอร์มบันทึกงานใหม่ (แบบ Agoda Style)
# ----------------------------------------------------
st.sidebar.title("✍️ บันทึกงานใหม่")

with st.sidebar.form("task_form", clear_on_submit=False):
    task_name = st.text_input("ชื่องาน / กิจกรรม *", placeholder="เช่น ประชุมวิชาการ...")
    
    category = st.selectbox(
        "หมวดหมู่", 
        ["ประชุม/ประสานงาน", "งานเอกสาร/สารบรรณ", "วิเคราะห์ข้อมูล/สถิติ", "พัฒนาระบบ/ไอที", "อื่นๆ"]
    )
    
    # กล่องเลือกวันที่แบบ Agoda: ให้ค่าเริ่มต้นเป็นช่วงวัน (วันนี้ ถึง วันนี้)
    # หากต้องการวันเดียว: คลิกวันเดิมซ้ำ
    # หากต้องการหลายวัน: คลิกวันเริ่ม แล้วคลิกวันสิ้นสุด
    selected_dates = st.date_input(
        "เลือกวันที่ปฏิบัติงาน (คลิกเลือกวันเริ่ม - วันสิ้นสุด)",
        value=(datetime.now().date(), datetime.now().date()),
        help="ถ้าเป็นงานวันเดียว ให้กดเลือกวันที่เดียวกันซ้ำ 2 ครั้ง หรือเลือกช่วงวันสำหรับงานหลายวันติดต่อกัน"
    )
    
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
    # ตรวจสอบว่าผู้ใช้เลือกวันที่ครบช่วงหรือไม่
    is_valid_date = False
    start_d = None
    end_d = None
    
    if isinstance(selected_dates, (list, tuple)):
        if len(selected_dates) == 2:
            start_d, end_d = selected_dates
            is_valid_date = True
        elif len(selected_dates) == 1:
            start_d = end_d = selected_dates[0]
            is_valid_date = True
    elif isinstance(selected_dates, date):
        start_d = end_d = selected_dates
        is_valid_date = True

    if not task_name:
        st.sidebar.error("กรุณาระบุชื่องาน")
    elif not is_valid_date:
        st.sidebar.error("กรุณาคลิกเลือกวันที่ให้ครบถ้วน (วันเริ่มและวันสิ้นสุด)")
    elif start_time >= end_time:
        st.sidebar.error("เวลาเริ่มต้นต้องเกิดขึ้นก่อนเวลาสิ้นสุด")
    else:
        days_count = (end_d - start_d).days + 1
        
        # แปลงรูปภาพ Base64
        final_attachment = attachment_url
        if uploaded_file is not None:
            image_data = convert_image_to_base64(uploaded_file)
            final_attachment = image_data

        tasks_to_create = []
        base_timestamp = int(datetime.now().timestamp())
        
        for i in range(days_count):
            curr_date = start_d + timedelta(days=i)
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
            st.sidebar.success(f"✅ บันทึกสำเร็จทั้งหมด {days_count} วัน!")

# ----------------------------------------------------
# 5. แสดงผลปุ่มซิงก์ปฏิทินที่ Sidebar หลังบันทึก
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
                        
                        attach = str(row["Attachment_URL"])
                        if attach.startswith("data:image"):
                            st.image(attach, caption="รูปภาพแนบ", width=250)
                        elif attach.startswith("http"):
                            st.markdown(f"📎 [เปิดไฟล์แนบ/เอกสาร]({attach})")
                            
                    with c3:
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

# === Tab 2: ปฏิทินรายเดือน (iOS Widget Style) ===
# === Tab 2: ปฏิทินรายเดือน (iOS Widget Style - แก้ไข HTML Render) ===
with tab_calendar:
    today_dt = datetime.now().date()
    curr_year, curr_month = map(int, selected_month.split("-"))
    thai_months_short = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", 
                         "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    
    # ------------------------------------------------
    # 1. การ์ด Progress สรุปภาพรวมประจำปี
    # ------------------------------------------------
    start_of_year = date(today_dt.year, 1, 1)
    end_of_year = date(today_dt.year, 12, 31)
    days_in_year = (end_of_year - start_of_year).days + 1
    days_passed = (today_dt - start_of_year).days + 1
    days_left = days_in_year - days_passed
    year_percent = int((days_passed / days_in_year) * 100)
    year_buddhist = today_dt.year + 543
    
    month_tasks = df[df["YearMonth"] == selected_month].copy()
    total_month_items = len(month_tasks)

    progress_html = (
        f'<div style="background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(16px); '
        f'border: 1px solid #E2E8F0; border-radius: 20px; padding: 18px 24px; '
        f'box-shadow: 0 8px 25px rgba(0, 0, 0, 0.05); margin-bottom: 16px;">'
        f'<div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px;">'
        f'<span style="font-size: 22px; font-weight: 700; color: #1E293B;">{year_buddhist}</span>'
        f'<span style="font-size: 22px; font-weight: 700; color: #4338CA;">{year_percent}%</span>'
        f'</div>'
        f'<div style="background: #E2E8F0; border-radius: 999px; height: 7px; width: 100%; overflow: hidden; margin-bottom: 8px;">'
        f'<div style="background: linear-gradient(90deg, #6366F1 0%, #4F46E5 100%); width: {year_percent}%; height: 100%; border-radius: 999px;"></div>'
        f'</div>'
        f'<div style="display: flex; justify-content: space-between; font-size: 12px; color: #64748B;">'
        f'<span>ผ่านไปแล้ว {year_percent}% ของปี</span>'
        f'<span>เหลืออีก {days_left} วัน</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(progress_html, unsafe_allow_html=True)

    # ------------------------------------------------
    # 2. การ์ดปฏิทิน Calendar Widget Grid
    # ------------------------------------------------
    cal_obj = py_cal.Calendar(firstweekday=0)
    month_matrix = cal_obj.monthdatescalendar(curr_year, curr_month)
    
    first_d = month_matrix[0][0]
    last_d = month_matrix[-1][-1]
    date_range_label = f"{first_d.day} {thai_months_short[first_d.month]} - {last_d.day} {thai_months_short[last_d.month]}"
    
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding: 0 4px;">'
        f'<span style="font-size: 16px; font-weight: 700; color: #1E293B;">{date_range_label}</span>'
        f'<span style="background: #4F46E5; color: white; border-radius: 50%; width: 22px; height: 22px; '
        f'display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600;">{total_month_items}</span>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)
    
    category_colors = {
        "ประชุม/ประสานงาน": {"bg": "#E0E7FF", "text": "#3730A3", "dot": "#6366F1"},
        "งานเอกสาร/สารบรรณ": {"bg": "#FEE2E2", "text": "#991B1B", "dot": "#EF4444"},
        "วิเคราะห์ข้อมูล/สถิติ": {"bg": "#FEF3C7", "text": "#92400E", "dot": "#F59E0B"},
        "พัฒนาระบบ/ไอที": {"bg": "#DCFCE7", "text": "#166534", "dot": "#10B981"},
        "อื่นๆ": {"bg": "#F1F5F9", "text": "#475569", "dot": "#94A3B8"}
    }
    
    days_short = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]
    h_cols = st.columns(7)
    for idx, d_name in enumerate(days_short):
        h_cols[idx].markdown(f"<div style='text-align: center; font-size: 12px; color: #94A3B8; font-weight: 600;'>{d_name}</div>", unsafe_allow_html=True)
        
    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
    
    for week_dates in month_matrix:
        w_cols = st.columns(7)
        for c_idx, cell_date in enumerate(week_dates):
            with w_cols[c_idx]:
                is_curr_month = (cell_date.month == curr_month)
                is_today = (cell_date == today_dt)
                
                day_num_str = str(cell_date.day)
                text_color = "#1E293B" if is_curr_month else "#CBD5E1"
                
                if is_today:
                    day_badge = (
                        f'<div style="background: #4F46E5; color: white; width: 24px; height: 24px; border-radius: 50%; '
                        f'display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; margin-bottom: 4px;">'
                        f'{day_num_str}</div>'
                    )
                else:
                    day_badge = (
                        f'<div style="font-size: 13px; font-weight: 600; color: {text_color}; margin-bottom: 4px; padding-left: 2px;">'
                        f'{day_num_str}</div>'
                    )
                
                matched_tasks = df[df["Date"] == cell_date]
                tasks_html = ""
                
                for _, t_row in matched_tasks.iterrows():
                    c_info = category_colors.get(t_row.get("Category", "อื่นๆ"), category_colors["อื่นๆ"])
                    task_title = str(t_row["Task_Name"])
                    short_title = (task_title[:9] + "...") if len(task_title) > 9 else task_title
                    tasks_html += (
                        f'<div style="background: {c_info["bg"]}; color: {c_info["text"]}; font-size: 10px; padding: 2px 5px; '
                        f'border-radius: 4px; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; '
                        f'display: flex; align-items: center; gap: 4px;">'
                        f'<span style="display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: {c_info["dot"]}; flex-shrink: 0;"></span>'
                        f'<span>{short_title}</span></div>'
                    )
                
                cell_html = (
                    f'<div style="background: #FFFFFF; min-height: 85px; border-radius: 10px; padding: 6px; '
                    f'border: 1px solid #E2E8F0; margin-bottom: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">'
                    f'{day_badge}{tasks_html}</div>'
                )
                st.markdown(cell_html, unsafe_allow_html=True)
                
                if len(matched_tasks) > 0:
                    with st.popover(f"🔎 {len(matched_tasks)} งาน"):
                        st.caption(f"📅 รายละเอียดวันที่ {cell_date.strftime('%d/%m/%Y')}")
                        for _, m_row in matched_tasks.iterrows():
                            st.markdown(f"• **{m_row['Task_Name']}** (`{m_row['Category']}`)")
                            st.caption(f"เวลา: {m_row['Start_Time']} - {m_row['End_Time']}")
                            if m_row["Details"]:
                                st.write(m_row["Details"])
                            st.divider()
