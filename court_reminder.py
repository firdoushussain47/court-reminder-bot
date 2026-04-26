import gspread
from google.oauth2.service_account import Credentials
from twilio.rest import Client
from datetime import datetime, timedelta
import sys
import os
import json
import base64

TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER  = os.environ.get("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")

SHEET_NAME          = os.environ.get("SHEET_NAME", "Court Reminders")
WORKSHEET_NAME      = os.environ.get("WORKSHEET_NAME", "Sheet1")
GOOGLE_CREDS_B64    = os.environ.get("GOOGLE_CREDENTIALS_B64")

DATE_FORMAT = "%d-%m-%Y"

COL_NAME          = "Name"
COL_PHONE         = "Phone"
COL_CASE          = "Case"
COL_NEXT_DATE     = "Next Date"
COL_REMINDER_SENT = "Reminder Sent"


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def connect_to_google_sheets():
    log("Connecting to Google Sheets...")
    if not GOOGLE_CREDS_B64:
        log("ERROR: GOOGLE_CREDENTIALS_B64 secret not set in GitHub.")
        return None
    try:
        creds_json = base64.b64decode(GOOGLE_CREDS_B64).decode("utf-8")
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open(SHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        log(f"Connected to: '{SHEET_NAME}' > '{WORKSHEET_NAME}'")
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        log(f"ERROR: Sheet '{SHEET_NAME}' not found.")
        return None
    except Exception as e:
        log(f"ERROR connecting to Google Sheets: {e}")
        return None


def get_twilio_client():
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        log("ERROR: Twilio credentials not set in GitHub Secrets.")
        return None
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        log("Twilio client initialized.")
        return client
    except Exception as e:
        log(f"ERROR initializing Twilio: {e}")
        return None


def send_whatsapp_message(twilio_client, phone, name, case, next_date_str, row_number):
    to_number = f"whatsapp:{phone}"
    message_body = (
        f"Hello {name},\n\n"
        f"Reminder: Your court hearing for {case} is on {next_date_str}.\n"
        f"Please be present.\n\n"
        f"- Your Lawyer"
    )
    try:
        message = twilio_client.messages.create(
            from_=TWILIO_FROM_NUMBER,
            to=to_number,
            body=message_body
        )
        log(f"  Row {row_number}: SUCCESS Message sent! SID: {message.sid}")
        return True
    except Exception as e:
        error_str = str(e)
        if "21608" in error_str:
            log(f"  Row {row_number}: FAILED {phone} has not joined the Twilio sandbox yet.")
        elif "21211" in error_str:
            log(f"  Row {row_number}: FAILED Invalid phone number: {phone}")
        elif "20003" in error_str:
            log(f"  Row {row_number}: FAILED Twilio authentication failed.")
        else:
            log(f"  Row {row_number}: FAILED to send to {phone}: {error_str}")
        return False


def parse_date(date_str, row_number):
    if not date_str or str(date_str).strip() == "":
        log(f"  Row {row_number}: Next Date is empty skipping.")
        return None
    try:
        return datetime.strptime(str(date_str).strip(), DATE_FORMAT).date()
    except ValueError:
        log(f"  Row {row_number}: Invalid date {date_str}. Use DD-MM-YYYY format.")
        return None


def validate_phone(phone_raw, row_number):
    if not phone_raw or str(phone_raw).strip() == "":
        log(f"  Row {row_number}: Phone number is empty skipping.")
        return None
    phone = str(phone_raw).strip().replace(" ", "").replace("-", "").replace("'", "")
    if not phone.startswith("+"):
        phone = "+" + phone
    digits = phone[1:]
    if not digits.isdigit() or len(digits) < 10:
        log(f"  Row {row_number}: Phone {phone} looks invalid.")
        return None
    log(f"  Row {row_number}: Phone validated: {phone}")
    return phone


def mark_reminder_sent(worksheet, data_row_index, headers):
    try:
        col_index = headers.index(COL_REMINDER_SENT) + 1
        sheet_row = data_row_index + 2
        worksheet.update_cell(sheet_row, col_index, "YES")
        log(f"  Sheet updated Row {data_row_index + 1} Reminder Sent YES")
        return True
    except Exception as e:
        log(f"  Failed to update sheet: {e}")
        return False


def main():
    log("COURT HEARING REMINDER V2 STARTING")
    log("=" * 55)

    today    = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    log(f"Today    : {today.strftime(DATE_FORMAT)}")
    log(f"Checking : {tomorrow.strftime(DATE_FORMAT)}")
    log("-" * 55)

    worksheet = connect_to_google_sheets()
    if not worksheet:
        sys.exit(1)

    twilio_client = get_twilio_client()
    if not twilio_client:
        sys.exit(1)

    try:
        all_records = worksheet.get_all_records()
        headers     = worksheet.row_values(1)
        log(f"Loaded {len(all_records)} rows. Columns: {headers}")
    except Exception as e:
        log(f"ERROR reading sheet: {e}")
        sys.exit(1)

    required = [COL_NAME, COL_PHONE, COL_CASE, COL_NEXT_DATE, COL_REMINDER_SENT]
    missing  = [c for c in required if c not in headers]
    if missing:
        log(f"ERROR: Missing columns: {missing}")
        sys.exit(1)

    log("-" * 55)

    sent = skipped = failed = 0

    for idx, record in enumerate(all_records):
        row_num       = idx + 1
        name          = str(record.get(COL_NAME, "")).strip()
        phone_raw     = str(record.get(COL_PHONE, "")).strip()
        case          = str(record.get(COL_CASE, "")).strip()
        next_date_raw = str(record.get(COL_NEXT_DATE, "")).strip()
        reminder_sent = str(record.get(COL_REMINDER_SENT, "")).strip().upper()

        log(f"\nRow {row_num}: {name or '(empty)'}")

        if not name:
            log("  Skipping empty name.")
            skipped += 1
            continue

        if reminder_sent == "YES":
            log("  Skipping reminder already sent.")
            skipped += 1
            continue

        next_date = parse_date(next_date_raw, row_num)
        if not next_date:
            skipped += 1
            continue

        if next_date != tomorrow:
            log(f"  Hearing on {next_date.strftime(DATE_FORMAT)} not tomorrow.")
            skipped += 1
            continue

        log("  HEARING IS TOMORROW sending reminder...")

        phone = validate_phone(phone_raw, row_num)
        if not phone:
            failed += 1
            continue

        success = send_whatsapp_message(
            twilio_client, phone, name, case,
            next_date.strftime(DATE_FORMAT), row_num
        )

        if success:
            mark_reminder_sent(worksheet, idx, headers)
            sent += 1
        else:
            failed += 1

    log("=" * 55)
    log("DONE SUMMARY")
    log(f"Sent    : {sent}")
    log(f"Skipped : {skipped}")
    log(f"Failed  : {failed}")
    log("=" * 55)


if __name__ == "__main__":
    main()
