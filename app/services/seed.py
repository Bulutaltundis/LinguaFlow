from sqlmodel import Session, select

from app.models.course import Course
from app.models.lesson import Unit, Lesson, Question
from app.models.shop import ShopItem
from app.models.reward import Chest


def seed_database(session: Session):
    if not session.exec(select(Chest)).first():
        session.add_all([
            Chest(name="Ahşap Sandık", rarity="common", icon="📦", min_gems=15, max_gems=35),
            Chest(name="Gümüş Sandık", rarity="uncommon", icon="🧰", min_gems=30, max_gems=70),
            Chest(name="Altın Sandık", rarity="rare", icon="🎁", min_gems=60, max_gems=130),
            Chest(name="Kristal Sandık", rarity="epic", icon="💎", min_gems=120, max_gems=280),
            Chest(name="Efsane Sandık", rarity="legendary", icon="👑", min_gems=250, max_gems=600),
        ])
        session.commit()

    default_items = [
        ("Seri Dondurucu", "Bir gün aksasan bile serini korur.", "🧊", 80, "streak_freeze"),
        ("XP Boost", "2 saat boyunca ders XP'sini ikiye katlar.", "⚡", 120, "xp_boost"),
        ("Kalp Paketi", "5 ekstra can kazan.", "❤️", 60, "heart_pack"),
        ("Okyanus Teması", "Profilini mavi bir temayla özelleştir.", "🌊", 150, "theme"),
        ("Altın Taç", "Profilinde parlayan kozmetik rozeti göster.", "👑", 180, "cosmetic"),
    ]
    existing_names = {item.name for item in session.exec(select(ShopItem).where(ShopItem.class_id == None)).all()}
    missing = [ShopItem(name=n, description=d, icon=i, price=p, type=t) for n, d, i, p, t in default_items if n not in existing_names]
    if missing:
        session.add_all(missing)
        session.commit()

    existing_course = session.exec(
        select(Course)
    ).first()

    if existing_course:
        return

    course = Course(
        name="İngilizce",
        language="English",
        description="Sıfırdan İngilizce öğren.",
        icon="🇬🇧",
    )

    session.add(course)
    session.commit()
    session.refresh(course)

    # UNIT 1

    unit1 = Unit(
        course_id=course.id,
        title="Temeller",
        description="İlk İngilizce kelimelerin",
        order=1,
    )

    session.add(unit1)
    session.commit()
    session.refresh(unit1)

    # LESSON 1

    lesson1 = Lesson(
        unit_id=unit1.id,
        title="Temel Kelimeler",
        icon="📚",
        xp_reward=10,
        order=1,
    )

    session.add(lesson1)
    session.commit()
    session.refresh(lesson1)

    questions = [
        Question(
            lesson_id=lesson1.id,
            type="multiple_choice",
            prompt="'Hello' ne demektir?",
            answer="Merhaba",
            options="Merhaba|Güle güle|Teşekkürler|Lütfen",
            explanation="Hello = Merhaba",
            order=1,
        ),
        Question(
            lesson_id=lesson1.id,
            type="multiple_choice",
            prompt="'Apple' ne demektir?",
            answer="Elma",
            options="Armut|Elma|Portakal|Muz",
            explanation="Apple = Elma",
            order=2,
        ),
        Question(
            lesson_id=lesson1.id,
            type="translation",
            prompt="'Ben bir öğrenciyim.' cümlesini İngilizceye çevir.",
            answer="I am a student",
            explanation="I am a student = Ben bir öğrenciyim.",
            order=3,
        ),
        Question(
            lesson_id=lesson1.id,
            type="multiple_choice",
            prompt="'Thank you' ne demektir?",
            answer="Teşekkür ederim",
            options="Merhaba|Lütfen|Teşekkür ederim|Hoşça kal",
            explanation="Thank you = Teşekkür ederim.",
            order=4,
        ),
        Question(
            lesson_id=lesson1.id,
            type="fill_blank",
            prompt="I ___ Bulut.",
            answer="am",
            options="am|is|are|be",
            explanation="I am = Ben ...",
            order=5,
        ),
    ]

    session.add_all(questions)

    # LESSON 2

    lesson2 = Lesson(
        unit_id=unit1.id,
        title="Selamlaşma",
        icon="👋",
        xp_reward=15,
        order=2,
    )

    session.add(lesson2)
    session.commit()
    session.refresh(lesson2)

    session.add_all([
        Question(
            lesson_id=lesson2.id,
            type="multiple_choice",
            prompt="'Good morning' ne demektir?",
            answer="Günaydın",
            options="İyi geceler|Günaydın|İyi akşamlar|Hoşça kal",
            explanation="Good morning = Günaydın.",
            order=1,
        ),
        Question(
            lesson_id=lesson2.id,
            type="translation",
            prompt="'Nasılsın?' İngilizce nasıl söylenir?",
            answer="How are you",
            explanation="How are you? = Nasılsın?",
            order=2,
        ),
    ])

    # UNIT 2

    unit2 = Unit(
        course_id=course.id,
        title="Tanışma",
        description="Kendinden bahsetmeyi öğren.",
        order=2,
    )

    session.add(unit2)
    session.commit()
    session.refresh(unit2)

    lesson3 = Lesson(
        unit_id=unit2.id,
        title="Kendini Tanıt",
        icon="🙋",
        xp_reward=20,
        order=1,
    )

    session.add(lesson3)
    session.commit()
    session.refresh(lesson3)

    session.add_all([
        Question(
            lesson_id=lesson3.id,
            type="translation",
            prompt="'Benim adım Alex.' İngilizce nasıl söylenir?",
            answer="My name is Alex",
            explanation="My name is Alex.",
            order=1,
        ),
        Question(
            lesson_id=lesson3.id,
            type="multiple_choice",
            prompt="'I am 12 years old.' ne demektir?",
            answer="12 yaşındayım",
            options="12 yaşındayım|12 yaşındasın|12 yaşında|12 yaşında değilim",
            explanation="I am 12 years old = 12 yaşındayım.",
            order=2,
        ),
    ])

    session.commit()
