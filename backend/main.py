import os
import re
import json
import random
import sqlite3
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pypdf import PdfReader
from PIL import Image
import pytesseract


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

DATABASE_FOLDER = os.path.join(
    BASE_DIR,
    "database"
)

FRONTEND_FOLDER = os.path.join(
    BASE_DIR,
    "frontend"
)

DATABASE_PATH = os.path.join(
    DATABASE_FOLDER,
    "study_assistant.db"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    DATABASE_FOLDER,
    exist_ok=True
)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="AI Study Assistant",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn


def column_exists(
    conn,
    table_name,
    column_name
):

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        column["name"] == column_name
        for column in columns
    )


def add_column_if_missing(
    conn,
    table_name,
    column_name,
    column_definition
):

    if not column_exists(
        conn,
        table_name,
        column_name
    ):

        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


def init_database():

    conn = get_db()

    # =====================================================
    # MATERIALS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            material_type TEXT DEFAULT 'unknown',
            content TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)

    add_column_if_missing(
        conn,
        "materials",
        "material_type",
        "TEXT DEFAULT 'unknown'"
    )


    # =====================================================
    # CONVERSATIONS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    add_column_if_missing(
        conn,
        "conversations",
        "user_id",
        "TEXT DEFAULT 'default'"
    )


    # =====================================================
    # QUIZZES
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            material_id INTEGER,
            questions TEXT NOT NULL,
            score INTEGER,
            total INTEGER DEFAULT 10,
            created_at TEXT NOT NULL
        )
    """)

    add_column_if_missing(
        conn,
        "quizzes",
        "user_id",
        "TEXT DEFAULT 'default'"
    )

    add_column_if_missing(
        conn,
        "quizzes",
        "total",
        "INTEGER DEFAULT 10"
    )


    # =====================================================
    # STUDY PLANS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            title TEXT NOT NULL,
            days INTEGER NOT NULL,
            hours_per_day REAL NOT NULL,
            start_time TEXT DEFAULT '18:00',
            subjects TEXT NOT NULL,
            sessions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    add_column_if_missing(
        conn,
        "study_plans",
        "user_id",
        "TEXT DEFAULT 'default'"
    )

    add_column_if_missing(
        conn,
        "study_plans",
        "start_time",
        "TEXT DEFAULT '18:00'"
    )

    add_column_if_missing(
        conn,
        "study_plans",
        "updated_at",
        "TEXT"
    )

    # Fix old records where updated_at is NULL
    conn.execute("""
        UPDATE study_plans
        SET updated_at = created_at
        WHERE updated_at IS NULL
    """)

    conn.commit()
    conn.close()


init_database()


# =========================================================
# MODELS
# =========================================================

class AskRequest(BaseModel):

    question: str

    material_id: Optional[int] = None

    user_id: str = "default"


class QuizScoreRequest(BaseModel):

    quiz_id: int

    score: int = Field(
        ge=0,
        le=10
    )

    user_id: str = "default"


class StudyPlanRequest(BaseModel):

    title: str = "My Study Plan"

    days: int = Field(
        ge=1,
        le=365
    )

    hours_per_day: float = Field(
        gt=0,
        le=24
    )

    start_time: str = "18:00"

    subjects: list[str]

    user_id: str = "default"


class StudyPlanUpdateRequest(BaseModel):

    title: str = "My Study Plan"

    days: int = Field(
        ge=1,
        le=365
    )

    hours_per_day: float = Field(
        gt=0,
        le=24
    )

    start_time: str = "18:00"

    subjects: list[str]

    user_id: str = "default"


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(text: str):

    text = text.replace(
        "\x00",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def split_sentences(text: str):

    text = clean_text(text)

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= 35
    ]


def tokenize(text):

    return set(
        re.findall(
            r"[a-zA-Z]{3,}",
            text.lower()
        )
    )


def get_keywords(
    text,
    limit=30
):

    words = re.findall(
        r"[a-zA-Z]{4,}",
        text.lower()
    )

    stop_words = {
        "that",
        "this",
        "with",
        "from",
        "which",
        "their",
        "there",
        "these",
        "those",
        "about",
        "would",
        "could",
        "should",
        "where",
        "when",
        "what",
        "into",
        "have",
        "been",
        "were",
        "they",
        "them",
        "than",
        "then",
        "also",
        "more",
        "some",
        "such",
        "other",
        "only",
        "very",
        "each",
        "because",
        "while",
        "your",
        "you",
        "will",
        "using",
        "used",
        "over",
        "under",
        "between",
        "after",
        "before",
        "through",
        "during",
        "being",
        "their",
        "ours",
        "ourselves"
    }

    frequency = {}

    for word in words:

        if word in stop_words:
            continue

        frequency[word] = (
            frequency.get(
                word,
                0
            ) + 1
        )

    sorted_words = sorted(
        frequency,
        key=frequency.get,
        reverse=True
    )

    return sorted_words[:limit]


# =========================================================
# TIME HELPERS
# =========================================================

def parse_time(time_string):

    try:

        hour, minute = map(
            int,
            time_string.split(":")
        )

        if not (
            0 <= hour <= 23
            and
            0 <= minute <= 59
        ):
            raise ValueError

        return (
            hour * 60
            + minute
        )

    except Exception:

        return 18 * 60


def validate_time(time_string):

    if not re.match(
        r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        time_string
    ):
        raise HTTPException(
            status_code=400,
            detail="Start time must use HH:MM format."
        )


def format_time(minutes):

    minutes = minutes % (
        24 * 60
    )

    hour = minutes // 60

    minute = minutes % 60

    suffix = "AM"

    if hour >= 12:
        suffix = "PM"

    display_hour = hour % 12

    if display_hour == 0:
        display_hour = 12

    return (
        f"{display_hour}:"
        f"{minute:02d} "
        f"{suffix}"
    )


# =========================================================
# STUDY PLAN GENERATOR
# =========================================================

def build_study_sessions(
    days,
    hours_per_day,
    start_time,
    subjects
):

    if not subjects:

        subjects = [
            "General Revision"
        ]

    total_minutes = int(
        round(
            hours_per_day * 60
        )
    )

    if total_minutes < 30:

        total_minutes = 30

    sessions = []

    # Choose block length based on
    # the amount of study time.
    if total_minutes <= 60:

        block_length = total_minutes

    elif total_minutes <= 120:

        block_length = 50

    else:

        block_length = 60

    for day_number in range(
        1,
        days + 1
    ):

        remaining = total_minutes

        current_time = parse_time(
            start_time
        )

        subject_index = (
            (day_number - 1)
            % len(subjects)
        )

        day_sessions = []

        while remaining > 0:

            session_length = min(
                block_length,
                remaining
            )

            subject = subjects[
                subject_index
                % len(subjects)
            ]

            day_sessions.append({

                "type": "study",

                "subject": subject,

                "start": format_time(
                    current_time
                ),

                "end": format_time(
                    current_time
                    + session_length
                ),

                "minutes": session_length,

                "hours": round(
                    session_length / 60,
                    2
                )
            })

            current_time += (
                session_length
            )

            remaining -= (
                session_length
            )

            subject_index += 1

            # Add a break between
            # study blocks.
            if remaining > 0:

                break_length = min(
                    15,
                    remaining
                )

                day_sessions.append({

                    "type": "break",

                    "subject": "Break",

                    "start": format_time(
                        current_time
                    ),

                    "end": format_time(
                        current_time
                        + break_length
                    ),

                    "minutes": break_length,

                    "hours": round(
                        break_length / 60,
                        2
                    )
                })

                current_time += (
                    break_length
                )

        sessions.append({

            "day": day_number,

            "total_study_hours":
                round(
                    total_minutes / 60,
                    2
                ),

            "sessions":
                day_sessions
        })

    return sessions


# =========================================================
# QUIZ HELPERS
# =========================================================

def choose_distractors(
    answer,
    keywords
):

    choices = [
        word
        for word in keywords
        if word.lower()
        != answer.lower()
    ]

    random.shuffle(
        choices
    )

    selected = choices[:3]

    while len(selected) < 3:

        selected.append(
            f"Option {len(selected) + 1}"
        )

    return selected


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "app": "AI Study Assistant",
        "version": "3.0.0"
    }


# =========================================================
# STATS
# =========================================================

@app.get("/api/stats")
def get_stats(
    user_id: str = "default"
):

    conn = get_db()

    materials = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM materials
        """
    ).fetchone()["count"]

    conversations = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM conversations
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["count"]

    quizzes = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM quizzes
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["count"]

    plans = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM study_plans
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["count"]

    conn.close()

    return {
        "materials": materials,
        "conversations": conversations,
        "quizzes": quizzes,
        "plans": plans
    }


