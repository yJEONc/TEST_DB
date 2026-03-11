let grades = [];
let schools = [];
let unitsByGrade = {};
let endSchoolMap = {};

let selectedGrade = null;
let selectedSchool = null;
let selectedUnits = new Set();

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
        endSchoolMap = data.endSchoolMap || {};

        const currentTermDisplay = document.getElementById("currentTermDisplay");
        if (currentTermDisplay) {
            currentTermDisplay.textContent = data.currentTermName
                ? `현재 기준 : ${data.currentTermName}`
                : "";
        }

        const endCacheInfo = document.getElementById("endCacheInfo");
        if (endCacheInfo) {
            endCacheInfo.textContent = data.endCacheUpdatedAt
                ? `end 캐시 갱신 시각 : ${data.endCacheUpdatedAt}`
                : "end 캐시 갱신 시각 : 없음";
        }

        renderGradeList();
        renderSchoolList();
        renderUnits();
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
        li.textContent = g + "학년";

        li.addEventListener("click", () => {
            selectedGrade = g;
            selectedSchool = null;
            selectedUnits.clear();

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

    const highlightedSchools = new Set(endSchoolMap[selectedGrade] || []);

    schools.forEach(school => {
        const li = document.createElement("li");
        li.className = "sidebar-item" + (selectedSchool === school ? " active" : "");
        li.textContent = school;

        if (selectedGrade && highlightedSchools.has(school)) {
            li.classList.add("school-done");
            li.title = "end 시트에 이미 등록된 학교입니다.";
        }

        li.addEventListener("click", () => {
            selectedSchool = school;
            selectedUnits.clear();

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
        container.innerHTML = "<p>학년을 먼저 선택하세요.</p>";
        return;
    }

    const units = unitsByGrade[selectedGrade] || [];

    if (units.length === 0) {
        container.innerHTML = "<p>표시할 단원이 없습니다.</p>";
        return;
    }

    units.forEach(item => {
        const key = `${item.number}|${item.unit}`;

        const label = document.createElement("label");
        label.className = "unit-item";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selectedUnits.has(key);

        checkbox.addEventListener("change", () => {
            if (checkbox.checked) {
                selectedUnits.add(key);
            } else {
                selectedUnits.delete(key);
            }
            updateSaveButton();
        });

        const span = document.createElement("span");
        span.textContent = `${item.number}. ${item.unit}`;

        label.appendChild(checkbox);
        label.appendChild(span);
        container.appendChild(label);
    });
}

function updateSummary() {
    const summary = document.getElementById("selectionSummary");

    if (!selectedGrade && !selectedSchool) {
        summary.textContent = "학년과 학교를 선택하세요.";
        return;
    }

    if (selectedGrade && !selectedSchool) {
        summary.textContent = `${selectedGrade}학년을 선택했습니다. 학교를 선택하세요.`;
        return;
    }

    summary.textContent = `${selectedGrade}학년 / ${selectedSchool}`;
}

function updateSaveButton() {
    const saveBtn = document.getElementById("saveBtn");
    saveBtn.disabled = !(selectedGrade && selectedSchool && selectedUnits.size > 0);
}

async function saveSelection() {
    if (!(selectedGrade && selectedSchool && selectedUnits.size > 0)) {
        return;
    }

    const units = Array.from(selectedUnits).map(v => {
        const [number, unit] = v.split("|");
        return { number, unit };
    });

    try {
        const res = await fetch("/api/save", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                grade: selectedGrade,
                school: selectedSchool,
                units: units
            })
        });

        const data = await res.json();

        if (!data.ok) {
            alert("저장 실패: " + (data.error || "알 수 없는 오류"));
            return;
        }

        alert(`저장 완료: ${data.saved}건`);
    } catch (err) {
        console.error(err);
        alert("저장 중 오류가 발생했습니다.");
    }
}

async function refreshEndCache() {
    const btn = document.getElementById("refreshEndBtn");
    const originalText = btn.textContent;

    try {
        btn.disabled = true;
        btn.textContent = "업데이트 중...";

        const res = await fetch("/api/refresh_end_cache", {
            method: "POST"
        });
        const data = await res.json();

        if (!data.ok) {
            alert("end 시트 업데이트 실패: " + (data.error || ""));
            return;
        }

        await fetchData();
        alert("end 시트 캐시를 업데이트했습니다.");
    } catch (err) {
        console.error(err);
        alert("end 시트 업데이트 중 오류가 발생했습니다.");
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

document.getElementById("saveBtn").addEventListener("click", saveSelection);
document.getElementById("refreshEndBtn").addEventListener("click", refreshEndCache);

fetchData();
