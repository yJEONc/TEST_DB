from flask import Flask, render_template, request, jsonify
import datetime
import gspread
from google.oauth2.service_account import Credentials

# 구글 시트 설정
SPREADSHEET_ID = "1rsplfNq4e7d-nrp-Wlg1Mn9dsgjAcNn49yPQDXdzwg8"
SERVICE_ACCOUNT_FILE = "service_key.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)

def get_gspread_client():
    """service_key.json을 이용해 gspread 클라이언트 생성"""
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_sheets():
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    units_ws = sh.worksheet("units")
    school_ws = sh.worksheet("school")
    records_ws = sh.worksheet("records")
    return units_ws, school_ws, records_ws

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    """학년/학교/단원 목록을 한 번에 내려주는 API"""
    units_ws, school_ws, _ = get_sheets()

    units_records = units_ws.get_all_records()
    school_records = school_ws.get_all_records()

    # 학년 목록
    grade_set = set()
    units_by_grade = {}

    for row in units_records:
        grade = str(row.get("grade")).strip()
        number = str(row.get("number")).strip()
        unit_name = str(row.get("units")).strip()

        if not grade or not number or not unit_name:
            continue

        grade_set.add(grade)
        units_by_grade.setdefault(grade, []).append({
            "number": number,
            "unit": unit_name
        })

    grades = sorted(grade_set, key=lambda x: int(x))

    # 학교 목록
    schools = []
    for row in school_records:
        name = str(row.get("school")).strip()
        if name:
            schools.append(name)

    schools = sorted(set(schools))

    return jsonify({
        "grades": grades,
        "schools": schools,
        "unitsByGrade": units_by_grade
    })

@app.route("/api/save", methods=["POST"])
def api_save():
    """선택된 정보들을 records 시트에 저장"""
    _, _, records_ws = get_sheets()

    data = request.get_json(force=True)
    grade = str(data.get("grade")).strip()
    school = str(data.get("school")).strip()
    units = data.get("units", [])

    if not grade or not school or not units:
        return jsonify({"ok": False, "error": "필수 정보가 부족합니다."}), 400

    today = datetime.date.today().isoformat()

    rows = []
    for item in units:
        number = str(item.get("number")).strip()
        unit_name = str(item.get("unit")).strip()
        if not number or not unit_name:
            continue
        rows.append([today, grade, school, number, unit_name])

    if not rows:
        return jsonify({"ok": False, "error": "저장할 단원이 없습니다."}), 400

    # 여러 줄 한 번에 append
    records_ws.append_rows(rows)

    return jsonify({"ok": True, "saved": len(rows)})

if __name__ == "__main__":
    app.run(debug=True)