# =========================================================
# UPLOAD
# =========================================================

@app.post("/api/upload")
async def upload_material(
    file: UploadFile = File(...)
):

    filename = (
        file.filename
        or "uploaded_file"
    )

    extension = os.path.splitext(
        filename
    )[1].lower()

    allowed_extensions = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp"
    }

    if extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload a PDF "
                "or image file."
            )
        )

    file_bytes = await file.read()

    if not file_bytes:

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    safe_filename = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        filename
    )

    saved_filename = (
        datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )
        + "_"
        + safe_filename
    )

    file_path = os.path.join(
        UPLOAD_FOLDER,
        saved_filename
    )

    with open(
        file_path,
        "wb"
    ) as output_file:

        output_file.write(
            file_bytes
        )

    extracted_text = ""

    material_type = "image"

    try:

        if extension == ".pdf":

            material_type = "pdf"

            reader = PdfReader(
                file_path
            )

            pages = []

            for page in reader.pages:

                page_text = (
                    page.extract_text()
                    or ""
                )

                if page_text.strip():

                    pages.append(
                        page_text
                    )

            extracted_text = "\n".join(
                pages
            )

        else:

            image = Image.open(
                file_path
            )

            # Improve OCR for common
            # photographed notes.
            if image.mode != "RGB":

                image = image.convert(
                    "RGB"
                )

            extracted_text = (
                pytesseract.image_to_string(
                    image
                )
            )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not read the file: "
                f"{error}"
            )
        )

    extracted_text = clean_text(
        extracted_text
    )

    if not extracted_text:

        raise HTTPException(
            status_code=400,
            detail=(
                "No readable text was found. "
                "For photos, make sure the "
                "text is clear and readable."
            )
        )

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO materials
        (
            filename,
            material_type,
            content,
            uploaded_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            filename,
            material_type,
            extracted_text,
            datetime.now().isoformat()
        )
    )

    material_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {

        "message":
            "Material uploaded successfully.",

        "material_id":
            material_id,

        "filename":
            filename,

        "material_type":
            material_type,

        "characters":
            len(extracted_text)
    }


