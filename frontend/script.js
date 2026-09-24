const API = "";

let materials = [];
let plans = [];
let quizData = null;
let currentQuizIndex = 0;
let selectedAnswer = null;
let editingPlanId = null;


/* =====================================================
   HELPERS
===================================================== */

function $(id) {
    return document.getElementById(id);
}

function escapeHTML(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatDate(dateString) {
    if (!dateString) {
        return "";
    }

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
        return dateString;
    }

    return date.toLocaleString();
}

function showToast(message) {
    const toast = $("toast");

    if (!toast) return;

    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2500);
}

async function apiFetch(url, options = {}) {
    try {
        const response = await fetch(API + url, options);

        let data = {};

        try {
            data = await response.json();
        } catch {
            data = {};
        }

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.message ||
                `Request failed (${response.status})`
            );
        }

        return data;
    } catch (error) {
        console.error(error);
        throw error;
    }
}


/* =====================================================
   DARK / LIGHT MODE
===================================================== */

function loadTheme() {
    const savedTheme = localStorage.getItem("studyai-theme");

    if (savedTheme === "dark") {
        document.body.classList.add("dark");
    } else {
        document.body.classList.remove("dark");
    }

    updateThemeButton();
}

function updateThemeButton() {
    const button = $("themeButton");

    if (!button) return;

    if (document.body.classList.contains("dark")) {
        button.textContent = "☀️ Light mode";
    } else {
        button.textContent = "🌙 Dark mode";
    }
}

function toggleTheme() {
    document.body.classList.toggle("dark");

    const isDark = document.body.classList.contains("dark");

    localStorage.setItem(
        "studyai-theme",
        isDark ? "dark" : "light"
    );

    updateThemeButton();
}


/* =====================================================
   NAVIGATION
===================================================== */

const pageTitles = {
    dashboard: "Good to see you 👋",
    materials: "Your study material 📚",
    ask: "Ask AI 💬",
    quiz: "Test your knowledge 🧠",
    "study-plan": "Plan your study time ⏰",
    history: "Your progress 📊"
};

function showSection(sectionId) {
    document.querySelectorAll(".section").forEach(section => {
        section.classList.remove("active");
    });

    const section = $(sectionId);

    if (section) {
        section.classList.add("active");
    }

    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.toggle(
            "active",
            item.dataset.section === sectionId
        );
    });

    const title = $("pageTitle");

    if (title) {
        title.textContent =
            pageTitles[sectionId] ||
            "AI Study Assistant";
    }

    document.querySelector(".sidebar")?.classList.remove("open");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    if (sectionId === "materials") {
        loadMaterials();
    }

    if (sectionId === "ask") {
        loadAskMaterials();
    }

    if (sectionId === "study-plan") {
        loadPlans();
    }

    if (sectionId === "history") {
        loadHistory();
    }
}

function setupNavigation() {
    document.querySelectorAll(".nav-item").forEach(button => {
        button.addEventListener("click", () => {
            showSection(button.dataset.section);
        });
    });

    $("mobileMenu")?.addEventListener("click", () => {
        document.querySelector(".sidebar")?.classList.toggle("open");
    });
}


/* =====================================================
   STATS
===================================================== */

async function loadStats() {
    try {
        const data = await apiFetch("/api/stats");

        $("materialsCount").textContent =
            data.materials ?? data.material_count ?? 0;

        $("questionsCount").textContent =
            data.questions ??
            data.conversations ??
            data.question_count ??
            0;

        $("quizCount").textContent =
            data.quizzes ??
            data.quiz_count ??
            0;

        $("plansCount").textContent =
            data.study_plans ??
            data.plans ??
            data.plan_count ??
            0;

    } catch (error) {
        console.error("Stats error:", error);
    }
}


/* =====================================================
   STREAK
===================================================== */

