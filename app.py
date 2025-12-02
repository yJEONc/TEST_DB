
from flask import Flask, jsonify, render_template
import os, json, traceback
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1rsplfNq4e7d-nrp-Wlg1Mn9dsgjAcNn49yPQDXdzwg8"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)

def load_credentials():
    raw = os.environ.get("SERVICE_KEY")
    if not raw:
        return None, "SERVICE_KEY missing"

    try:
        data = json.loads(raw)
    except Exception as e:
        return None, f"JSON parse error: {str(e)}"

    try:
        creds = Credentials.from_service_account_info(data, scopes=SCOPES)
    except Exception as e:
        return None, f"Credentials error: {str(e)}"

    return creds, "OK"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/debug")
def api_debug():
    result = {}

    raw = os.environ.get("SERVICE_KEY")
    result["env_length"] = len(raw) if raw else 0
    result["env_start"] = raw[:60] if raw else None

    creds, cred_status = load_credentials()
    result["credential_status"] = cred_status

    if creds is None:
        return jsonify(result)

    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)
        sheets = sh.worksheets()
        result["worksheets"] = [s.title for s in sheets]
    except Exception as e:
        result["sheets_error"] = str(e)
        result["trace"] = traceback.format_exc()
        return jsonify(result)

    result["status"] = "OK"
    return jsonify(result)