# =========================================================
# MATERIALS
# =========================================================

@app.get("/api/materials")
def get_materials():

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            id,
            filename,
            material_type,
            uploaded_at,
            LENGTH(content) AS characters
        FROM materials
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


@app.get("/api/material/{material_id}")
def get_material(
    material_id: int
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM materials
        WHERE id = ?
        """,
        (material_id,)
    ).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Material not found."
        )

    return dict(row)


@app.delete("/api/material/{material_id}")
def delete_material(
    material_id: int
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM materials
        WHERE id = ?
        """,
        (material_id,)
    ).fetchone()

    if not row:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Material not found."
        )

    conn.execute(
        """
        DELETE FROM materials
        WHERE id = ?
        """,
        (material_id,)
    )

    conn.commit()
    conn.close()

    return {
        "message":
            "Material deleted successfully."
    }


# =========================================================
# ASK AI
# =========================================================

@app.post("/api/ask")
def ask_question(
    request: AskRequest
):

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    conn = get_db()

    if request.material_id:

        material = conn.execute(
            """
            SELECT *
            FROM materials
            WHERE id = ?
            """,
            (request.material_id,)
        ).fetchone()

    else:

        material = conn.execute(
            """
            SELECT *
            FROM materials
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    if not material:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload study "
                "material first."
            )
        )

    question_words = tokenize(
        question
    )

    sentences = split_sentences(
        material["content"]
    )

    scored_sentences = []

    for sentence in sentences:

        sentence_words = tokenize(
            sentence
        )

        overlap = len(
            question_words
            & sentence_words
        )

        if overlap > 0:

            scored_sentences.append(
                (
                    overlap,
                    sentence
                )
            )

    scored_sentences.sort(
        reverse=True,
        key=lambda item: item[0]
    )

    if scored_sentences:

        best_sentences = [
            item[1]
            for item in
            scored_sentences[:3]
        ]

        answer = " ".join(
            best_sentences
        )

    else:

        answer = (
            "I couldn't find a direct "
            "answer in the uploaded "
            "material. Try asking using "
            "keywords from your notes."
        )

    conn.execute(
        """
        INSERT INTO conversations
        (
            user_id,
            question,
            answer,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request.user_id,
            question,
            answer,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()

    return {
        "question": question,
        "answer": answer
    }


# =========================================================
# CONVERSATION HISTORY
# =========================================================

@app.get("/api/conversations")
def get_conversations(
    user_id: str = "default"
):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 100
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# QUIZ
# =========================================================

@app.get("/api/quiz")
def generate_quiz(
    material_id: Optional[int] = None,
    user_id: str = "default"
):

    conn = get_db()

    if material_id:

        material = conn.execute(
            """
            SELECT *
            FROM materials
            WHERE id = ?
            """,
            (material_id,)
        ).fetchone()

    else:

        material = conn.execute(
            """
            SELECT *
            FROM materials
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    if not material:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload study "
                "material first."
            )
        )

    text = material["content"]

    sentences = split_sentences(
        text
    )

    keywords = get_keywords(
        text,
        50
    )

    if len(sentences) < 10:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "I need more study material "
                "to create exactly 10 questions. "
                "Please upload a longer document."
            )
        )

    random.shuffle(
        sentences
    )

    questions = []

    used_questions = set()

    # =====================================================
    # PRIMARY QUESTION GENERATION
    # =====================================================

    for sentence in sentences:

        if len(questions) >= 10:
            break

        sentence_words = re.findall(
            r"\b[A-Za-z]{4,}\b",
            sentence
        )

        candidates = [
            word
            for word in sentence_words
            if word.lower()
            in keywords
        ]

        if not candidates:
            continue

        answer = max(
            candidates,
            key=len
        )

        question_text = re.sub(
            rf"\b{re.escape(answer)}\b",
            "_____",
            sentence,
            count=1,
            flags=re.IGNORECASE
        )

        if (
            question_text
            in used_questions
        ):
            continue

        used_questions.add(
            question_text
        )

        distractors = choose_distractors(
            answer,
            keywords
        )

        options = [
            answer,
            *distractors
        ]

        random.shuffle(
            options
        )

        questions.append({

            "question":
                question_text,

            "options":
                options,

            "answer":
                answer
        })


    # =====================================================
    # FALLBACK
    # =====================================================

    if len(questions) < 10:

        for sentence in sentences:

            if len(questions) >= 10:
                break

            question_text = (
                "Which statement is "
                "supported by the material?"
            )

            question_text += (
                f" Question "
                f"{len(questions) + 1}"
            )

            questions.append({

                "question":
                    question_text,

                "options": [
                    "Correct according to the material",
                    "Not stated in the material",
                    "Opposite of the material",
                    "Unrelated information"
                ],

                "answer":
                    "Correct according to the material"
            })


    if len(questions) < 10:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to generate "
                "exactly 10 questions."
            )
        )

    questions = questions[:10]

    cursor = conn.execute(
        """
        INSERT INTO quizzes
        (
            user_id,
            material_id,
            questions,
            score,
            total,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            material["id"],
            json.dumps(
                questions
            ),
            None,
            10,
            datetime.now().isoformat()
        )
    )

    quiz_id = cursor.lastrowid

    conn.commit()
    conn.close()

    public_questions = []

    for question in questions:

        public_questions.append({

            "question":
                question["question"],

            "options":
                question["options"]
        })

    return {

        "quiz_id":
            quiz_id,

        "material_id":
            material["id"],

        "total":
            10,

        "questions":
            public_questions
    }


# =========================================================
# QUIZ SCORE
# =========================================================

@app.post("/api/quiz/score")
def save_quiz_score(
    request: QuizScoreRequest
):

    conn = get_db()

    quiz = conn.execute(
        """
        SELECT *
        FROM quizzes
        WHERE id = ?
        AND user_id = ?
        """,
        (
            request.quiz_id,
            request.user_id
        )
    ).fetchone()

    if not quiz:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Quiz not found."
        )

    conn.execute(
        """
        UPDATE quizzes
        SET score = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            request.score,
            request.quiz_id,
            request.user_id
        )
    )

    conn.commit()
    conn.close()

    return {

        "message":
            "Score saved.",

        "score":
            request.score,

        "total":
            10
    }


# =========================================================
# QUIZ HISTORY
# =========================================================

@app.get("/api/quiz/history")
def get_quiz_history(
    user_id: str = "default"
):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            id,
            material_id,
            score,
            total,
            created_at
        FROM quizzes
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 100
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# STUDY PLAN VALIDATION
# =========================================================

def validate_study_plan(
    days,
    hours_per_day,
    start_time,
    subjects
):

    if days < 1 or days > 365:

        raise HTTPException(
            status_code=400,
            detail=(
                "Days must be between "
                "1 and 365."
            )
        )

    if (
        hours_per_day <= 0
        or
        hours_per_day > 24
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Hours per day must be "
                "greater than 0 and "
                "cannot exceed 24."
            )
        )

    validate_time(
        start_time
    )

    cleaned_subjects = [
        subject.strip()
        for subject in subjects
        if subject
        and subject.strip()
    ]

    if not cleaned_subjects:

        raise HTTPException(
            status_code=400,
            detail=(
                "Please enter at least "
                "one subject."
            )
        )

    return cleaned_subjects


# =========================================================
# CREATE STUDY PLAN
# =========================================================

@app.post("/api/study-plan")
def create_study_plan(
    request: StudyPlanRequest
):

    subjects = validate_study_plan(
        request.days,
        request.hours_per_day,
        request.start_time,
        request.subjects
    )

    sessions = build_study_sessions(
        request.days,
        request.hours_per_day,
        request.start_time,
        subjects
    )

    now = datetime.now().isoformat()

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO study_plans
        (
            user_id,
            title,
            days,
            hours_per_day,
            start_time,
            subjects,
            sessions,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.user_id,
            request.title.strip()
            or "My Study Plan",
            request.days,
            request.hours_per_day,
            request.start_time,
            json.dumps(subjects),
            json.dumps(sessions),
            now,
            now
        )
    )

    plan_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {

        "id":
            plan_id,

        "title":
            request.title.strip()
            or "My Study Plan",

        "days":
            request.days,

        "hours_per_day":
            request.hours_per_day,

        "start_time":
            request.start_time,

        "subjects":
            subjects,

        "sessions":
            sessions
    }


# =========================================================
# GET ALL STUDY PLANS
# =========================================================

@app.get("/api/study-plans")
def get_study_plans(
    user_id: str = "default"
):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM study_plans
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    result = []

    for row in rows:

        item = dict(row)

        try:

            item["subjects"] = json.loads(
                item["subjects"]
            )

        except Exception:

            item["subjects"] = []

        try:

            item["sessions"] = json.loads(
                item["sessions"]
            )

        except Exception:

            item["sessions"] = []

        result.append(
            item
        )

    return result


# =========================================================
# GET ONE STUDY PLAN
# =========================================================

@app.get("/api/study-plan/{plan_id}")
def get_study_plan(
    plan_id: int,
    user_id: str = "default"
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM study_plans
        WHERE id = ?
        AND user_id = ?
        """,
        (
            plan_id,
            user_id
        )
    ).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Study plan not found."
        )

    item = dict(row)

    item["subjects"] = json.loads(
        item["subjects"]
    )

    item["sessions"] = json.loads(
        item["sessions"]
    )

    return item