function loadStreak() {
    const today = new Date()
        .toISOString()
        .split("T")[0];

    const savedDate =
        localStorage.getItem("studyai-last-study-date");

    let streak =
        parseInt(
            localStorage.getItem("studyai-streak") || "0",
            10
        );

    if (!savedDate) {
        streak = 1;

        localStorage.setItem(
            "studyai-last-study-date",
            today
        );

        localStorage.setItem(
            "studyai-streak",
            streak
        );
    } else if (savedDate !== today) {

        const previous = new Date(savedDate);
        const current = new Date(today);

        const difference =
            Math.round(
                (current - previous) /
                (1000 * 60 * 60 * 24)
            );

        if (difference === 1) {
            streak += 1;
        } else if (difference > 1) {
            streak = 1;
        }

        localStorage.setItem(
            "studyai-last-study-date",
            today
        );

        localStorage.setItem(
            "studyai-streak",
            streak
        );
    }

    $("streakNumber").textContent = streak;
}


/* =====================================================
   MATERIALS
===================================================== */

async function loadMaterials() {
    const list = $("materialsList");

    if (!list) return;

    list.innerHTML =
        `<div class="empty">Loading materials...</div>`;

    try {
        const data =
            await apiFetch("/api/materials");

        materials =
            Array.isArray(data)
                ? data
                : data.materials || [];

        renderMaterials();
        populateMaterialSelects();

    } catch (error) {
        list.innerHTML =
            `<div class="empty">Unable to load materials.</div>`;

        console.error(error);
    }
}

function renderMaterials() {
    const list = $("materialsList");

    if (!list) return;

    if (!materials.length) {
        list.innerHTML = `
            <div class="empty">
                No materials uploaded yet.
                Upload your first PDF or image above.
            </div>
        `;
        return;
    }

    list.innerHTML = materials.map(material => {

        const type =
            material.material_type ||
            material.type ||
            "file";

        return `
            <div class="material-card">

                <div class="material-info">

                    <strong>
                        📄 ${escapeHTML(material.filename)}
                    </strong>

                    <span>
                        ${escapeHTML(type)}
                        ${material.uploaded_at
                            ? " • " + escapeHTML(
                                formatDate(material.uploaded_at)
                              )
                            : ""}
                    </span>

                </div>

                <div class="material-actions">

                    <button
                        class="small-button"
                        onclick="useMaterial(${material.id})"
                    >
                        Ask about it
                    </button>

                    <button
                        class="danger-button"
                        onclick="deleteMaterial(${material.id})"
                    >
                        Delete
                    </button>

                </div>

            </div>
        `;
    }).join("");
}

function populateMaterialSelects() {
    const select = $("askMaterial");

    if (!select) return;

    const current =
        select.value;

    select.innerHTML = `
        <option value="">
            Latest material
        </option>
    `;

    materials.forEach(material => {

        const option =
            document.createElement("option");

        option.value = material.id;

        option.textContent =
            material.filename;

        select.appendChild(option);
    });

    if (current) {
        select.value = current;
    }
}

function useMaterial(id) {
    showSection("ask");

    const select = $("askMaterial");

    if (select) {
        select.value = String(id);
    }
}

async function deleteMaterial(id) {
    const confirmed =
        confirm(
            "Delete this study material?"
        );

    if (!confirmed) return;

    try {
        await apiFetch(
            `/api/material/${id}`,
            {
                method: "DELETE"
            }
        );

        showToast("Material deleted");

        await loadMaterials();
        await loadStats();

    } catch (error) {
        showToast(error.message);
    }
}


/* =====================================================
   UPLOAD
===================================================== */

function setupUpload() {
    const fileInput = $("fileInput");
    const fileName = $("fileName");
    const uploadButton = $("uploadButton");

    fileInput?.addEventListener("change", () => {

        const file =
            fileInput.files?.[0];

        if (!file) {
            fileName.textContent = "";
            return;
        }

        fileName.textContent =
            `Selected: ${file.name}`;
    });

    uploadButton?.addEventListener(
        "click",
        uploadMaterial
    );
}

