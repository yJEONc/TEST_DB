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
    gspread 클라이언트를 만들고, 필요한 worksheet 3개(units, class+, records)를 반환
    """
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    try:
        units_ws = sh.worksheet("units")
        school_ws = sh.worksheet("class+")
        records_ws = sh.worksheet("records")
    except Exception as e:
        raise RuntimeError(f"시트 이름(units/class+/records)을 찾을 수 없습니다: {e}")

    return units_ws, school_ws, records_ws


def get_header_index(headers, target_name):
    """
    헤더 리스트에서 target_name의 인덱스를 반환
    """
    try:
        return headers.index(target_name)
    except ValueError:
        raise RuntimeError(f"헤더 '{target_name}' 를 찾을 수 없습니다. 현재 헤더: {headers}")


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

        # 중복 헤더 때문에 get_all_records() 대신 get_all_values() 사용
        units_rows = units_ws.get_all_values()
        school_rows = school_ws.get_all_values()

        if not units_rows:
            raise RuntimeError("units 시트가 비어 있습니다.")
        if not school_rows:
            raise RuntimeError("class+ 시트가 비어 있습니다.")

        units_headers = units_rows[0]
        units_data = units_rows[1:]

        school_headers = school_rows[0]
        school_data = school_rows[1:]

        grade_idx = get_header_index(units_headers, "grade")
        number_idx = get_header_index(units_headers, "number")
        unit_idx = get_header_index(units_headers, "units")

        current_school_idx = get_header_index(school_headers, "현재 학교")

        grade_set = set()
        units_by_grade = {}

        # units 시트 처리
        for row in units_data:
            grade_raw = row[grade_idx].strip() if len(row) > grade_idx else ""
            number = row[number_idx].strip() if len(row) > number_idx else ""
            unit_name = row[unit_idx].strip() if len(row) > unit_idx else ""

            if not grade_raw or not number or not unit_name:
                continue

            grade_set.add(grade_raw)
            units_by_grade.setdefault(grade_raw, []).append({
                "number": number,
                "unit": unit_name,
            })

        # 학년 정렬
        def grade_key(g):
            try:
                return int(g)
            except ValueError:
                return 9999

        grades = sorted(grade_set, key=grade_key)

        # 학교 목록 처리 (class+ 시트의 현재 학교 기준)
        schools = []
        for row in school_data:
            name = row[current_school_idx].strip() if len(row) > current_school_idx else ""
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

        records_ws.append_rows(rows)

        return jsonify({"ok": True, "saved": len(rows)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


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

        # 헤더 확인용
        try:
            class_ws = sh.worksheet("class+")
            class_rows = class_ws.get_all_values()
            result["class+_headers"] = class_rows[0] if class_rows else []
        except Exception as inner_e:
            result["class+_headers_error"] = str(inner_e)

        try:
            units_ws = sh.worksheet("units")
            units_rows = units_ws.get_all_values()
            result["units_headers"] = units_rows[0] if units_rows else []
        except Exception as inner_e:
            result["units_headers_error"] = str(inner_e)

        result["status"] = "OK"
    except Exception as e:
        result["credential_status"] = "ERROR"
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
