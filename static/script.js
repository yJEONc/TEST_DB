let grades = [];
let schools = [];
let unitsByGrade = {};

let selectedGrade = null;
let selectedSchool = null;
let selectedUnits = new Set(); // "number|unit" 형태로 저장

let isSaving = false;

/* ✅ 저장 UI 토글 (로딩바 + 버튼 잠금/문구 변경) */
function setSavingUI(on) {
    const loading = document.getElementById("saveLoading");
    const btn = document.getElementById("saveBtn");
    if (!btn) return;

    if (on) {
        isSaving = true;

        if (loading) {
            loading.classList.add("active");
            loading.setAttribute("aria-hidden", "false");
        }

        btn.disabled = true; // 중복 클릭 방지
        btn.dataset.prevText = btn.textContent;
        btn.textContent = "저장 중...";
    } else {
        isSaving = false;

        if (loading) {
            loading.classList.remove("active");
            loading.setAttribute("aria-hidden", "true");
        }

        btn.textContent = btn.dataset.prevText || "선택 저장";

        // 현재 선택 상태에 맞춰 버튼 활성/비활성 복구
        updateSaveButton();
    }
}

async function fetchData() {
    try {
        const res = await fetch("/api/data");
        const data = await res.json();

        if (!data.ok) {
            console.error("API error:", data);
            alert("데이터 로딩 중 오류가 발생했습니다.\n" + (data.error || ""));
            return;
        }

        grades = data.grades || [];
        schools = data.schools || [];
        unitsByGrade = data.unitsByGrade || {};

        renderGradeList();
        renderSchoolList();
        renderUnits();

        // ✅ 초기 요약/버튼 상태도 맞춰주기(원래는 학년/학교 눌러야 갱신됐음)
        updateSummary();
        updateSaveButton();
    } catch (err) {
        console.error(err);
        alert("서버와 통신 중 오류가 발생했습니다.");
    }
}

function renderGradeList() {
    const ul = document.getElementById("gradeList");
    ul.innerHTML = "";
    grades.forEach(g => {
        const li = document.createElement("li");
        li.className = "sidebar-item" + (selectedGrade === g ? " active" : "");
        li.textContent = `중학교 ${g}학년`;
        li.onclick = () => {
            selectedGrade = g;
            selectedUnits.clear(); // 학년 변경 시 선택 초기화
            renderGradeList();
            renderUnits();
            updateSummary();
            updateSaveButton();
        };
        ul.appendChild(li);
    });
}

function renderSchoolList() {
    const ul = document.getElementById("schoolList");
    ul.innerHTML = "";
    schools.forEach(school => {
        const li = document.createElement("li");
        li.className = "sidebar-item" + (selectedSchool === school ? " active" : "");
        li.textContent = school;

        li.onclick = () => {
            selectedSchool = school;

            // 🔥 추가: 학교 변경 시 단원 선택 초기화
            selectedUnits.clear();
            renderUnits();

            renderSchoolList();
            updateSummary();
            updateSaveButton();
        };

        ul.appendChild(li);
    });
}

function renderUnits() {
    const container = document.getElementById("unitList");
    container.innerHTML = "";

    if (!selectedGrade) {
        const p = document.createElement("p");
        p.textContent = "왼쪽에서 학년을 먼저 선택하세요.";
        p.style.fontSize = "14px";
        p.style.color = "#6b7280";
        container.appendChild(p);
        return;
    }

    const list = unitsByGrade[selectedGrade] || [];
    if (list.length === 0) {
        const p = document.createElement("p");
        p.textContent = "등록된 단원이 없습니다.";
        container.appendChild(p);
        return;
    }

    list.forEach(item => {
        const key = `${item.number}|${item.unit}`;
        const wrapper = document.createElement("div");
        wrapper.className = "unit-item";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selectedUnits.has(key);
        checkbox.onchange = () => {
            if (checkbox.checked) {
                selectedUnits.add(key);
            } else {
                selectedUnits.delete(key);
            }
            updateSaveButton();
            updateSummary(); // ✅ 단원 선택 개수까지 summary에 반영하고 싶으면 유지(원래는 안 했음)
        };

        const codeSpan = document.createElement("span");
        codeSpan.className = "unit-code";
        codeSpan.textContent = item.number;

        const nameSpan = document.createElement("span");
        nameSpan.className = "unit-name";
        nameSpan.textContent = item.unit;

        wrapper.onclick = (e) => {
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.onchange();
            }
        };

        wrapper.appendChild(checkbox);
        wrapper.appendChild(codeSpan);
        wrapper.appendChild(nameSpan);
        container.appendChild(wrapper);
    });
}

function updateSummary() {
    const summary = document.getElementById("selectionSummary");

    // ✅ 단원 선택 개수까지 보여주면(스크린샷처럼) UX가 좋아서 넣어둠
    const unitCount = selectedUnits.size;

    if (selectedGrade && selectedSchool) {
        summary.textContent = `중학교 ${selectedGrade}학년 / ${selectedSchool} / 선택 단원: ${unitCount}개`;
    } else if (selectedGrade) {
        summary.textContent = `중학교 ${selectedGrade}학년을 선택했습니다. 학교를 선택하세요.`;
    } else if (selectedSchool) {
        summary.textContent = `${selectedSchool}을(를) 선택했습니다. 학년을 선택하세요.`;
    } else {
        summary.textContent = "학년과 학교를 선택하세요.";
    }
}

function updateSaveButton() {
    const btn = document.getElementById("saveBtn");

    // ✅ 저장 중엔 무조건 잠금 유지
    if (isSaving) {
        btn.disabled = true;
        return;
    }

    if (selectedGrade && selectedSchool && selectedUnits.size > 0) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
    }
}

async function saveSelection() {
    // ✅ 저장 중이면 무시(중복 클릭 방지)
    if (isSaving) return;

    if (!selectedGrade || !selectedSchool || selectedUnits.size === 0) return;

    setSavingUI(true);

    const units = Array.from(selectedUnits).map(key => {
        const [number, unit] = key.split("|");
        return { number, unit };
    });

    const payload = {
        grade: selectedGrade,
        school: selectedSchool,
        units
    };

    try {
        const res = await fetch("/api/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.ok) {
            alert(`저장 완료! (${data.saved}개 단원)`);
        } else {
            alert("저장 중 오류: " + (data.error || "알 수 없는 오류"));
        }
    } catch (err) {
        console.error(err);
        alert("저장 요청 중 오류가 발생했습니다.");
    } finally {
        setSavingUI(false);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    fetchData();
    document.getElementById("saveBtn").addEventListener("click", saveSelection);
});