async function uploadMaterial() {
    const fileInput = $("fileInput");
    const status = $("uploadStatus");

    if (!fileInput?.files?.length) {
        showToast("Please choose a file first.");
        return;
    }

    const file =
        fileInput.files[0];

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );

    status.textContent =
        "Uploading and analyzing...";

    status.className =
        "status";

    try {

        const data =
            await apiFetch(
                "/api/upload",
                {
                    method: "POST",
                    body: formData
                }
            );

        status.textContent =
            data.message ||
            "Material uploaded successfully.";

        status.className =
            "status success";

        fileInput.value = "";

        $("fileName").textContent = "";

        showToast(
            "Material uploaded successfully!"
        );

        await loadMaterials();
        await loadStats();

    } catch (error) {

        status.textContent =
            error.message;

        status.className =
            "status error";

        showToast(
            "Upload failed."
        );
    }
}


/* =====================================================
   ASK AI
===================================================== */

function setupAsk() {
    $("askButton")?.addEventListener(
        "click",
        askAI
    );
}

async function askAI() {
    const question =
        $("questionInput")?.value.trim();

    const materialId =
        $("askMaterial")?.value;

    const output =
        $("answerOutput");

    if (!question) {
        showToast("Please enter a question.");
        return;
    }

    output.textContent =
        "Thinking...";

    try {

        const body = {
            question: question,
            user_id: "default"
        };

        if (materialId) {
            body.material_id =
                Number(materialId);
        }

        const data =
            await apiFetch(
                "/api/ask",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify(body)
                }
            );

        output.textContent =
            data.answer ||
            data.response ||
            "No answer returned.";

        await loadStats();

    } catch (error) {

        output.textContent =
            error.message;

        showToast(
            "Unable to answer question."
        );
    }
}

function loadAskMaterials() {
    if (!materials.length) {
        loadMaterials();
    } else {
        populateMaterialSelects();
    }
}


/* =====================================================
   QUIZ
===================================================== */

function setupQuiz() {
    $("generateQuizButton")?.addEventListener(
        "click",
        generateQuiz
    );

    $("nextQuestionButton")?.addEventListener(
        "click",
        nextQuizQuestion
    );
}

async function generateQuiz() {
    const button =
        $("generateQuizButton");

    button.disabled = true;
    button.textContent =
        "Generating...";

    try {

        const data =
            await apiFetch(
                "/api/quiz"
            );

        quizData = data;

        if (Array.isArray(data)) {
            quizData = {
                questions: data
            };
        }

        if (
            !quizData.questions ||
            quizData.questions.length !== 10
        ) {
            throw new Error(
                "The quiz must contain exactly 10 questions."
            );
        }

        currentQuizIndex = 0;
        selectedAnswer = null;

        $("quizResult")
            .classList.add("hidden");

        $("quizContainer")
            .classList.remove("hidden");

        renderQuizQuestion();

    } catch (error) {

        showToast(
            error.message ||
            "Unable to generate quiz."
        );

    } finally {

        button.disabled = false;
        button.textContent =
            "Generate 10 Questions";
    }
}

function renderQuizQuestion() {
    const questions =
        quizData.questions;

    const question =
        questions[currentQuizIndex];

    selectedAnswer = null;

    $("currentQuestion").textContent =
        currentQuizIndex + 1;

    $("quizProgress").style.width =
        `${((currentQuizIndex + 1) / 10) * 100}%`;

    $("quizQuestion").textContent =
        question.question ||
        question.text ||
        "";

    const options =
        question.options || [];

    const optionsContainer =
        $("quizOptions");

    optionsContainer.innerHTML = "";

    options.forEach((option, index) => {

        const button =
            document.createElement("button");

        button.className =
            "quiz-option";

        button.textContent =
            option;

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(".quiz-option")
                    .forEach(item => {
                        item.classList.remove(
                            "selected"
                        );
                    });

                button.classList.add(
                    "selected"
                );

                selectedAnswer =
                    index;

                $("nextQuestionButton")
                    .disabled = false;
            }
        );

        optionsContainer.appendChild(
            button
        );
    });

    $("nextQuestionButton").textContent =
        currentQuizIndex === 9
            ? "Finish Quiz ✓"
            : "Next Question →";

    $("nextQuestionButton").disabled =
        true;
}

