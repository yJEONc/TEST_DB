from flask import Flask, render_template, request, jsonify
import datetime
import os
import json
import traceback
import re
import threading

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1rsplfNq4e7d-nrp-Wlg1Mn9dsgjAcNn49yPQDXdzwg8"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)

# -----------------------------
# end 시트 캐시
# -----------------------------
END_CACHE = {
    "loaded": False,
    "end_school_map": {},   # {"1": ["학교A", "학교B"], "2": [...]}
    "updated_at": None
}
END_CACHE_LOCK = threading.Lock()


def get_credentials():
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


def get_spreadsheet():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID)


def get_sheets():
    sh = get_spreadsheet()

    try:
        units_ws = sh.worksheet("units")
        school_ws = sh.worksheet("class+")
        records_ws = sh.worksheet("records")
        settings_ws = sh.worksheet("settings")
        end_ws = sh.worksheet("end")
    except Exception as e:
        raise RuntimeError(f"시트 이름(units/class+/records/settings/end)을 찾을 수 없습니다: {e}")

    return units_ws, school_ws, records_ws, settings_ws, end_ws


def get_header_index(headers, target_name):
    try:
        return headers.index(target_name)
    except ValueError:
        raise RuntimeError(f"헤더 '{target_name}' 를 찾을 수 없습니다. 현재 헤더: {headers}")


def safe_cell(row, idx):
    return row[idx].strip() if len(row) > idx and row[idx] is not None else ""


def parse_start_date(text):
    if not text:
        return None

    s = str(text).strip()
    if not s or s in {"미정", "예정", "-", "?", "미확정"}:
        return None

    s = s.replace("년", ".").replace("월", ".").replace("일", "")
    s = s.replace("/", ".")
    s = re.sub(r"\s+", "", s)

    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None

    m = re.search(r"(\d{1,2})\.(\d{1,2})", s)
    if m:
        mo, d = map(int, m.groups())
        y = datetime.date.today().year
        try:
            return datetime.date(y, mo, d)
        except ValueError:
            return None

    return None


def get_current_sort_header(settings_ws):
    val = settings_ws.acell("A1").value
    val = (val or "").strip()

    if not val:
        raise RuntimeError("settings 시트 A1 이 비어 있습니다.")

    return val


def get_current_term_name(settings_ws):
    header_name = get_current_sort_header(settings_ws)
    if header_name.endswith("_시험기간"):
        return header_name[:-5]
    return header_name


def school_sort_key(item):
    dt = item["date"]
    school = item["school"]
    return (dt is None, dt or datetime.date.max, school)


def build_end_school_map_from_rows(end_rows):
    """
    end 시트에서
    B열=grade, C열=school 기준으로 학년별 학교 목록 생성
    """
    end_school_map = {}

    if not end_rows:
        return end_school_map

    start_idx = 0
    if len(end_rows[0]) >= 3:
        b0 = (end_rows[0][1] or "").strip().lower()
        c0 = (end_rows[0][2] or "").strip().lower()
        if b0 == "grade" or c0 == "school":
            start_idx = 1

    for row in end_rows[start_idx:]:
        grade_val = row[1].strip() if len(row) > 1 and row[1] else ""
        school_val = row[2].strip() if len(row) > 2 and row[2] else ""

        if not grade_val or not school_val:
            continue

        end_school_map.setdefault(grade_val, set()).add(school_val)

    return {
        grade: sorted(list(schools_set))
        for grade, schools_set in end_school_map.items()
    }


