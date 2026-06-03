from rapidfuzz import fuzz
from typing import List, Dict, Any

RAVEN_OPTIONS_COUNT = 6
RAVEN_TASKS_COUNT = 5


async def get_random_luria_words_from_db(session) -> List[str]:
    from sqlalchemy import select, func
    from models import WordBank

    stmt = select(WordBank.word).order_by(func.random()).limit(10)
    result = await session.execute(stmt)
    words = [row[0] for row in result.fetchall()]

    return words

def check_luria_recall(user_input: str, original_words: List[str]) -> List[str]:
    user_words = user_input.lower().split()
    recalled = []

    for original in original_words:
        for user_word in user_words:
            if fuzz.ratio(original.lower(), user_word) > 75:
                recalled.append(original)
                break

    return recalled


def get_raven_category(age: int) -> str:
    return "child" if age <= 14 else "adult"


async def get_random_raven_tasks_from_db(
        session, age: int, count: int = RAVEN_TASKS_COUNT
) -> List[Dict[str, Any]]:
    from sqlalchemy import select, func
    from models import RavenTest

    category = get_raven_category(age)

    stmt = (
        select(RavenTest)
        .where(RavenTest.category == category)
        .order_by(func.random())
        .limit(count)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "image": r.image,
            "answer": r.answer,
            "answers_count": r.answers_count,
            "category": r.category,
        }
        for r in rows
    ]


def check_raven_answer(correct_answer: int, user_answer: int) -> bool:
    return correct_answer == user_answer