import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from twilio.rest import Client
from datetime import datetime, timedelta
import json
import base64

DATE_FORMAT = "%d-%m-%Y"
COL_NAME          = "Name"
COL_PHONE         = "Phone"
COL_CASE          = "Case"
COL_PREV_DATE     = "Previous Date"
COL_NEXT_DATE     = "Next Date"
COL_REMINDER_SENT = "Reminder Sent"

# ── Professional Law Firm Styling ──────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+3:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Source Sans 3', sans-serif;
}

/* Background */
.stApp {
    background: linear-gradient(135deg, #0a0a0f 0%, #111827 50%, #0d1117 100%);
    min-height: 100vh;
}

/* Firm Header Banner */
.firm-header {
    background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-bottom: 2px solid #c9a84c;
    padding: 18px 32px;
    margin: -1rem -1rem 2rem -1rem;
    display: flex;
    align-items: center;
    gap: 16px;
}
.firm-name {
    font-family: 'Playfair Display', serif;
    font-size: 26px;
    font-weight: 700;
    color: #c9a84c;
    letter-spacing: 1px;
    margin: 0;
    line-height: 1.2;
}
.firm-subtitle {
    font-size: 12px;
    color: #8899aa;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin: 0;
}
.firm-logo {
    font-size: 36px;
    line-height: 1;
}

/* Page title */
h1 {
    font-family: 'Playfair Display', serif !important;
    color: #c9a84c !important;
    font-size: 28px !important;
    border-bottom: 1px solid #2a2a3e;
    padding-bottom: 12px;
}

h2, h3 {
    font-family: 'Playfair Display', serif !important;
    color: #e8d5a3 !important;
}

/* Cards */
.case-card {
    background: linear-gradient(135deg, #161625 0%, #1c1c2e 100%);
    border: 1px solid #2a2a4a;
    border-left: 3px solid #c9a84c;
    border-radius: 8px;
    padding: 20px 24px;
    margin: 12px 0;
}
.case-card-urgent {
    border-left: 3px solid #e05252;
}

/* Stat boxes */
.stat-box {
    background: linear-gradient(135deg, #161625, #1c1c2e);
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
}
.stat-number {
    font-family: 'Playfair Display', serif;
    font-size: 36px;
    color: #c9a84c;
    font-weight: 700;
}
.stat-label {
    font-size: 12px;
    color: #8899aa;
    text-transform: uppercase;
    letter-spacing: 2px;
}

/* Form inputs */
.stTextInput input, .stDateInput input {
    background: #1c1c2e !important;
    border: 1px solid #2a2a4a !important;
    color: #e8e8e8 !important;
    border-radius: 6px !important;
}
.stTextInput input:focus, .stDateInput input:focus {
    border-color: #c9a84c !important;
    box-shadow: 0 0 0 2px rgba(201,168,76,0.2) !important;
}

/* Buttons */
.stButton button {
    background: linear-gradient(135deg, #c9a84c, #a07830) !important;
    color: #0a0a0f !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    padding: 8px 20px !important;
    transition: all 0.2s !important;
}
.stButton button:hover {
    background: linear-gradient(135deg, #dbb85c, #b08840) !important;
    transform: translateY(-1px) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161625 100%) !important;
    border-right: 1px solid #2a2a4a !important;
}
section[data-testid="stSidebar"] .stRadio label {
    color: #c9a84c !important;
}

/* Success/Warning/Error */
.stSuccess {
    background: #0d2a1a !important;
    border-color: #1d6a3a !important;
}
.stWarning {
    background: #2a1a0d !important;
    border-color: #6a3a1d !important;
}

/* Divider */
hr {
    border-color: #2a2a4a !important;
}

/* Text colors */
p, li, label {
    color: #c8c8d8 !important;
}

.gold-badge {
    background: linear-gradient(135deg, #c9a84c, #a07830);
    color: #0a0a0f;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}
</style>

<div class="firm-header">
    <div class="firm-logo">⚖️</div>
    <div>
        <p class="firm-name">Advance Law Firm</p>
        <p class="firm-subtitle">Sopore Court &nbsp;|&nbsp; Legal Hearing Management System</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Connect to Google Sheets ────────────────────────────
def connect_to_sheet():
    try:
        creds_b64  = st.secrets["GOOGLE_CREDENTIALS_B64"]
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds     = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client    = gspread.authorize(creds)
        sheet     = client.open(st.secrets["SHEET_NAME"])
        worksheet = sheet.worksheet(st.secrets["WORKSHEET_NAME"])
        return worksheet
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None


# ── Send WhatsApp ───────────────────────────────────────
def send_whatsapp(phone, name, case, next_date):
    try:
        client = Client(
            st.secrets["TWILIO_ACCOUNT_SID"],
            st.secrets["TWILIO_AUTH_TOKEN"]
        )
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        body = (
            f"Hello {name},\n\n"
            f"Reminder: Your court hearing for {case} is on {next_date}.\n"
            f"Please be present.\n\n"
            f"- Advance Law Firm, Sopore"
        )
        msg = client.messages.create(
            from_=st.secrets["TWILIO_FROM_NUMBER"],
            to=f"whatsapp:{phone}",
            body=body
        )
        return True, msg.sid
    except Exception as e:
        return False, str(e)


# ── Mark Reminder Sent ──────────────────────────────────
def mark_sent(worksheet, case_no):
    try:
        headers  = worksheet.row_values(1)
        all_rows = worksheet.get_all_values()
        col_idx  = headers.index(COL_REMINDER_SENT) + 1
        for i, row in enumerate(all_rows):
            if len(row) > 2 and row[2] == case_no:
                worksheet.update_cell(i + 1, col_idx, "YES")
                return True
    except Exception as e:
        st.error(f"Sheet update failed: {e}")
    return False


# ── Sidebar Navigation ──────────────────────────────────
st.sidebar.markdown("### ⚖️ Navigation")
page = st.sidebar.radio(
    "",
    ["📊 Dashboard", "➕ Add Client", "🔍 Search & Remind"]
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small style='color:#556677'>Advance Law Firm<br>Sopore Court<br>Legal Management v2.0</small>",
    unsafe_allow_html=True
)

worksheet = connect_to_sheet()
if not worksheet:
    st.stop()


# ════════════════════════════════════════════════════════
#   DASHBOARD
# ════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("📊 Hearing Dashboard")

    today    = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)

    all_records    = worksheet.get_all_records()
    tomorrow_cases = []
    week_cases     = []
    total_active   = 0

    for record in all_records:
        date_str = str(record.get(COL_NEXT_DATE, "")).strip()
        if not date_str:
            continue
        try:
            hearing_date = datetime.strptime(date_str, DATE_FORMAT).date()
        except:
            continue
        total_active += 1
        if hearing_date == tomorrow:
            tomorrow_cases.append(record)
        elif today < hearing_date <= week_end:
            week_cases.append(record)

    # Stats row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{len(all_records)}</div>
            <div class="stat-label">Total Clients</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number" style="color:#e05252">{len(tomorrow_cases)}</div>
            <div class="stat-label">Tomorrow</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number" style="color:#52a0e0">{len(week_cases)}</div>
            <div class="stat-label">This Week</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tomorrow's hearings
    st.subheader(f"⚠️ Tomorrow's Hearings — {tomorrow.strftime(DATE_FORMAT)}")
    if not tomorrow_cases:
        st.success("✅ No hearings scheduled for tomorrow.")
    else:
        for record in tomorrow_cases:
            reminder = str(record.get(COL_REMINDER_SENT, "NO")).upper()
            st.markdown(f"""
            <div class="case-card case-card-urgent">
                <strong style="color:#e8d5a3;font-size:16px">👤 {record.get(COL_NAME)}</strong>
                &nbsp;&nbsp;<span class="gold-badge">{record.get(COL_CASE)}</span><br>
                <span style="color:#8899aa;font-size:13px">📱 {record.get(COL_PHONE)} &nbsp;|&nbsp; 📅 {record.get(COL_NEXT_DATE)}</span>
            </div>""", unsafe_allow_html=True)

            if reminder == "YES":
                st.success("✅ Reminder already sent")
            else:
                if st.button(f"📲 Send WhatsApp to {record.get(COL_NAME)}", key=f"t_{record.get(COL_CASE)}"):
                    with st.spinner("Sending WhatsApp reminder..."):
                        ok, result = send_whatsapp(
                            record.get(COL_PHONE), record.get(COL_NAME),
                            record.get(COL_CASE),  record.get(COL_NEXT_DATE)
                        )
                    if ok:
                        mark_sent(worksheet, record.get(COL_CASE))
                        st.success(f"✅ Reminder sent to {record.get(COL_NAME)}!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed: {result}")

    st.markdown("---")

    # This week
    st.subheader("📆 Upcoming This Week")
    if not week_cases:
        st.info("No other hearings scheduled this week.")
    else:
        for record in week_cases:
            st.markdown(f"""
            <div class="case-card">
                <strong style="color:#e8d5a3">{record.get(COL_NAME)}</strong>
                &nbsp;&nbsp;<span class="gold-badge">{record.get(COL_CASE)}</span><br>
                <span style="color:#8899aa;font-size:13px">📅 {record.get(COL_NEXT_DATE)} &nbsp;|&nbsp; 📱 {record.get(COL_PHONE)}</span>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#   ADD CLIENT
# ════════════════════════════════════════════════════════
elif page == "➕ Add Client":
    st.title("➕ Add New Client")
    st.markdown("Register a new client's hearing details below.")

    with st.form("add_client_form", clear_on_submit=True):
        name      = st.text_input("👤 Client Full Name *")
        phone     = st.text_input("📱 Phone Number *", placeholder="919876543210 (without +)")
        case      = st.text_input("📁 Case Number *", placeholder="CRL/001/2025")
        col1, col2 = st.columns(2)
        with col1:
            prev_date = st.date_input("📅 Previous Hearing Date")
        with col2:
            next_date = st.date_input("📅 Next Hearing Date")

        submitted = st.form_submit_button("💾 Save Client Record")

    if submitted:
        if not name or not phone or not case:
            st.error("⚠️ Please fill all required fields marked with *")
        else:
            all_records    = worksheet.get_all_records()
            dup_phone = any(
                str(r.get(COL_PHONE, "")).replace(" ","") == phone.replace(" ","")
                for r in all_records
            )
            dup_case  = any(
                str(r.get(COL_CASE, "")).strip().lower() == case.strip().lower()
                for r in all_records
            )
            if dup_phone:
                st.warning(f"⚠️ Phone number already exists in records!")
            elif dup_case:
                st.warning(f"⚠️ Case number {case} already exists in records!")
            else:
                try:
                    worksheet.append_row([
                        name, phone, case,
                        prev_date.strftime(DATE_FORMAT),
                        next_date.strftime(DATE_FORMAT),
                        "NO"
                    ])
                    st.success(f"✅ Client **{name}** added successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Failed to save: {e}")


# ════════════════════════════════════════════════════════
#   SEARCH & REMIND
# ════════════════════════════════════════════════════════
elif page == "🔍 Search & Remind":
    st.title("🔍 Search Client")
    st.markdown("Search by phone number or case number to find client details.")

    search_type  = st.radio("Search by:", ["📱 Phone Number", "📁 Case Number"], horizontal=True)
    search_query = st.text_input("Enter search value:")

    if search_query:
        all_records = worksheet.get_all_records()
        results     = []

        for idx, record in enumerate(all_records):
            if "Phone" in search_type:
                val = str(record.get(COL_PHONE, "")).replace(" ", "")
                if search_query.replace(" ", "") in val:
                    results.append((idx, record))
            else:
                val = str(record.get(COL_CASE, "")).strip().lower()
                if search_query.strip().lower() in val:
                    results.append((idx, record))

        if not results:
            st.warning("⚠️ No clients found matching your search.")
        else:
            st.markdown(f"**Found {len(results)} record(s):**")
            for idx, record in results:
                reminder = str(record.get(COL_REMINDER_SENT, "NO")).upper()
                st.markdown(f"""
                <div class="case-card">
                    <strong style="color:#e8d5a3;font-size:17px">👤 {record.get(COL_NAME)}</strong>
                    &nbsp;&nbsp;<span class="gold-badge">{record.get(COL_CASE)}</span><br><br>
                    <span style="color:#8899aa">📱 {record.get(COL_PHONE)}</span><br>
                    <span style="color:#8899aa">📅 Previous: {record.get(COL_PREV_DATE)}</span><br>
                    <span style="color:#c9a84c">📅 Next Hearing: <strong>{record.get(COL_NEXT_DATE)}</strong></span><br>
                    <span style="color:#8899aa">Reminder Sent: {'✅ YES' if reminder == 'YES' else '⏳ NO'}</span>
                </div>""", unsafe_allow_html=True)

                if st.button(f"📲 Send Reminder to {record.get(COL_NAME)}", key=f"s_{idx}"):
                    with st.spinner("Sending WhatsApp reminder..."):
                        ok, result = send_whatsapp(
                            record.get(COL_PHONE), record.get(COL_NAME),
                            record.get(COL_CASE),  record.get(COL_NEXT_DATE)
                        )
                    if ok:
                        mark_sent(worksheet, record.get(COL_CASE))
                        st.success(f"✅ Reminder sent to {record.get(COL_NAME)}!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed: {result}")