async function nextQuizQuestion() {
    if (selectedAnswer === null) {
        return;
    }

    const question =
        quizData.questions[currentQuizIndex];

    const correctAnswer =
        question.answer ??
        question.correct_answer ??
        question.correctAnswer;

    if (
        typeof correctAnswer === "number" &&
        selectedAnswer === correctAnswer
    ) {
        quizData.score =
            (quizData.score || 0) + 1;
    } else if (
        typeof correctAnswer === "string"
    ) {

        const selectedOption =
            question.options[
                selectedAnswer
            ];

        if (
            selectedOption ===
            correctAnswer
        ) {
            quizData.score =
                (quizData.score || 0) + 1;
        }
    }

    if (currentQuizIndex < 9) {

        currentQuizIndex += 1;

        renderQuizQuestion();

        return;
    }

    await finishQuiz();
}

async function finishQuiz() {
    const score =
        quizData.score || 0;

    const quizId =
        quizData.quiz_id ||
        quizData.id;

    $("quizContainer")
        .classList.add("hidden");

    const result =
        $("quizResult");

    result.classList.remove("hidden");

    result.innerHTML = `
        <div class="eyebrow">
            QUIZ COMPLETE
        </div>

        <div class="result-score">
            ${score}/10
        </div>

        <h3>
            You completed all 10 questions!
        </h3>

        <button
            class="primary-button"
            onclick="generateQuiz()"
        >
            Try Another Quiz
        </button>
    `;

    if (quizId) {

        try {

            await apiFetch(
                "/api/quiz/score",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        quiz_id:
                            Number(quizId),

                        score: score,

                        user_id:
                            "default"
                    })
                }
            );

        } catch (error) {
            console.error(
                "Score save error:",
                error
            );
        }
    }

    await loadStats();
}


/* =====================================================
   STUDY PLANS
===================================================== */

function setupStudyPlan() {
    $("savePlanButton")?.addEventListener(
        "click",
        saveStudyPlan
    );

    $("cancelEditButton")?.addEventListener(
        "click",
        cancelPlanEdit
    );
}

function getPlanFormData() {
    const title =
        $("planTitle").value.trim() ||
        "My Study Plan";

    const days =
        Number(
            $("planDays").value
        );

    const hours =
        Number(
            $("planHours").value
        );

    const startTime =
        $("planStartTime").value ||
        "18:00";

    const subjects =
        $("planSubjects")
            .value
            .split(",")
            .map(item => item.trim())
            .filter(Boolean);

    return {
        title,
        days,
        hours_per_day: hours,
        start_time: startTime,
        subjects,
        user_id: "default"
    };
}

async function saveStudyPlan() {
    const status =
        $("planStatus");

    const data =
        getPlanFormData();

    if (!data.days || data.days < 1) {
        showToast(
            "Enter at least 1 day."
        );
        return;
    }

    if (
        !data.hours_per_day ||
        data.hours_per_day <= 0
    ) {
        showToast(
            "Enter study hours."
        );
        return;
    }

    if (!data.subjects.length) {
        showToast(
            "Enter at least one subject."
        );
        return;
    }

    const button =
        $("savePlanButton");

    button.disabled = true;

    status.textContent =
        editingPlanId
            ? "Updating plan..."
            : "Creating plan...";

    try {

        let response;

        if (editingPlanId) {

            response =
                await apiFetch(
                    `/api/study-plan/${editingPlanId}`,
                    {
                        method: "PUT",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify(data)
                    }
                );

        } else {

            response =
                await apiFetch(
                    "/api/study-plan",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify(data)
                    }
                );
        }

        showToast(
            editingPlanId
                ? "Study plan updated!"
                : "Study plan created!"
        );

        status.textContent =
            "Saved successfully.";

        cancelPlanEdit();

        await loadPlans();
        await loadStats();

    } catch (error) {

        status.textContent =
            error.message;

        showToast(
            "Could not save study plan."
        );

    } finally {

        button.disabled = false;
    }
}

