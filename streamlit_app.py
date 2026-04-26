import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from twilio.rest import Client
from datetime import datetime
import json
import base64
import os

# ─────────────────────────────────────────────
#   CONFIGURATION
# ─────────────────────────────────────────────
DATE_FORMAT = "%d-%m-%Y"

COL_NAME          = "Name"
COL_PHONE         = "Phone"
COL_CASE          = "Case"
COL_PREV_DATE     = "Previous Date"
COL_NEXT_DATE     = "Next Date"
COL_REMINDER_SENT = "Reminder Sent"

# ─────────────────────────────────────────────
#   GOOGLE SHEETS CONNECTION
# ─────────────────────────────────────────────
def connect_to_sheet():
    try:
        creds_b64 = st.secrets["GOOGLE_CREDENTIALS_B64"]
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["SHEET_NAME"])
        worksheet = sheet.worksheet(st.secrets["WORKSHEET_NAME"])
        return worksheet
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

# ─────────────────────────────────────────────
#   SEND WHATSAPP
# ─────────────────────────────────────────────
def send_whatsapp(phone, name, case, next_date):
    try:
        client = Client(
            st.secrets["TWILIO_ACCOUNT_SID"],
            st.secrets["TWILIO_AUTH_TOKEN"]
        )
        # Auto add + if missing
        if not phone.startswith("+"):
            phone = "+" + phone

        message_body = (
            f"Hello {name},\n\n"
            f"Reminder: Your court hearing for {case} is on {next_date}.\n"
            f"Please be present.\n\n"
            f"- Your Lawyer"
        )
        message = client.messages.create(
            from_=st.secrets["TWILIO_FROM_NUMBER"],
            to=f"whatsapp:{phone}",
            body=message_body
        )
        return True, message.sid
    except Exception as e:
        return False, str(e)

# ─────────────────────────────────────────────
#   PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Court Reminder System",
    page_icon="⚖️",
    layout="centered"
)

st.title("⚖️ Court Hearing Reminder System")
st.markdown("---")

# ─────────────────────────────────────────────
#   NAVIGATION
# ─────────────────────────────────────────────
page = st.sidebar.radio(
    "Navigation",
    ["➕ Add Client", "🔍 Search & Remind"]
)

worksheet = connect_to_sheet()
if not worksheet:
    st.stop()

# ─────────────────────────────────────────────
#   PAGE 1 — ADD CLIENT
# ─────────────────────────────────────────────
if page == "➕ Add Client":
    st.header("➕ Add New Client")
    st.markdown("Fill in the details below to add a new client.")

    with st.form("add_client_form"):
        name      = st.text_input("Client Name *")
        phone     = st.text_input("Phone Number *", placeholder="919876543210")
        case      = st.text_input("Case Number *", placeholder="CRL/001/2025")
        prev_date = st.date_input("Previous Hearing Date")
        next_date = st.date_input("Next Hearing Date")

        submitted = st.form_submit_button("💾 Save Client")

    if submitted:
        # Validate required fields
        if not name or not phone or not case:
            st.error("Please fill in all required fields marked with *")
        else:
            # Check for duplicates
            all_records = worksheet.get_all_records()
            duplicate_phone = any(
                str(r.get(COL_PHONE, "")).replace(" ", "") == phone.replace(" ", "")
                for r in all_records
            )
            duplicate_case = any(
                str(r.get(COL_CASE, "")).strip().lower() == case.strip().lower()
                for r in all_records
            )

            if duplicate_phone:
                st.warning(f"⚠️ Phone number {phone} already exists in the sheet!")
            elif duplicate_case:
                st.warning(f"⚠️ Case number {case} already exists in the sheet!")
            else:
                # Save to Google Sheet
                try:
                    worksheet.append_row([
                        name,
                        phone,
                        case,
                        prev_date.strftime(DATE_FORMAT),
                        next_date.strftime(DATE_FORMAT),
                        "NO"
                    ])
                    st.success(f"✅ Client **{name}** added successfully!")
                except Exception as e:
                    st.error(f"Failed to save: {e}")

# ─────────────────────────────────────────────
#   PAGE 2 — SEARCH & REMIND
# ─────────────────────────────────────────────
elif page == "🔍 Search & Remind":
    st.header("🔍 Search Client")
    st.markdown("Search by phone number or case number.")

    search_type = st.radio("Search by:", ["Phone Number", "Case Number"], horizontal=True)
    search_query = st.text_input("Enter search value:")

    if search_query:
        all_records = worksheet.get_all_records()
        results = []

        for idx, record in enumerate(all_records):
            if search_type == "Phone Number":
                value = str(record.get(COL_PHONE, "")).replace(" ", "")
                query = search_query.replace(" ", "")
                if query in value:
                    results.append((idx, record))
            else:
                value = str(record.get(COL_CASE, "")).strip().lower()
                if search_query.strip().lower() in value:
                    results.append((idx, record))

        if not results:
            st.warning("No clients found matching your search.")
        else:
            for idx, record in results:
                st.markdown("---")
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"**👤 Name:** {record.get(COL_NAME)}")
                    st.markdown(f"**📱 Phone:** {record.get(COL_PHONE)}")
                    st.markdown(f"**📁 Case:** {record.get(COL_CASE)}")

                with col2:
                    st.markdown(f"**📅 Previous Date:** {record.get(COL_PREV_DATE)}")
                    st.markdown(f"**📅 Next Date:** {record.get(COL_NEXT_DATE)}")
                    reminder_status = record.get(COL_REMINDER_SENT, "NO")
                    if reminder_status == "YES":
                        st.markdown("**✅ Reminder Sent:** YES")
                    else:
                        st.markdown("**⏳ Reminder Sent:** NO")

                # Send Reminder Button
                if st.button(f"📲 Send Reminder to {record.get(COL_NAME)}", key=f"btn_{idx}"):
                    phone = str(record.get(COL_PHONE, ""))
                    name  = str(record.get(COL_NAME, ""))
                    case  = str(record.get(COL_CASE, ""))
                    next_date = str(record.get(COL_NEXT_DATE, ""))

                    with st.spinner("Sending WhatsApp message..."):
                        success, result = send_whatsapp(phone, name, case, next_date)

                    if success:
                        st.success(f"✅ Reminder sent to {name}!")
                        # Update sheet
                        headers = worksheet.row_values(1)
                        col_index = headers.index(COL_REMINDER_SENT) + 1
                        worksheet.update_cell(idx + 2, col_index, "YES")
                    else:
                        st.error(f"❌ Failed to send: {result}")