def refresh_end_cache():
    """
    end 시트를 다시 읽어서 캐시 갱신
    """
    _, _, _, _, end_ws = get_sheets()
    end_rows = end_ws.get_all_values()
    end_school_map = build_end_school_map_from_rows(end_rows)

    with END_CACHE_LOCK:
        END_CACHE["loaded"] = True
        END_CACHE["end_school_map"] = end_school_map
        END_CACHE["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return END_CACHE


def ensure_end_cache():
    """
    처음 1번만 end 시트를 읽고, 이후에는 캐시 사용
    """
    with END_CACHE_LOCK:
        if END_CACHE["loaded"]:
            return END_CACHE

    return refresh_end_cache()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    try:
        units_ws, school_ws, _, settings_ws, _ = get_sheets()

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

        current_sort_header = get_current_sort_header(settings_ws)
        sort_idx = get_header_index(school_headers, current_sort_header)

        grade_set = set()
        units_by_grade = {}

        for row in units_data:
            grade_raw = safe_cell(row, grade_idx)
            number = safe_cell(row, number_idx)
            unit_name = safe_cell(row, unit_idx)

            if not grade_raw or not number or not unit_name:
                continue

            grade_set.add(grade_raw)
            units_by_grade.setdefault(grade_raw, []).append({
                "number": number,
                "unit": unit_name,
            })

        def grade_key(g):
            try:
                return int(g)
            except ValueError:
                return 9999

        grades = sorted(grade_set, key=grade_key)

        school_map = {}

        for row in school_data:
            school_name = safe_cell(row, current_school_idx)
            sort_text = safe_cell(row, sort_idx)

            if not school_name:
                continue

            parsed_date = parse_start_date(sort_text)

            if school_name not in school_map:
                school_map[school_name] = {
                    "school": school_name,
                    "date": parsed_date,
                }
            else:
                old_date = school_map[school_name]["date"]
                if old_date is None and parsed_date is not None:
                    school_map[school_name]["date"] = parsed_date
                elif old_date is not None and parsed_date is not None and parsed_date < old_date:
                    school_map[school_name]["date"] = parsed_date

        sorted_school_items = sorted(school_map.values(), key=school_sort_key)
        schools = [item["school"] for item in sorted_school_items]

        end_cache = ensure_end_cache()

        return jsonify({
            "ok": True,
            "grades": grades,
            "schools": schools,
            "unitsByGrade": units_by_grade,
            "currentSortHeader": current_sort_header,
            "currentTermName": get_current_term_name(settings_ws),
            "endSchoolMap": end_cache["end_school_map"],
            "endCacheUpdatedAt": end_cache["updated_at"],
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        }), 500


@app.route("/api/refresh_end_cache", methods=["POST"])
def api_refresh_end_cache():
    """
    end 시트 수동 업데이트 버튼용
    """
    try:
        cache = refresh_end_cache()
        return jsonify({
            "ok": True,
            "updatedAt": cache["updated_at"],
            "gradeCount": len(cache["end_school_map"]),
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        }), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    try:
        _, _, records_ws, settings_ws, _ = get_sheets()

        data = request.get_json(force=True) or {}
        grade = str(data.get("grade") or "").strip()
        school = str(data.get("school") or "").strip()
        units = data.get("units") or []

        if not grade or not school or not units:
            return jsonify({"ok": False, "error": "grade, school, units 정보가 필요합니다."}), 400

        today = datetime.date.today().isoformat()
        current_term_name = get_current_term_name(settings_ws)

        rows = []
        for item in units:
            number = str(item.get("number") or "").strip()
            unit_name = str(item.get("unit") or "").strip()
            if not number or not unit_name:
                continue

            rows.append([today, grade, school, number, unit_name, current_term_name])

        if not rows:
            return jsonify({"ok": False, "error": "저장할 단원이 없습니다."}), 400

        records_ws.append_rows(rows)

        return jsonify({
            "ok": True,
            "saved": len(rows),
            "currentTermName": current_term_name
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/debug")
def api_debug():
    result = {}
    raw = os.environ.get("SERVICE_KEY")
    result["env_length"] = len(raw) if raw else 0
    result["env_start"] = raw[:60] if raw else None

    try:
        sh = get_spreadsheet()
        ws_list = sh.worksheets()
        result["worksheets"] = [w.title for w in ws_list]

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

        try:
            settings_ws = sh.worksheet("settings")
            result["settings_A1"] = settings_ws.acell("A1").value
            result["current_sort_header"] = get_current_sort_header(settings_ws)
            result["current_term_name"] = get_current_term_name(settings_ws)
        except Exception as inner_e:
            result["settings_error"] = str(inner_e)

        with END_CACHE_LOCK:
            result["end_cache_loaded"] = END_CACHE["loaded"]
            result["end_cache_updated_at"] = END_CACHE["updated_at"]
            result["end_cache_grade_keys"] = list(END_CACHE["end_school_map"].keys())

        result["status"] = "OK"

    except Exception as e:
        result["credential_status"] = "ERROR"
        result["error"] = str(e)
        result["trace"] = traceback.format_exc()

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