async function loadPlans() {
    const list =
        $("plansList");

    if (!list) return;

    list.innerHTML =
        `<div class="empty">Loading plans...</div>`;

    try {

        const data =
            await apiFetch(
                "/api/study-plans"
            );

        plans =
            Array.isArray(data)
                ? data
                : data.plans || [];

        renderPlans();

    } catch (error) {

        list.innerHTML =
            `<div class="empty">
                Unable to load study plans.
            </div>`;

        console.error(error);
    }
}

function renderPlans() {
    const list =
        $("plansList");

    if (!plans.length) {

        list.innerHTML = `
            <div class="empty">
                No study plans yet.
                Create your first hourly plan.
            </div>
        `;

        return;
    }

    list.innerHTML =
        plans.map(renderPlanCard).join("");
}

function renderPlanCard(plan) {
    const sessions =
        plan.sessions || [];

    const subjects =
        Array.isArray(plan.subjects)
            ? plan.subjects.join(", ")
            : plan.subjects || "";

    let scheduleHTML = "";

    if (sessions.length) {

        scheduleHTML =
            sessions.map(day => {

                const daySessions =
                    day.sessions || [];

                return `
                    <div class="day-card">

                        <h4>
                            Day ${escapeHTML(day.day)}
                            ${
                                day.total_study_hours
                                    ? ` • ${escapeHTML(
                                        day.total_study_hours
                                      )} hrs`
                                    : ""
                            }
                        </h4>

                        ${
                            daySessions.length
                                ? daySessions.map(
                                    session => {

                                        const isBreak =
                                            session.type === "break";

                                        return `
                                            <div class="session ${
                                                isBreak
                                                    ? "break"
                                                    : ""
                                            }">

                                                <div class="session-time">
                                                    ${escapeHTML(
                                                        session.start || ""
                                                    )}
                                                    -
                                                    ${escapeHTML(
                                                        session.end || ""
                                                    )}
                                                </div>

                                                <div class="session-subject">
                                                    ${
                                                        isBreak
                                                            ? "☕ Break"
                                                            : "📚 " +
                                                              escapeHTML(
                                                                  session.subject ||
                                                                  "Study"
                                                              )
                                                    }
                                                </div>

                                            </div>
                                        `;
                                    }
                                ).join("")
                                : `<div class="empty">
                                    No sessions.
                                  </div>`
                        }

                    </div>
                `;
            }).join("");
    }

    return `
        <div class="plan-card">

            <div class="plan-header">

                <div>

                    <h3>
                        ${escapeHTML(
                            plan.title ||
                            "Study Plan"
                        )}
                    </h3>

                    <div class="plan-meta">
                        ${escapeHTML(
                            plan.days || 0
                        )} days
                        •
                        ${escapeHTML(
                            plan.hours_per_day || 0
                        )} hours/day
                        •
                        Start:
                        ${escapeHTML(
                            plan.start_time || ""
                        )}
                    </div>

                    <div class="plan-meta">
                        Topics:
                        ${escapeHTML(subjects)}
                    </div>

                </div>

                <div class="plan-actions">

                    <button
                        class="small-button"
                        onclick="editPlan(${plan.id})"
                    >
                        Edit
                    </button>

                    <button
                        class="danger-button"
                        onclick="deletePlan(${plan.id})"
                    >
                        Delete
                    </button>

                </div>

            </div>

            ${scheduleHTML}

        </div>
    `;
}

async function editPlan(id) {
    try {

        const plan =
            await apiFetch(
                `/api/study-plan/${id}`
            );

        editingPlanId =
            plan.id;

        $("planFormTitle").textContent =
            "Edit study plan";

        $("planTitle").value =
            plan.title ||
            "My Study Plan";

        $("planDays").value =
            plan.days ||
            7;

        $("planHours").value =
            plan.hours_per_day ||
            3;

        $("planStartTime").value =
            plan.start_time ||
            "18:00";

        const subjects =
            Array.isArray(plan.subjects)
                ? plan.subjects.join(", ")
                : plan.subjects || "";

        $("planSubjects").value =
            subjects;

        $("savePlanButton").textContent =
            "Update Plan";

        $("cancelEditButton")
            .classList.remove("hidden");

        showSection("study-plan");

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    } catch (error) {

        showToast(
            "Could not load study plan."
        );
    }
}

