from flask import Flask, render_template, request, jsonify
import datetime
import os
import json
import traceback

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1rsplfNq4e7d-nrp-Wlg1Mn9dsgjAcNn49yPQDXdzwg8"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)


def get_credentials():
    """
    SERVICE_KEY 환경 변수에 들어있는 Service Account JSON을 이용해 Credentials 생성
    """
    raw = os.environ.get("SERVICE_KEY")
    if not raw:
        raise RuntimeError("환경 변수 SERVICE_KEY 가 설정되어 있지 않습니다.")

    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"SERVICE_KEY JSON 파싱 오류: {e}")

    try:
        creds = Credentials.from_service_account_info(data, scopes=SCOPES)
    except Exception as e:
        raise RuntimeError(f"Credentials 생성 오류: {e}")

    return creds


def get_sheets():
    """
    gspread 클라이언트를 만들고, 필요한 worksheet 3개(units, school, records)를 반환
    """
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    try:
        units_ws = sh.worksheet("units")
        school_ws = sh.worksheet("school")
        records_ws = sh.worksheet("records")
    except Exception as e:
        raise RuntimeError(f"시트 이름(units/school/records)을 찾을 수 없습니다: {e}")

    return units_ws, school_ws, records_ws


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    """
    학년/학교/단원 목록을 내려주는 API
    """
    try:
        units_ws, school_ws, _ = get_sheets()
        units_records = units_ws.get_all_records()
        school_records = school_ws.get_all_records()

        grade_set = set()
        units_by_grade = {}

        # units 시트: grade, number, units
        for row in units_records:
            grade_raw = row.get("grade")
            number = str(row.get("number") or "").strip()
            unit_name = str(row.get("units") or "").strip()

            if grade_raw is None or not number or not unit_name:
                continue

            grade_str = str(grade_raw).strip()
            grade_set.add(grade_str)

            units_by_grade.setdefault(grade_str, []).append({
                "number": number,
                "unit": unit_name,
            })

        # 학년 정렬 (1,2,3 ...)
        def grade_key(g):
            try:
                return int(g)
            except ValueError:
                return 9999

        grades = sorted(grade_set, key=grade_key)

        # 학교 목록
        schools = []
        for row in school_records:
            name = str(row.get("school") or "").strip()
            if name:
                schools.append(name)
        schools = sorted(set(schools))

        return jsonify({
            "ok": True,
            "grades": grades,
            "schools": schools,
            "unitsByGrade": units_by_grade,
        })

    except Exception as e:
        # 디버깅용으로 에러 메시지도 내려줌
        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        }), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    """
    선택된 학년/학교/단원들을 records 시트에 저장
    """
    try:
        _, _, records_ws = get_sheets()

        data = request.get_json(force=True) or {}
        grade = str(data.get("grade") or "").strip()
        school = str(data.get("school") or "").strip()
        units = data.get("units") or []

        if not grade or not school or not units:
            return jsonify({"ok": False, "error": "grade, school, units 정보가 필요합니다."}), 400

        today = datetime.date.today().isoformat()

        rows = []
        for item in units:
            number = str(item.get("number") or "").strip()
            unit_name = str(item.get("unit") or "").strip()
            if not number or not unit_name:
                continue
            rows.append([today, grade, school, number, unit_name])

        if not rows:
            return jsonify({"ok": False, "error": "저장할 단원이 없습니다."}), 400

        # 여러 줄 한 번에 추가
        records_ws.append_rows(rows)

        return jsonify({"ok": True, "saved": len(rows)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


# 디버깅 유지용 (원하면 사용)
@app.route("/api/debug")
def api_debug():
    result = {}
    raw = os.environ.get("SERVICE_KEY")
    result["env_length"] = len(raw) if raw else 0
    result["env_start"] = raw[:60] if raw else None
    try:
        creds = get_credentials()
        result["credential_status"] = "OK"
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws_list = sh.worksheets()
        result["worksheets"] = [w.title for w in ws_list]
        result["status"] = "OK"
    except Exception as e:
        result["credential_status"] = "ERROR"
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()
    return jsonify(result)


if __name__ == "__main__":
    # 로컬 테스트용
    app.run(debug=True)