# =========================================================
# UPDATE STUDY PLAN
# =========================================================

@app.put("/api/study-plan/{plan_id}")
def update_study_plan(
    plan_id: int,
    request: StudyPlanUpdateRequest
):

    subjects = validate_study_plan(
        request.days,
        request.hours_per_day,
        request.start_time,
        request.subjects
    )

    # IMPORTANT:
    # Whenever the user changes hours,
    # days, subjects, or start time,
    # the entire hourly schedule is
    # regenerated.

    sessions = build_study_sessions(
        request.days,
        request.hours_per_day,
        request.start_time,
        subjects
    )

    now = datetime.now().isoformat()

    conn = get_db()

    cursor = conn.execute(
        """
        UPDATE study_plans
        SET
            title = ?,
            days = ?,
            hours_per_day = ?,
            start_time = ?,
            subjects = ?,
            sessions = ?,
            updated_at = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            request.title.strip()
            or "My Study Plan",

            request.days,

            request.hours_per_day,

            request.start_time,

            json.dumps(
                subjects
            ),

            json.dumps(
                sessions
            ),

            now,

            plan_id,

            request.user_id
        )
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:

        raise HTTPException(
            status_code=404,
            detail=(
                "Study plan not found "
                "for this user."
            )
        )

    return {

        "message":
            "Study plan updated.",

        "id":
            plan_id,

        "title":
            request.title.strip()
            or "My Study Plan",

        "days":
            request.days,

        "hours_per_day":
            request.hours_per_day,

        "start_time":
            request.start_time,

        "subjects":
            subjects,

        "sessions":
            sessions
    }


# =========================================================
# DELETE STUDY PLAN
# =========================================================

@app.delete("/api/study-plan/{plan_id}")
def delete_study_plan(
    plan_id: int,
    user_id: str = "default"
):

    conn = get_db()

    cursor = conn.execute(
        """
        DELETE FROM study_plans
        WHERE id = ?
        AND user_id = ?
        """,
        (
            plan_id,
            user_id
        )
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:

        raise HTTPException(
            status_code=404,
            detail="Study plan not found."
        )

    return {
        "message":
            "Study plan deleted."
    }


# =========================================================
# FRONTEND
# =========================================================

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(
        os.path.join(
            FRONTEND_FOLDER,
            "index.html"
        )
    )


if os.path.isdir(FRONTEND_FOLDER):

    app.mount(
        "/",
        StaticFiles(
            directory=FRONTEND_FOLDER,
            html=True
        ),
        name="frontend"
    )
   
