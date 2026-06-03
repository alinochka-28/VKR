from typing import Dict, Optional


SCHULTE_TOTAL_NUMBERS = 25

EMOTION_MODIFIERS: Dict[str, Dict[str, float]] = {
    "радость": {
        "attention": 0.15,
        "perception": 0.10,
        "memory": 0.10,
        "thinking": 0.05,
        "imagination": 0.20,
    },
    "печаль": {
        "attention": -0.15,
        "perception": -0.05,
        "memory": -0.10,
        "thinking": -0.05,
        "imagination": -0.10,
    },
    "страх": {
        "attention": -0.20,
        "perception": -0.10,
        "memory": -0.15,
        "thinking": -0.20,
        "imagination": -0.05,
    },
    "гнев": {
        "attention": -0.10,
        "perception": -0.15,
        "memory": -0.05,
        "thinking": -0.10,
        "imagination": -0.20,
    },
    "доверие": {
        "attention": 0.05,
        "perception": 0.05,
        "memory": 0.10,
        "thinking": 0.05,
        "imagination": 0.05,
    },
    "отвращение": {
        "attention": -0.05,
        "perception": -0.10,
        "memory": -0.05,
        "thinking": -0.15,
        "imagination": -0.15,
    },
    "ожидание": {
        "attention": 0.10,
        "perception": 0.05,
        "memory": 0.05,
        "thinking": 0.10,
        "imagination": 0.10,
    },
    "удивление": {
        "attention": 0.05,
        "perception": 0.15,
        "memory": 0.05,
        "thinking": 0.05,
        "imagination": 0.15,
    },
}


def apply_emotion_modifier(
    scores: Dict[str, float],
    emotion_value: Optional[str],
) -> Dict[str, float]:
    if emotion_value is None:
        return dict(scores)

    modifiers = EMOTION_MODIFIERS.get(emotion_value.lower(), {})
    adjusted: Dict[str, float] = {}
    for key, value in scores.items():
        delta = modifiers.get(key, 0.0) * 10.0
        adjusted[key] = round(max(0.0, min(10.0, value + delta)), 1)
    return adjusted


def emotion_modifier_description(emotion_value: Optional[str]) -> str:
    if emotion_value is None:
        return "Эмоциональное состояние не учитывалось."

    mods = EMOTION_MODIFIERS.get(emotion_value.lower(), {})
    if not mods:
        return f"Для эмоции «{emotion_value}» нет данных о влиянии."

    parts = []
    for key, coeff in mods.items():
        label = {
            "attention": "Внимание",
            "perception": "Восприятие",
            "memory": "Память",
            "thinking": "Мышление",
            "imagination": "Воображение",
        }.get(key, key)
        sign = "+" if coeff > 0 else ""
        parts.append(f"{label}: {sign}{coeff * 10:.0f}%")

    return f"Влияние «{emotion_value}» на показатели: " + ", ".join(parts) + "."


def score_attention(errors: int) -> float:
    if errors is None or errors < 0:
        errors = 0
    raw = 10.0 - (errors / SCHULTE_TOTAL_NUMBERS) * 10.0
    return round(max(0.0, min(10.0, raw)), 1)


def _score_perception_child(time_sec: float) -> float:
    if time_sec < 40:
        return 10.0
    if time_sec < 50:
        return 8.0
    if time_sec < 60:
        return 6.0
    if time_sec < 90:
        return 4.0
    return 2.0


def _score_perception_adult(time_sec: float) -> float:
    if time_sec < 30:
        return 10.0
    if time_sec < 40:
        return 8.0
    if time_sec <= 60:
        return 6.0
    return 4.0


def score_perception(time_sec: float, age: int) -> float:
    if time_sec is None or time_sec <= 0:
        return 0.0
    if age is not None and age <= 14:
        return round(_score_perception_child(float(time_sec)), 1)
    return round(_score_perception_adult(float(time_sec)), 1)


LURIA_TOTAL_WORDS = 10


def score_memory(recalled: int) -> float:
    if recalled is None or recalled < 0:
        recalled = 0
    return round(min(LURIA_TOTAL_WORDS, max(0, recalled)) * 1.0, 1)


RAVEN_TOTAL_TASKS = 5
RAVEN_ACCURACY_WEIGHT = 0.7
RAVEN_SPEED_WEIGHT = 0.3


def _raven_accuracy_score(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (correct / total) * 10.0


def _raven_speed_score(avg_time_sec: float) -> float:
    if avg_time_sec is None or avg_time_sec <= 0:
        return 0.0
    if avg_time_sec <= 15:
        return 10.0
    if avg_time_sec <= 20:
        return 8.0
    if avg_time_sec <= 30:
        return 6.0
    if avg_time_sec <= 45:
        return 4.0
    return 2.0


def score_thinking(correct: int, total: int, total_time_sec: float) -> float:
    if total <= 0:
        return 0.0
    accuracy = _raven_accuracy_score(correct or 0, total)
    avg_time = (total_time_sec or 0.0) / total
    speed = _raven_speed_score(avg_time)
    final = accuracy * RAVEN_ACCURACY_WEIGHT + speed * RAVEN_SPEED_WEIGHT
    return round(max(0.0, min(10.0, final)), 1)


def score_imagination(correct: int, total: int, total_time_sec: float) -> float:
    return score_thinking(correct, total, total_time_sec)


def calculate_all_scores(
    *,
    schulte_errors: int,
    schulte_time_sec: float,
    luria_recalled: int,
    raven_correct: int,
    raven_total: int,
    raven_total_time_sec: float,
    age: int,
) -> Dict[str, float]:
    return {
        "attention": score_attention(schulte_errors),
        "perception": score_perception(schulte_time_sec, age),
        "memory": score_memory(luria_recalled),
        "thinking": score_thinking(raven_correct, raven_total, raven_total_time_sec),
        "imagination": score_imagination(
            raven_correct, raven_total, raven_total_time_sec
        ),
    }


def interpret_score(score: float) -> str:

    if score >= 9:
        return "Отлично"
    if score >= 6:
        return "Хорошо / выше среднего"
    if score >= 3:
        return "Ниже среднего"
    return "❌ Плохо"