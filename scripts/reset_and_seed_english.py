"""Replace all courses with a complete 3-unit English starter course.

Run from the project root:
    uv run python scripts/reset_and_seed_english.py

This script deletes courses, units, lessons, questions and their lesson
progress/attempt records. It keeps users, classrooms and memberships. Existing
classrooms are detached from the deleted course and can be assigned to the new
course from the teacher/admin UI.
"""

from dotenv import load_dotenv
from sqlmodel import Session, delete, select

load_dotenv()

from app.core.database import create_db_and_tables, engine
from app.models.attempt import QuestionAttempt
from app.models.classroom import Classroom
from app.models.course import Course
from app.models.lesson import Lesson, Question, Unit
from app.models.progress import UserProgress


UNITS = [
    (
        "Everyday Foundations",
        "Günlük hayatta kullanılan temel kelimeler ve ifadeler.",
        [
            ("Greetings", "hello", "merhaba", "Hello, my friend."),
            ("Introductions", "name", "isim", "My name is Alex."),
            ("People", "friend", "arkadaş", "My friend is kind."),
            ("Family", "mother", "anne", "My mother is at home."),
            ("Numbers", "three", "üç", "I have three books."),
            ("Colors", "blue", "mavi", "The sky is blue."),
            ("Days", "Monday", "Pazartesi", "Today is Monday."),
            ("Time", "morning", "sabah", "I study in the morning."),
            ("Places", "school", "okul", "I walk to school."),
            ("Daily Actions", "learn", "öğrenmek", "I learn English every day."),
        ],
    ),
    (
        "Useful Conversations",
        "Konuşma kurmak için gerekli günlük ifadeler.",
        [
            ("Polite Words", "please", "lütfen", "Please open the door."),
            ("Food", "water", "su", "I drink water."),
            ("Drinks", "coffee", "kahve", "She likes coffee."),
            ("Shopping", "price", "fiyat", "What is the price?"),
            ("Directions", "left", "sol", "Turn left here."),
            ("Transport", "train", "tren", "The train is fast."),
            ("Weather", "rainy", "yağmurlu", "It is rainy today."),
            ("Home", "kitchen", "mutfak", "The kitchen is clean."),
            ("School Life", "teacher", "öğretmen", "My teacher is helpful."),
            ("Hobbies", "music", "müzik", "I listen to music."),
        ],
    ),
    (
        "Building Sentences",
        "Cümle kurma, fiiller ve temel günlük konuşma.",
        [
            ("Common Verbs", "go", "gitmek", "I go home at five."),
            ("Have and Have Got", "book", "kitap", "I have a new book."),
            ("Likes", "like", "sevmek", "I like this song."),
            ("Present Simple", "work", "çalışmak", "They work every day."),
            ("Questions", "why", "neden", "Why are you late?"),
            ("Descriptions", "beautiful", "güzel", "This place is beautiful."),
            ("Clothes", "jacket", "ceket", "My jacket is black."),
            ("Body and Health", "head", "baş", "My head hurts."),
            ("Travel", "hotel", "otel", "The hotel is near the beach."),
            ("Review Challenge", "practice", "pratik yapmak", "I practice English every day."),
        ],
    ),
]


def options_for(items, answer, key_index):
    values = [item[key_index] for item in items if item[key_index] != answer]
    return "|".join([answer, *values[:3]])


def add_lesson(session, unit_id: int, lesson_order: int, title: str, word: str, meaning: str, sentence: str, items):
    lesson = Lesson(
        unit_id=unit_id,
        title=title,
        icon="📘",
        xp_reward=15,
        order=lesson_order,
    )
    session.add(lesson)
    session.flush()

    questions = [
        Question(
            lesson_id=lesson.id,
            type="multiple_choice",
            prompt=f"'{word}' ne demektir?",
            answer=meaning,
            options=options_for(items, meaning, 2),
            explanation=f"{word} = {meaning}",
            order=1,
        ),
        Question(
            lesson_id=lesson.id,
            type="multiple_choice",
            prompt=f"'{meaning}' kelimesinin İngilizcesi hangisidir?",
            answer=word,
            options=options_for(items, word, 1),
            explanation=f"{meaning} = {word}",
            order=2,
        ),
        Question(
            lesson_id=lesson.id,
            type="translation",
            prompt=f"Şu cümleyi İngilizceye çevir: {sentence}",
            answer=sentence,
            explanation=sentence,
            order=3,
        ),
        Question(
            lesson_id=lesson.id,
            type="fill_blank",
            prompt=f"Cümleyi tamamla: I practice ___.",
            answer=word,
            options=options_for(items, word, 1),
            explanation=f"Doğru kelime: {word}",
            order=4,
        ),
        Question(
            lesson_id=lesson.id,
            type="multiple_choice",
            prompt=f"'{word}' kelimesiyle ilgili doğru seçeneği bul.",
            answer=sentence,
            options="|".join([sentence, f"I do not know {word}.", f"{word} is not a word.", "This answer is incorrect."]),
            explanation=sentence,
            order=5,
        ),
        Question(
            lesson_id=lesson.id,
            type="translation",
            prompt=f"'{word}' kelimesini kullanarak kısa bir cümleyi çevir: {sentence}",
            answer=sentence,
            explanation=f"Örnek doğru cevap: {sentence}",
            order=6,
        ),
    ]
    session.add_all(questions)


def reset_and_seed():
    create_db_and_tables()
    with Session(engine) as session:
        # Keep the accounts and classrooms, but remove stale lesson references.
        old_lesson_ids = list(session.exec(select(Lesson.id)).all())
        if old_lesson_ids:
            session.exec(delete(QuestionAttempt).where(QuestionAttempt.lesson_id.in_(old_lesson_ids)))
            session.exec(delete(UserProgress).where(UserProgress.lesson_id.in_(old_lesson_ids)))
        session.exec(delete(Question))
        session.exec(delete(Lesson))
        session.exec(delete(Unit))
        session.exec(delete(Course))

        # Classrooms remain intact, but their deleted course relation is cleared.
        for classroom in session.exec(select(Classroom)).all():
            classroom.course_id = None
            session.add(classroom)

        for unit_order, (unit_title, unit_description, lessons) in enumerate(UNITS, start=1):
            course = None
            # One shared course, three units.
            if unit_order == 1:
                course = Course(
                    name="İngilizce Başlangıç",
                    language="English",
                    description="Günlük İngilizceyi temelden öğren.",
                    icon="🇬🇧",
                )
                session.add(course)
                session.flush()
            else:
                course = session.exec(select(Course).where(Course.name == "İngilizce Başlangıç")).one()

            unit = Unit(
                course_id=course.id,
                title=unit_title,
                description=unit_description,
                order=unit_order,
            )
            session.add(unit)
            session.flush()

            for lesson_order, (title, word, meaning, sentence) in enumerate(lessons, start=1):
                add_lesson(session, unit.id, lesson_order, title, word, meaning, sentence, lessons)

        session.commit()

        course = session.exec(select(Course).where(Course.name == "İngilizce Başlangıç")).one()
        units = session.exec(select(Unit).where(Unit.course_id == course.id)).all()
        lessons = session.exec(select(Lesson).where(Lesson.unit_id.in_([unit.id for unit in units]))).all()
        questions = session.exec(select(Question).where(Question.lesson_id.in_([lesson.id for lesson in lessons]))).all()
        print(f"Kurs yenilendi: {course.name} (id={course.id})")
        print(f"Ünite: {len(units)} | Ders: {len(lessons)} | Soru: {len(questions)}")


if __name__ == "__main__":
    reset_and_seed()
