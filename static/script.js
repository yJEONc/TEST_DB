let grades = [];
let schools = [];
let unitsByGrade = {};

let selectedGrade = null;
let selectedSchool = null;
let selectedUnits = new Set(); // "number|unit" 형태로 저장

let isSaving = false;

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
        btn.disabled = true; // ✅ 중복 클릭 방지
        btn.dataset.prevText = btn.textContent;
        btn.textContent = "저장 중...";
    } else {
        isSaving = false;
        if (loading) {
            loading.classList.remove("active");
            loading.setAttribute("aria-hidden", "true");
        }
        btn.textContent = btn.dataset.prevText || "선택 저장";
        // ✅ 현재 선택 상태에 맞춰 버튼 활성/비활성 복구
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
        updateSummary();
        updateSaveButton();
    } catch (err) {
        console.error(err);
        alert("데이터 로딩 중 오류가 발생했습니다.");
    }
}

function renderGradeList() {
    const ul = document.getElementById("gradeList");
    ul.innerHTML = "";

    grades.forEach(grade => {
        const li = document.createElement("li");
        li.className = "sidebar-item";
        li.textContent = grade;

        if (grade === selectedGrade) li.classList.add("active");

        li.addEventListener("click", () => {
            selectedGrade = grade;
            selectedSchool = null;
            selectedUnits.clear(); // 학년 변경 시 선택 초기화
            renderGradeList();
            renderSchoolList();
            renderUnits();
            updateSummary();
            updateSaveButton();
        });

        ul.appendChild(li);
    });
}

function renderSchoolList() {
    const ul = document.getElementById("schoolList");
    ul.innerHTML = "";

    schools.forEach(school => {
        const li = document.createElement("li");
        li.className = "sidebar-item";
        li.textContent = school;

        if (school === selectedSchool) li.classList.add("active");

        li.addEventListener("click", () => {
            selectedSchool = school;
            selectedUnits.clear(); // 학교 변경 시 단원 선택 초기화
            renderSchoolList();
            renderUnits();
            updateSummary();
            updateSaveButton();
        });

        ul.appendChild(li);
    });
}

function renderUnits() {
    const container = document.getElementById("unitList");
    container.innerHTML = "";

    if (!selectedGrade) {
        container.innerHTML = "<p style='color:#6b7280;font-size:14px;'>먼저 학년을 선택하세요.</p>";
        return;
    }

    const units = unitsByGrade[selectedGrade] || [];
    if (units.length === 0) {
        container.innerHTML = "<p style='color:#6b7280;font-size:14px;'>해당 학년의 단원 데이터가 없습니다.</p>";
        return;
    }

    units.forEach(item => {
        const key = `${item.number}|${item.unit}`;

        const row = document.createElement("label");
        row.className = "unit-item";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selectedUnits.has(key);

        checkbox.addEventListener("change", (e) => {
            if (e.target.checked) {
                selectedUnits.add(key);
            } else {
                selectedUnits.delete(key);
            }
            updateSummary();
            updateSaveButton();
        });

        const codeSpan = document.createElement("span");
        codeSpan.className = "unit-code";
        codeSpan.textContent = item.number;

        const nameSpan = document.createElement("span");
        nameSpan.className = "unit-name";
        nameSpan.textContent = item.unit;

        row.appendChild(checkbox);
        row.appendChild(codeSpan);
        row.appendChild(nameSpan);

        container.appendChild(row);
    });
}

function updateSummary() {
    const summary = document.getElementById("selectionSummary");

    const gradeText = selectedGrade ? `학년: ${selectedGrade}` : "학년: (미선택)";
    const schoolText = selectedSchool ? `학교: ${selectedSchool}` : "학교: (미선택)";
    const unitCount = selectedUnits.size;

    summary.textContent = `${gradeText} / ${schoolText} / 선택 단원: ${unitCount}개`;
}

function updateSaveButton() {
    const btn = document.getElementById("saveBtn");
    if (selectedGrade && selectedSchool && selectedUnits.size > 0) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
    }
}

async function saveSelection() {
    if (isSaving) return; // ✅ 이미 저장 중이면 무시
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
