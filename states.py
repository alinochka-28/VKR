from vkbottle import BaseStateGroup

class TestStates(BaseStateGroup):
    WAITING_CONSENT = "waiting_consent"              # ожидание согласия на обработку ПД
    WAITING_AGE = "waiting_age"                      # ожидание ввода возраста
    WAITING_EMOTION_WILSON = "waiting_wilson"        # ожидание выбора человечка
    WAITING_EMOTION_WILSON_SUPPORT = "waiting_wilson_support"  # уточнение для 16 позиции
    WAITING_EMOTION_ECMES = "waiting_ecmes"          # ожидание выбора настроения
    WAITING_LURIA_INSTRUCTION = "luria_instruction"  # ожидание нажатия Дальше после инструкции
    WAITING_LURIA_WORDS1 = "luria_words1"            # первое запоминание слов
    WAITING_LURIA_WORDS2 = "luria_words2"            # повторение слов
    WAITING_RAVEN = "waiting_raven"                  # ожидание ответа на задание Равена
    WAITING_SCHULTE = "waiting_schulte"              # ожидание клика по таблице Шульте
    WAITING_LURIA_RECALL = "luria_recall"            # ожидание ввода вспомненных слов
    WAITING_SCHULTE_INSTRUCTION = "schulte_instruction"  # ожидание нажатия Дальше к Шульте
    WAITING_REPORT = "waiting_report"                # ожидание генерации отчёта
    WAITING_START_AFTER_AGE = "waiting_start_after_age"