function cancelPlanEdit() {
    editingPlanId = null;

    $("planFormTitle").textContent =
        "Create a study plan";

    $("savePlanButton").textContent =
        "Create Plan";

    $("cancelEditButton")
        .classList.add("hidden");

    $("planTitle").value =
        "My Study Plan";

    $("planDays").value =
        7;

    $("planHours").value =
        3;

    $("planStartTime").value =
        "18:00";

    $("planSubjects").value =
        "";

    $("planStatus").textContent =
        "";
}

async function deletePlan(id) {
    const confirmed =
        confirm(
            "Delete this study plan?"
        );

    if (!confirmed) return;

    try {

        await apiFetch(
            `/api/study-plan/${id}`,
            {
                method: "DELETE"
            }
        );

        showToast(
            "Study plan deleted."
        );

        await loadPlans();
        await loadStats();

    } catch (error) {

        showToast(
            error.message ||
            "Could not delete plan."
        );
    }
}


/* =====================================================
   HISTORY
===================================================== */

async function loadHistory() {
    await Promise.all([
        loadConversationHistory(),
        loadQuizHistory()
    ]);
}

async function loadConversationHistory() {
    const container =
        $("conversationHistory");

    if (!container) return;

    try {

        const data =
            await apiFetch(
                "/api/conversations"
            );

        const conversations =
            Array.isArray(data)
                ? data
                : data.conversations || [];

        if (!conversations.length) {

            container.innerHTML = `
                <div class="empty">
                    No conversations yet.
                </div>
            `;

            return;
        }

        container.innerHTML =
            conversations.map(item => `
                <div class="history-item">

                    <strong>
                        ${escapeHTML(
                            item.question ||
                            "Question"
                        )}
                    </strong>

                    <div>
                        ${escapeHTML(
                            item.answer ||
                            ""
                        )}
                    </div>

                    <small>
                        ${escapeHTML(
                            formatDate(
                                item.created_at
                            )
                        )}
                    </small>

                </div>
            `).join("");

    } catch (error) {

        container.innerHTML =
            `<div class="empty">
                Unable to load conversations.
            </div>`;
    }
}

async function loadQuizHistory() {
    const container =
        $("quizHistory");

    if (!container) return;

    try {

        const data =
            await apiFetch(
                "/api/quiz/history"
            );

        const history =
            Array.isArray(data)
                ? data
                : data.history || [];

        if (!history.length) {

            container.innerHTML = `
                <div class="empty">
                    No quiz scores yet.
                </div>
            `;

            return;
        }

        container.innerHTML =
            history.map(item => {

                const score =
                    item.score ?? 0;

                const total =
                    item.total ?? 10;

                return `
                    <div class="history-item">

                        <strong>
                            Quiz
                        </strong>

                        <span class="score-badge">
                            ${escapeHTML(score)}
                            /
                            ${escapeHTML(total)}
                        </span>

                        <small>
                            ${escapeHTML(
                                formatDate(
                                    item.created_at
                                )
                            )}
                        </small>

                    </div>
                `;
            }).join("");

    } catch (error) {

        container.innerHTML =
            `<div class="empty">
                Unable to load quiz history.
            </div>`;
    }
}


/* =====================================================
   INITIALIZE
===================================================== */

async function initializeApp() {

    loadTheme();

    loadStreak();

    setupNavigation();

    setupUpload();

    setupAsk();

    setupQuiz();

    setupStudyPlan();

    $("themeButton")?.addEventListener(
        "click",
        toggleTheme
    );

    await loadStats();

    await loadMaterials();

    await loadPlans();

    await loadHistory();
}

document.addEventListener(
    "DOMContentLoaded",
    initializeApp
);