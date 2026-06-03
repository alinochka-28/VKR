from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, Callback, GroupEventType, GroupTypes
from vkbottle import PhotoMessageUploader
from vkbottle import BaseStateGroup
from sqlalchemy import select

from services.radar_chart import save_radar_to_tempfile, save_radar_with_emotion_to_tempfile
from states import TestStates
from config.database import async_session
from models import User, TestSession
from services.cognitive_service import (
    get_random_luria_words_from_db,
    get_random_raven_tasks_from_db,
    check_raven_answer,
    RAVEN_OPTIONS_COUNT,
    RAVEN_TASKS_COUNT,
)
from services.scoring_service import (
    calculate_all_scores,
    apply_emotion_modifier,
    emotion_modifier_description,
    interpret_score,
)
from core.emotion_model import (
    get_emotion_with_support,
    ECMESLevel,
    WilsonSupportType,
    BaseEmotion,
)
import asyncio
import json
import logging
import os
import random
import time
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

WILSON_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "emotion",
    "wilson.jpg",
)

ECMES_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "emotion",
    "ECMES.jpg",
)

RAVEN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "raven",
)

user_sessions = {}
suggested_start = {}

ECMES_CODE_TO_INT = {
    "very_good": 1,
    "good": 2,
    "neutral": 3,
    "bad": 4,
    "very_bad": 5,
}

GREETINGS = [
    "Привет! Я когнитивный чат-бот.",
    "Здравствуйте! Хотите проверить свои когнитивные способности?",
    "Приветствую! Я помогу вам узнать больше о вашем мышлении.",
    "Здравствуйте! Готовы пройти тестирование?",
]


def _is_bot_message(message: Message) -> bool:
    return bool(message.from_id and message.from_id < 0)


def state_equals(state, expected: BaseStateGroup) -> bool:
    if state is None:
        return False
    expected_str = f"{type(expected).__name__}:{expected.value}"
    return state.state == expected_str


class UserTestData:
    def __init__(self, vk_id: int):
        self.vk_id = vk_id
        self.age = None
        self.wilson_position = None
        self.wilson_support = None
        self.ecmes_level = None
        self.luria_words = []
        self.luria_recalled = []
        self.luria_timer_task = None
        self.luria_words_message_id = None
        self.schulte_grid = []
        self.schulte_next_target = 1
        self.schulte_pressed = set()
        self.schulte_errors = 0
        self.schulte_start_time = None
        self.schulte_message_id = None
        self.schulte_attachments = []  # предзагруженные фото сетки: индекс = сколько найдено
        self.raven_tasks = []
        self.raven_index = 0
        self.raven_correct = 0
        self.raven_start_time = None
        self.raven_total_time = 0.0
        self.luria_recall_index = 0
        self.final_emotion = None


async def safe_delete_state(bot, peer_id):
    try:
        await bot.state_dispenser.delete(peer_id)
    except KeyError:
        pass


def cancel_user_tasks(user_sessions: dict, peer_id: int):
    test_data = user_sessions.get(peer_id)
    if not test_data:
        return
    task = getattr(test_data, "luria_timer_task", None)
    if task and not task.done():
        task.cancel()


def _extract_message_id(sent_response):
    if sent_response is None:
        return None
    if hasattr(sent_response, "message_id"):
        return sent_response.message_id
    if isinstance(sent_response, int):
        return sent_response
    return None


def build_wilson_keyboard() -> Keyboard:
    keyboard = Keyboard(one_time=True, inline=False)
    per_row = 5
    for i in range(1, 22):
        keyboard.add(Text(str(i), payload={"wilson_pos": i}))
        if i % per_row == 0 and i != 21:
            keyboard.row()
    return keyboard


SCHULTE_MAX_NUMBER = 25


def build_schulte_keyboard(grid: list) -> Keyboard:
    # 25 кнопок невозможно разместить на inline-клавиатуре (VK режет её
    # примерно на 10 кнопках). Поэтому используем ОБЫЧНУЮ клавиатуру
    # (до 40 кнопок, 5 в ряд) с CALLBACK-кнопками: при нажатии они НЕ
    # отправляют число в чат, а присылают боту message_event.
    keyboard = Keyboard(one_time=False, inline=False)
    grid_size = len(grid)
    per_row = 5

    for idx, number in enumerate(grid):
        keyboard.add(
            Callback(str(number), payload={"schulte_num": number}),
            color=KeyboardButtonColor.PRIMARY,
        )
        if (idx + 1) % per_row == 0 and (idx + 1) != grid_size:
            keyboard.row()

    return keyboard


def setup_handlers(bot: Bot):

    @bot.on.message(text="/start")
    async def start_command(message: Message):
        if _is_bot_message(message):
            return
        await send_start(message)

    @bot.on.message(payload={"cmd": "start_test"})
    async def handle_start_button(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id

        cancel_user_tasks(user_sessions, peer_id)
        user_sessions.pop(peer_id, None)
        await safe_delete_state(bot, peer_id)

        saved_age = None
        try:
            async with async_session() as session:
                stmt = select(User).where(User.vk_id == peer_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user is not None:
                    saved_age = user.age
        except Exception as e:
            logger.exception(f"❌ Не удалось прочитать пользователя {peer_id}: {e}")

        test_data = UserTestData(peer_id)
        user_sessions[peer_id] = test_data

        if saved_age is not None:
            test_data.age = saved_age
            keyboard = Keyboard(one_time=True, inline=False)
            keyboard.add(
                Text("▶️ Начать тестирование", payload={"cmd": "continue_test"}),
                color=KeyboardButtonColor.POSITIVE,
            )
            keyboard.row()
            keyboard.add(
                Text("✏️ Изменить возраст", payload={"cmd": "change_age"})
            )
            keyboard.row()
            keyboard.add(
                Text("👤 Личный кабинет", payload={"cmd": "profile"}),
                color=KeyboardButtonColor.SECONDARY,
            )

            await message.answer(
                f"Есть согласие на обработку персональных данных.\n\n"
                f"Сохранённый возраст: {saved_age}\n\n",
                keyboard=keyboard.get_json(),
            )
            await bot.state_dispenser.set(peer_id, TestStates.WAITING_START_AFTER_AGE)
            return

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_AGE)
        await message.answer("Сколько вам лет? (от 7 лет)")

    async def show_consent(message: Message, bot: Bot):
        peer_id = message.peer_id

        keyboard = Keyboard(one_time=True, inline=False)
        keyboard.add(
            Text("✅ Согласен(на)", payload={"cmd": "consent_accept"}),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
        keyboard.add(
            Text("❌ Отказаться", payload={"cmd": "consent_decline"}),
            color=KeyboardButtonColor.NEGATIVE,
        )

        await message.answer(
            "Согласие на обработку персональных данных\n\n"
            "Перед началом тестирования необходимо ваше согласие на обработку "
            "персональных данных.\n\n"
            "В рамках работы бота обрабатываются:\n"
            "• ваш VK ID (идентификатор пользователя),\n"
            "• возраст,\n"
            "• результаты пройденных тестов.\n\n"
            "Данные используются исключительно для проведения когнитивного "
            "тестирования и отображения вашей личной динамики результатов. "
            "Данные не передаются третьим лицам.\n\n"
            "Нажимая «Согласен(на)», вы подтверждаете своё согласие на "
            "обработку перечисленных персональных данных.",
            keyboard=keyboard.get_json(),
        )

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_CONSENT)

    @bot.on.message(payload={"cmd": "consent_accept"})
    async def handle_consent_accept(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id

        try:
            async with async_session() as session:
                stmt = select(User).where(User.vk_id == peer_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user is None:
                    user = User(vk_id=peer_id, age=None, consent_given=True)
                    session.add(user)
                else:
                    user.consent_given = True
                await session.commit()
                logger.info(f"✅ Согласие на ОПД получено от {peer_id}")
        except Exception as e:
            logger.exception(f"❌ Не удалось сохранить согласие {peer_id}: {e}")
            await message.answer("⚠️ Не удалось сохранить согласие. Попробуйте позже.")
            return

        if peer_id not in user_sessions:
            user_sessions[peer_id] = UserTestData(peer_id)

        await message.answer("Спасибо! Согласие получено.")
        await bot.state_dispenser.set(peer_id, TestStates.WAITING_AGE)
        await message.answer("Сколько вам лет? (от 7 лет)")

    @bot.on.message(payload={"cmd": "consent_decline"})
    async def handle_consent_decline(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        user_sessions.pop(peer_id, None)
        await safe_delete_state(bot, peer_id)

        await message.answer(
            "Без согласия на обработку персональных данных пройти "
            "тестирование, к сожалению, невозможно.\n\n"
            "Если передумаете — нажмите «▶️ Начать тест» снова."
        )

    @bot.on.message(payload={"cmd": "back_to_start"})
    async def handle_back_to_start(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        cancel_user_tasks(user_sessions, peer_id)
        user_sessions.pop(peer_id, None)
        await safe_delete_state(bot, peer_id)
        suggested_start.pop(peer_id, None)
        await send_start(message)

    @bot.on.message(payload={"cmd": "change_age"})
    async def handle_change_age(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            user_sessions[peer_id] = UserTestData(peer_id)
        await bot.state_dispenser.set(peer_id, TestStates.WAITING_AGE)
        await message.answer("Введите ваш возраст (от 7 лет):")

    @bot.on.message(payload={"cmd": "schulte_start"})
    async def handle_schulte_start(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("Сессия истекла. Напишите /start")
            return

        test_data = user_sessions[peer_id]

        grid = list(range(1, SCHULTE_MAX_NUMBER + 1))
        random.shuffle(grid)
        test_data.schulte_grid = grid
        test_data.schulte_next_target = 1
        test_data.schulte_pressed = set()
        test_data.schulte_errors = 0

        keyboard = build_schulte_keyboard(grid)

        sent = await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                f"🔢 ТЕСТ ШУЛЬТЕ\n\n"
                f"Нажимайте числа по порядку: 1 → 2 → … → {SCHULTE_MAX_NUMBER}.\n\n"
                f"Найдено: 0/{SCHULTE_MAX_NUMBER}\n"
                f"Сейчас найдите: 1"
            ),
            keyboard=keyboard.get_json(),
        )
        test_data.schulte_message_id = _extract_message_id(sent)
        test_data.schulte_start_time = time.monotonic()

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_SCHULTE)

        logger.info(
            f"🔢 Schulte старт для {peer_id}, "
            f"чисел: {SCHULTE_MAX_NUMBER}, порядок: {grid}"
        )

    async def _ack_schulte_event(event_obj):
        # Тихо подтверждает нажатие callback-кнопки (без всплывающей подсказки),
        # иначе на кнопке зависает индикатор загрузки.
        try:
            await bot.api.messages.send_message_event_answer(
                event_id=event_obj.event_id,
                user_id=event_obj.user_id,
                peer_id=event_obj.peer_id,
            )
        except Exception as e:
            logger.debug(f"event answer failed: {e}")

    async def _update_schulte_status(test_data, peer_id: int):
        # Редактирует ОДНО и то же сообщение, показывая последнее нажатое число
        # и прогресс (1 → 2 → 3 …). Нижняя клавиатура остаётся на месте.
        msg_id = test_data.schulte_message_id
        if not msg_id:
            return

        found_count = len(test_data.schulte_pressed)
        last_pressed = found_count  # числа нажимаются строго по порядку 1..N
        next_target = test_data.schulte_next_target

        if next_target <= SCHULTE_MAX_NUMBER:
            tail = f"Сейчас найдите: {next_target}"
        else:
            tail = "Готово! 🎉"

        text = (
            f"🔢 ТЕСТ ШУЛЬТЕ\n\n"
            f"Последнее нажатое: {last_pressed}\n"
            f"Найдено: {found_count}/{SCHULTE_MAX_NUMBER}\n"
            f"{tail}"
        )

        try:
            await bot.api.messages.edit(
                peer_id=peer_id,
                message_id=msg_id,
                message=text,
                keep_forward_messages=True,
                keep_snippets=True,
            )
        except Exception as e:
            logger.debug(f"schulte status edit failed: {e}")

    @bot.on.raw_event(
        GroupEventType.MESSAGE_EVENT,
        dataclass=GroupTypes.MessageEvent,
    )
    async def handle_schulte_button(event: GroupTypes.MessageEvent):
        obj = event.object
        peer_id = obj.peer_id
        payload = obj.payload or {}

        if not isinstance(payload, dict) or "schulte_num" not in payload:
            return

        # тихо подтверждаем нажатие (без подсказок), чтобы кнопка не зависала
        await _ack_schulte_event(obj)

        if peer_id not in user_sessions:
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_SCHULTE):
            return

        test_data = user_sessions[peer_id]

        if test_data.schulte_next_target > SCHULTE_MAX_NUMBER:
            return

        try:
            number = int(payload.get("schulte_num"))
        except (TypeError, ValueError):
            return

        if not (1 <= number <= SCHULTE_MAX_NUMBER):
            return

        if number in test_data.schulte_pressed:
            return

        if number == test_data.schulte_next_target:
            test_data.schulte_pressed.add(number)
            test_data.schulte_next_target += 1

            await _update_schulte_status(test_data, peer_id)

            if test_data.schulte_next_target > SCHULTE_MAX_NUMBER:
                await finish_schulte_test(bot, peer_id)

        else:
            test_data.schulte_errors += 1
            logger.info(
                f"❌ Schulte ошибка у {peer_id}: нажал {number}, "
                f"ожидалось {test_data.schulte_next_target}, "
                f"всего ошибок {test_data.schulte_errors}"
            )

    async def finish_schulte_test(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            return

        elapsed = time.monotonic() - (test_data.schulte_start_time or time.monotonic())
        errors = test_data.schulte_errors

        test_data.schulte_time = elapsed
        test_data.schulte_errors_total = errors

        finish_text = (
            f"✅ *Тест Шульте завершён!*\n\n"
            f"⏱️ Время: {elapsed:.1f} сек\n"
            f"❌ Ошибок: {errors}\n\n"
            f"🎉 Вы нашли все {SCHULTE_MAX_NUMBER} чисел!"
        )

        empty_keyboard = Keyboard()
        empty_keyboard.buttons = []

        try:
            await bot.api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message=finish_text,
                keyboard=empty_keyboard.get_json(),
            )
        except Exception as e:
            logger.exception(f"❌ Не удалось отправить итог Шульте: {e}")

        logger.info(
            f"✅ Schulte завершён для {peer_id}: "
            f"время={elapsed:.1f}с, ошибок={errors}, чисел={SCHULTE_MAX_NUMBER}"
        )

        await show_raven_instruction_by_peer(bot, peer_id)

    EMOTION_EMOJI = {
        BaseEmotion.JOY: "😊",
        BaseEmotion.SADNESS: "😢",
        BaseEmotion.FEAR: "😨",
        BaseEmotion.ANGER: "😠",
        BaseEmotion.TRUST: "🤝",
        BaseEmotion.DISGUST: "🤢",
        BaseEmotion.ANTICIPATION: "🤔",
        BaseEmotion.SURPRISE: "😲",
    }

    async def show_emotion_result(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            return

        emotion = test_data.final_emotion
        if emotion is None:
            logger.warning(
                f"⚠️ show_emotion_result: нет final_emotion для {peer_id}"
            )
            return

        emoji = EMOTION_EMOJI.get(emotion, "🎯")

        try:
            await bot.api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message=(
                    f"🎯 *Итог по эмоциональному состоянию*\n\n"
                    f"На основе теста Уилсона и шкалы ECMES "
                    f"ваше текущее эмоциональное состояние:\n\n"
                    f"{emoji} *{emotion.value.capitalize()}*"
                ),
            )
        except Exception as e:
            logger.exception(
                f"❌ Не удалось отправить итог эмоций для {peer_id}: {e}"
            )

    @bot.on.message(payload={"cmd": "luria_start"})
    async def handle_luria_start_button(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id

        if peer_id not in user_sessions:
            await message.answer("Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_LURIA_INSTRUCTION):
            logger.warning(
                f"⚠️ luria_start: неверное состояние у {peer_id}: "
                f"{state.state if state else None}"
            )
            await message.answer("⚠️ Пожалуйста, следуйте инструкциям")
            return

        test_data = user_sessions[peer_id]

        try:
            async with async_session() as session:
                words = await get_random_luria_words_from_db(session)
        except Exception as e:
            logger.exception(f"Не удалось получить слова из БД: {e}")
            await message.answer("Не удалось загрузить слова. Попробуйте позже.")
            return

        if len(words) < 10:
            logger.error(f"В word_bank меньше 10 слов ({len(words)}).")
            await message.answer("Банк слов пуст. Обратитесь к администратору.")
            return

        test_data.luria_words = words

        words_block = "\n".join(f"  • {w}" for w in words)

        sent = await message.answer(
            f"{words_block}\n\n"
        )

        test_data.luria_words_message_id = _extract_message_id(sent)
        logger.info(f"Сохранён message_id: {test_data.luria_words_message_id}")

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_LURIA_WORDS1)

        if test_data.luria_timer_task and not test_data.luria_timer_task.done():
            test_data.luria_timer_task.cancel()

        test_data.luria_timer_task = asyncio.create_task(
            _luria_memorize_timer(message, bot, peer_id, seconds=60)
        )

        logger.info(f"Запущен тест Лурии для {peer_id}, таймер на 60 секунд")

    async def _luria_memorize_timer(
            message: Message, bot: Bot, peer_id: int, seconds: int
    ):
        try:
            await asyncio.sleep(seconds)
            logger.info(f"⏰ Таймер сработал для {peer_id} через {seconds} сек")
        except asyncio.CancelledError:
            logger.info(f"❌ Таймер отменён для {peer_id}")
            return

        if peer_id not in user_sessions:
            logger.info(f"👤 Пользователь {peer_id} вышел из сессии")
            return

        try:
            state = await bot.state_dispenser.get(peer_id)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить состояние: {e}")
            state = None

        if not state_equals(state, TestStates.WAITING_LURIA_WORDS1):
            logger.info(f"ℹ️ Пользователь {peer_id} уже не в фазе запоминания")
            return

        test_data = user_sessions[peer_id]

        msg_id = getattr(test_data, "luria_words_message_id", None)
        if msg_id:
            try:
                await bot.api.messages.delete(
                    message_ids=[msg_id],
                    delete_for_all=True,
                    peer_id=peer_id
                )
                logger.info(f"🗑️ Сообщение {msg_id} удалено для {peer_id}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить сообщение {msg_id}: {e}")
                try:
                    await bot.api.messages.edit(
                        peer_id=peer_id,
                        message_id=msg_id,
                        message="⏰ *Время вышло!* Сообщение со словами скрыто."
                    )
                    logger.info(f"✏️ Сообщение {msg_id} отредактировано")
                except Exception as edit_error:
                    logger.warning(f"⚠️ Не удалось отредактировать сообщение: {edit_error}")
        else:
            logger.warning(f"⚠️ Нет message_id для удаления у пользователя {peer_id}")

        await show_schulte_instruction_by_peer(bot, peer_id)

    async def show_schulte_instruction_by_peer(bot: Bot, peer_id: int):
        keyboard = Keyboard(one_time=True, inline=False).add(
            Text("▶️ Пройти далее", payload={"cmd": "schulte_start"}),
            color=KeyboardButtonColor.POSITIVE,
        )

        await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                "🔢 *ТЕСТ ШУЛЬТЕ*\n\n"
                "Сейчас вы увидите таблицу с числами от 1 до 25, "
                "расставленными в случайном порядке.\n\n"
                "🔹 Ваша задача — найти и нажимать числа по порядку: 1, 2, 3, …, 25.\n"
                "🔹 Тест измеряет скорость внимания и концентрацию.\n"
                "🔹 Старайтесь работать быстро, но без ошибок.\n\n"
                "Когда будете готовы — нажмите кнопку 👇"
            ),
            keyboard=keyboard.get_json(),
        )

        await bot.state_dispenser.set(
            peer_id, TestStates.WAITING_SCHULTE_INSTRUCTION
        )

    @bot.on.message(payload={"cmd": "continue_test"})
    async def handle_continue_test(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id

        if peer_id not in user_sessions:
            await message.answer("❌ Ошибка. Напишите /start")
            return

        attachment = None
        try:
            uploader = PhotoMessageUploader(bot.api)
            attachment = await uploader.upload(WILSON_IMAGE_PATH, peer_id=peer_id)
        except FileNotFoundError:
            logger.error(f"Не найдена картинка: {WILSON_IMAGE_PATH}")
        except Exception as e:
            logger.exception(f"Не удалось загрузить картинку Уилсона: {e}")

        await message.answer(
            "ТЕСТ УИЛСОНА\n\n"
            "На картинке дерево с 21 человечком.\n"
            "Каждый из них находится в разном состоянии.\n\n"
            "Выберите номер того человечка, с которым вы себя ассоциируете прямо сейчас:",
            attachment=attachment,
            keyboard=build_wilson_keyboard().get_json(),
        )

        await bot.state_dispenser.set(
            peer_id,
            TestStates.WAITING_EMOTION_WILSON,
        )

    @bot.on.message(
        func=lambda m: isinstance(m.get_payload_json(), dict)
        and "wilson_pos" in m.get_payload_json()
    )
    async def handle_wilson_button(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_EMOTION_WILSON):
            return

        payload = message.get_payload_json() or {}
        try:
            value = int(payload.get("wilson_pos"))
        except (TypeError, ValueError):
            return

        if not (1 <= value <= 21):
            return

        await process_wilson_value(message, bot, value)

    @bot.on.message(
        func=lambda m: isinstance(m.get_payload_json(), dict)
        and "support_type" in m.get_payload_json()
    )
    async def handle_support_button(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_EMOTION_WILSON_SUPPORT):
            return

        payload = message.get_payload_json() or {}
        support = payload.get("support_type")
        if support not in ("support", "overload"):
            return

        test_data = user_sessions[peer_id]
        test_data.wilson_support = support
        await ask_ecmes(message, bot)

    @bot.on.message(
        func=lambda m: isinstance(m.get_payload_json(), dict)
        and "ecmes" in m.get_payload_json()
    )
    async def handle_ecmes_button(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_EMOTION_ECMES):
            return

        payload = message.get_payload_json() or {}
        ecmes = payload.get("ecmes")
        valid = {"very_good", "good", "neutral", "bad", "very_bad"}
        if ecmes not in valid:
            return

        await finish_emotion_stage(message, bot, ecmes)

    async def show_raven_instruction_by_peer(bot: Bot, peer_id: int):
        keyboard = Keyboard(one_time=True, inline=False).add(
            Text("▶️ Пройти далее", payload={"cmd": "raven_start"}),
            color=KeyboardButtonColor.POSITIVE,
        )

        await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                "🧩 *ТЕСТ РАВЕНА*\n\n"
                f"Сейчас вам будет показано {RAVEN_TASKS_COUNT} картинок-головоломок.\n"
                "На каждой не хватает одного фрагмента.\n\n"
                f"🔹 Под картинкой будут варианты 1–{RAVEN_OPTIONS_COUNT}.\n"
                "🔹 Выберите тот, который правильно завершает рисунок.\n"
                "🔹 Тест измеряет логическое мышление и способность находить закономерности.\n\n"
                "Когда будете готовы — нажмите кнопку 👇"
            ),
            keyboard=keyboard.get_json(),
        )

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_RAVEN)

    def build_raven_keyboard(answers_count: int = RAVEN_OPTIONS_COUNT) -> Keyboard:
        # на случай некорректных данных из БД — подстраховка
        if not answers_count or answers_count < 1:
            answers_count = RAVEN_OPTIONS_COUNT

        keyboard = Keyboard(inline=True)
        per_row = 3
        for i in range(1, answers_count + 1):
            keyboard.add(
                Text(str(i), payload={"raven_ans": i}),
                color=KeyboardButtonColor.PRIMARY,
            )
            if i % per_row == 0 and i != answers_count:
                keyboard.row()
        return keyboard

    async def send_raven_task(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            return

        idx = test_data.raven_index
        total = len(test_data.raven_tasks)

        if idx >= total:
            await finish_raven_test(bot, peer_id)
            return

        task = test_data.raven_tasks[idx]
        image_path = os.path.join(RAVEN_DIR, task["image"])
        answers_count = task.get("answers_count") or RAVEN_OPTIONS_COUNT

        attachment = None
        try:
            uploader = PhotoMessageUploader(bot.api)
            attachment = await uploader.upload(image_path, peer_id=peer_id)
        except FileNotFoundError:
            logger.error(f"❌ Не найдена картинка Равена: {image_path}")
        except Exception as e:
            logger.exception(
                f"❌ Не удалось загрузить картинку Равена {image_path}: {e}"
            )

        await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                f"🧩 *Задание {idx + 1} из {total}*\n\n"
                f"Какой фрагмент правильно завершает рисунок?\n"
                f"Выберите номер 1–{answers_count} 👇"
            ),
            attachment=attachment,
            keyboard=build_raven_keyboard(answers_count).get_json(),
        )

    @bot.on.message(payload={"cmd": "raven_start"})
    async def handle_raven_start(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        logger.info(f"🧩 raven_start payload получен от {peer_id}")

        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_RAVEN):
            logger.warning(
                f"⚠️ raven_start: неверное состояние у {peer_id}: "
                f"{state.state if state else None}"
            )

        test_data = user_sessions[peer_id]
        age = test_data.age or 18

        try:
            async with async_session() as session:
                tasks = await get_random_raven_tasks_from_db(
                    session, age=age, count=RAVEN_TASKS_COUNT
                )
        except Exception as e:
            logger.exception(f"❌ Не удалось получить задания Равена: {e}")
            await message.answer("⚠️ Не удалось загрузить задания. Попробуйте позже.")
            return

        if not tasks:
            logger.error(
                f"❌ В raven_tests нет заданий для возраста {age} "
                f"(категория {'child' if age <= 14 else 'adult'})."
            )
            await message.answer(
                "⚠️ Банк заданий Равена пуст. Обратитесь к администратору."
            )
            return

        if len(tasks) < RAVEN_TASKS_COUNT:
            logger.warning(
                f"⚠️ В БД нашлось только {len(tasks)} заданий "
                f"(нужно {RAVEN_TASKS_COUNT}). Используем что есть."
            )

        test_data.raven_tasks = tasks
        test_data.raven_index = 0
        test_data.raven_correct = 0
        test_data.raven_start_time = time.monotonic()
        test_data.raven_total_time = 0.0

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_RAVEN)

        logger.info(
            f"🧩 Raven старт для {peer_id}: возраст={age}, "
            f"заданий={len(tasks)}, IDs={[t['id'] for t in tasks]}"
        )

        await send_raven_task(bot, peer_id)

    @bot.on.message(
        func=lambda m: isinstance(m.get_payload_json(), dict)
        and "raven_ans" in m.get_payload_json()
    )
    async def handle_raven_answer(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        state = await bot.state_dispenser.get(peer_id)
        if not state_equals(state, TestStates.WAITING_RAVEN):
            return

        test_data = user_sessions[peer_id]

        if test_data.raven_index >= len(test_data.raven_tasks):
            return

        payload = message.get_payload_json() or {}
        try:
            user_answer = int(payload.get("raven_ans"))
        except (TypeError, ValueError):
            return

        task = test_data.raven_tasks[test_data.raven_index]
        answers_count = task.get("answers_count") or RAVEN_OPTIONS_COUNT

        if not (1 <= user_answer <= answers_count):
            return

        is_correct = check_raven_answer(task["answer"], user_answer)
        if is_correct:
            test_data.raven_correct += 1

        logger.info(
            f"🧩 Raven ответ {peer_id}: задание #{task['id']} ({task['image']}), "
            f"ответ={user_answer}, правильный={task['answer']}, "
            f"итог={'✅' if is_correct else '❌'}"
        )

        test_data.raven_index += 1

        if test_data.raven_index >= len(test_data.raven_tasks):
            await finish_raven_test(bot, peer_id)
        else:
            await send_raven_task(bot, peer_id)

    async def finish_raven_test(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            return

        if test_data.raven_start_time is not None:
            test_data.raven_total_time = (
                time.monotonic() - test_data.raven_start_time
            )
        else:
            test_data.raven_total_time = 0.0

        correct = test_data.raven_correct
        total = len(test_data.raven_tasks)
        elapsed = test_data.raven_total_time

        await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                f"✅ *Тест Равена завершён!*\n\n"
                f"Правильных ответов: {correct} из {total}\n"
                f"⏱️ Время: {elapsed:.1f} сек"
            ),
        )

        logger.info(
            f"✅ Raven завершён для {peer_id}: {correct}/{total}, "
            f"время={elapsed:.1f}с"
        )

        await start_luria_recall(bot, peer_id)

    async def start_luria_recall(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            return

        test_data.luria_recall_index = 0
        test_data.luria_recalled = []

        await bot.api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=(
                "📚 *Вспоминаем слова*\n\n"
                "Помните 10 слов, которые я показывал перед тестом Шульте?\n"
                "Теперь введите их по очереди — *по одному слову в сообщении*.\n\n"
                "Порядок не важен. Если не помните — напишите «-» (минус) или «не помню», "
                "чтобы пропустить.\n\n"
                f"✏️ Введите слово 1 из 10:"
            ),
        )

        await bot.state_dispenser.set(peer_id, TestStates.WAITING_LURIA_RECALL)

    async def handle_luria_recall(message: Message, bot: Bot):
        peer_id = message.peer_id
        if peer_id not in user_sessions:
            await message.answer("❌ Сессия истекла. Напишите /start")
            return

        test_data = user_sessions[peer_id]
        text_in = (message.text or "").strip()

        if not text_in:
            await message.answer("✏️ Введите слово (или «-», чтобы пропустить)")
            return

        first_word = text_in.split()[0].lower()
        skip_markers = {"-", "—", "не", "не помню", "пропустить", "skip"}
        is_skip = first_word in skip_markers or text_in.lower() in skip_markers

        if not is_skip:
            already_recalled_lower = {w.lower() for w in test_data.luria_recalled}
            for original in test_data.luria_words:
                if original.lower() in already_recalled_lower:
                    continue
                if fuzz.ratio(original.lower(), first_word) > 75:
                    test_data.luria_recalled.append(original)
                    break

        test_data.luria_recall_index += 1
        total = 10
        idx = test_data.luria_recall_index

        if idx >= total:
            recalled = len(test_data.luria_recalled)
            await message.answer(
                f"Готово!\n\n"
                f"Вы вспомнили: *{recalled} из {total}* слов."
            )
            logger.info(
                f"✅ Luria recall завершён для {peer_id}: {recalled}/{total}"
            )
            await save_test_session(peer_id)
            await show_final_scores(bot, peer_id)
            await safe_delete_state(bot, peer_id)
            return

        await message.answer(f"✏️ Введите слово {idx + 1} из {total}:")

    async def save_test_session(peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            logger.warning(
                f"⚠️ save_test_session: нет user_sessions[{peer_id}], пропускаем."
            )
            return

        wilson_result = test_data.wilson_position or 0

        ecmes_result = ECMES_CODE_TO_INT.get(test_data.ecmes_level, 0)

        luria_result = len(test_data.luria_recalled or [])

        schulte_time = float(getattr(test_data, "schulte_time", 0.0) or 0.0)
        schulte_errors = int(getattr(test_data, "schulte_errors_total", 0) or 0)

        raven_time = float(getattr(test_data, "raven_total_time", 0.0) or 0.0)
        raven_total_tasks = len(test_data.raven_tasks or [])
        raven_correct = int(test_data.raven_correct or 0)
        raven_errors = max(0, raven_total_tasks - raven_correct)

        emotion_value = (
            test_data.final_emotion.value
            if test_data.final_emotion is not None
            else None
        )

        try:
            async with async_session() as session:
                new_session = TestSession(
                    vk_id=peer_id,
                    wilson_result=wilson_result,
                    ecmes_result=ecmes_result,
                    luria_result=luria_result,
                    schulte_time_result=schulte_time,
                    schulte_errors_result=schulte_errors,
                    raven_time_result=raven_time,
                    raven_errors_result=raven_errors,
                )
                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)

            logger.info(
                f"💾 TestSession сохранена для {peer_id}: id={new_session.id}, "
                f"wilson={wilson_result}, ecmes={ecmes_result}, "
                f"luria={luria_result}/10, schulte={schulte_time:.1f}с/{schulte_errors}, "
                f"raven_time={raven_time:.1f}с, raven_errors={raven_errors}, "
                f"emotion={emotion_value}"
            )
        except Exception as e:
            logger.exception(
                f"❌ Не удалось сохранить TestSession для {peer_id}: {e}"
            )

    async def show_final_scores(bot: Bot, peer_id: int):
        test_data = user_sessions.get(peer_id)
        if not test_data:
            logger.warning(
                f"⚠️ show_final_scores: нет user_sessions[{peer_id}], пропускаем."
            )
            return

        schulte_errors = int(getattr(test_data, "schulte_errors_total", 0) or 0)
        schulte_time = float(getattr(test_data, "schulte_time", 0.0) or 0.0)
        luria_recalled = len(test_data.luria_recalled or [])
        raven_correct = int(test_data.raven_correct or 0)
        raven_total = len(test_data.raven_tasks or []) or RAVEN_TASKS_COUNT
        raven_total_time = float(getattr(test_data, "raven_total_time", 0.0) or 0.0)
        age = int(test_data.age or 18)

        scores = calculate_all_scores(
            schulte_errors=schulte_errors,
            schulte_time_sec=schulte_time,
            luria_recalled=luria_recalled,
            raven_correct=raven_correct,
            raven_total=raven_total,
            raven_total_time_sec=raven_total_time,
            age=age,
        )

        logger.info(
            f"📊 Итоговые баллы для {peer_id}: {scores} "
            f"(schulte_errors={schulte_errors}, schulte_time={schulte_time:.1f}, "
            f"luria={luria_recalled}, raven={raven_correct}/{raven_total}, "
            f"raven_time={raven_total_time:.1f}, age={age})"
        )

        report = (
            "📊 ИТОГИ ТЕСТИРОВАНИЯ\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Внимание:    {scores['attention']}/10  — {interpret_score(scores['attention'])}\n"
            f"Восприятие:  {scores['perception']}/10  — {interpret_score(scores['perception'])}\n"
            f"Память:       {scores['memory']}/10  — {interpret_score(scores['memory'])}\n"
            f"Мышление:    {scores['thinking']}/10  — {interpret_score(scores['thinking'])}\n"
            f"Воображение: {scores['imagination']}/10  — {interpret_score(scores['imagination'])}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        try:
            await bot.api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message=report,
            )
        except Exception as e:
            logger.exception(
                f"❌ Не удалось отправить итоговые баллы {peer_id}: {e}"
            )

        # radar_path = None
        # try:
        #     radar_path = save_radar_to_tempfile(
        #         scores,
        #         title="Когнитивные способности",
        #         subtitle="Результаты этого теста",
        #     )
        #     uploader = PhotoMessageUploader(bot.api)
        #     attachment = await uploader.upload(radar_path, peer_id=peer_id)
        #     await bot.api.messages.send(
        #         peer_id=peer_id,
        #         random_id=0,
        #         message="🕸 Ваш радар-чарт по 5 показателям:",
        #         attachment=attachment,
        #     )
        # except Exception as e:
        #     logger.exception(
        #         f"❌ Не удалось отправить радар-чарт {peer_id}: {e}"
        #     )
        # finally:
        #     if radar_path:
        #         try:
        #             os.remove(radar_path)
        #         except OSError:
        #             pass

        # ── Второй радар-чарт: результаты с учётом эмоционального состояния ──
        emotion = test_data.final_emotion
        if emotion is not None:
            emotion_value = emotion.value if hasattr(emotion, "value") else str(emotion)
            adjusted_scores = apply_emotion_modifier(scores, emotion_value)
            emotion_radar_path = None
            try:
                emotion_radar_path = save_radar_with_emotion_to_tempfile(
                    scores,
                    adjusted_scores,
                    emotion_label=emotion_value,
                    title="Способности с учётом эмоционального состояния",
                )
                uploader2 = PhotoMessageUploader(bot.api)
                attachment2 = await uploader2.upload(
                    emotion_radar_path, peer_id=peer_id
                )

                # Формируем текст с разницей в баллах
                diff_lines = []
                labels_ru = {
                    "attention": "Внимание",
                    "perception": "Восприятие",
                    "memory": "Память",
                    "thinking": "Мышление",
                    "imagination": "Воображение",
                }
                for key, label in labels_ru.items():
                    orig = scores.get(key, 0)
                    adj = adjusted_scores.get(key, 0)
                    diff = round(adj - orig, 1)
                    if diff > 0:
                        diff_lines.append(f"  {label}: {orig} → {adj} (+{diff})")
                    elif diff < 0:
                        diff_lines.append(f"  {label}: {orig} → {adj} ({diff})")
                    else:
                        diff_lines.append(f"  {label}: {orig} (без изменений)")

                description = emotion_modifier_description(emotion_value)
                caption = (
                    f"Радар-чарт с учётом эмоции «{emotion_value}»\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    f"Синий — результат теста без учета эмоционального состояния.\n"
                    f"Оранжевый — оценка с поправкой на ваше состояние.\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    + "\n".join(diff_lines) + "\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    f"{description}"
                )
                await bot.api.messages.send(
                    peer_id=peer_id,
                    random_id=0,
                    message=caption,
                    attachment=attachment2,
                )
            except Exception as e:
                logger.exception(
                    f"❌ Не удалось отправить эмоциональный радар-чарт {peer_id}: {e}"
                )
            finally:
                if emotion_radar_path:
                    try:
                        os.remove(emotion_radar_path)
                    except OSError:
                        pass

        # ── Меню «что дальше» (как в начале) ──
        menu_kb = Keyboard(inline=True)
        menu_kb.add(
            Text("🔁 Пройти тест заново", payload={"cmd": "start_test"}),
            color=KeyboardButtonColor.POSITIVE,
        )
        menu_kb.row()
        menu_kb.add(
            Text("👤 Личный кабинет", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        menu_kb.row()
        menu_kb.add(
            Text("🏠 В главное меню", payload={"cmd": "back_to_start"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        try:
            await bot.api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message="Что дальше? Выберите действие:",
                keyboard=menu_kb.get_json(),
            )
        except Exception as e:
            logger.exception(
                f"❌ Не удалось отправить финальное меню {peer_id}: {e}"
            )

    async def has_user_consent(peer_id: int) -> bool:
        try:
            async with async_session() as session:
                stmt = select(User).where(User.vk_id == peer_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()

                return bool(user and user.consent_given)
        except Exception as e:
            logger.exception(f"❌ Ошибка проверки consent для {peer_id}: {e}")
            return False

    @bot.on.message()
    async def handle_all(message: Message):
        if _is_bot_message(message):
            return

        peer_id = message.peer_id
        text = message.text.strip() if message.text else ""

        consent = await has_user_consent(peer_id)

        if not consent:
            state = await bot.state_dispenser.get(peer_id)

            if not state_equals(state, TestStates.WAITING_CONSENT):
                if peer_id not in user_sessions:
                    user_sessions[peer_id] = UserTestData(peer_id)

                await show_consent(message, bot)

            return

        logger.info(f"MSG: {text} | {peer_id}")

        payload_dict = message.get_payload_json()
        if isinstance(payload_dict, dict) and any(
            k in payload_dict
            for k in (
                "cmd",
                "wilson_pos",
                "support_type",
                "ecmes",
                "schulte_num",
                "raven_ans",
            )
        ):
            return

        if peer_id in user_sessions:
            state = await bot.state_dispenser.get(peer_id)
            logger.info(f"STATE: {state}")

            if state_equals(state, TestStates.WAITING_CONSENT):
                await message.answer(
                    "👇 Пожалуйста, нажмите одну из кнопок выше, "
                    "чтобы дать согласие или отказаться."
                )
                return

            if state_equals(state, TestStates.WAITING_AGE):
                await handle_age(message, bot)
                return

            elif state_equals(state, TestStates.WAITING_START_AFTER_AGE):
                await message.answer("👇 Нажмите кнопку, чтобы начать тест")
                return

            elif state_equals(state, TestStates.WAITING_EMOTION_WILSON):
                await handle_wilson(message, bot)
                return

            elif state_equals(state, TestStates.WAITING_EMOTION_WILSON_SUPPORT):
                await handle_wilson_support(message, bot)
                return

            elif state_equals(state, TestStates.WAITING_EMOTION_ECMES):
                await handle_ecmes(message, bot)
                return

            elif state_equals(state, TestStates.WAITING_LURIA_INSTRUCTION):
                await message.answer(
                    "👇 Нажмите кнопку «Пройти далее», когда будете готовы запоминать слова"
                )
                return

            elif state_equals(state, TestStates.WAITING_LURIA_WORDS1):
                await message.answer(
                    "⏳ Идёт запоминание слов. Пожалуйста, дождитесь окончания таймера."
                )
                return

            elif state_equals(state, TestStates.WAITING_LURIA_RECALL):
                await handle_luria_recall(message, bot)
                return

            elif state_equals(state, TestStates.WAITING_SCHULTE_INSTRUCTION):
                await message.answer(
                    "👇 Нажмите кнопку «Пройти далее», чтобы начать тест Шульте"
                )
                return

            elif state_equals(state, TestStates.WAITING_SCHULTE):
                return

            elif state_equals(state, TestStates.WAITING_RAVEN):
                _td = user_sessions.get(message.peer_id)
                _ac = RAVEN_OPTIONS_COUNT
                if _td and 0 <= _td.raven_index < len(_td.raven_tasks):
                    _ac = _td.raven_tasks[_td.raven_index].get(
                        "answers_count"
                    ) or RAVEN_OPTIONS_COUNT
                await message.answer(
                    f"👇 Пожалуйста, выберите один из вариантов 1–{_ac} кнопкой"
                )
                return

            else:
                user_sessions.pop(peer_id, None)
                await safe_delete_state(bot, peer_id)
                await send_start(message)
                return

        await send_start(message)

    async def send_start(message: Message):
        peer_id = message.peer_id

        current_time = time.time()
        last_time = suggested_start.get(peer_id, 0)

        if current_time - last_time < 300:
            return

        suggested_start[peer_id] = current_time

        keyboard = Keyboard(inline=True).add(
            Text("▶️ Начать тест", payload={"cmd": "start_test"}),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
        keyboard.add(
            Text("👤 Личный кабинет", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        greeting = random.choice(GREETINGS)

        await message.answer(
            f"{greeting}\n\n",
            keyboard=keyboard.get_json()
        )

    async def handle_age(message: Message, bot: Bot):
        try:
            age = int(message.text)
            if age < 7 or age > 99:
                raise ValueError
        except Exception:
            await message.answer("Некорректно введен возраст")
            return

        test_data = user_sessions[message.peer_id]
        test_data.age = age

        try:
            async with async_session() as session:
                stmt = select(User).where(User.vk_id == message.peer_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()

                if user is None:
                    user = User(vk_id=message.peer_id, age=age, consent_given=True)
                    session.add(user)
                    logger.info(f"➕ Новый пользователь {message.peer_id}, возраст {age}")
                else:
                    user.age = age
                    logger.info(f"♻️ Обновлён возраст пользователя {message.peer_id}: {age}")

                await session.commit()
        except Exception as e:
            logger.exception(f"❌ Не удалось сохранить пользователя {message.peer_id}: {e}")
            await message.answer(
                "⚠️ Не удалось сохранить ваши данные. Попробуйте ещё раз позже."
            )
            return

        keyboard = Keyboard(one_time=True, inline=False)
        keyboard.add(
            Text("▶️ Начать тестирование", payload={"cmd": "continue_test"}),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
        keyboard.add(
            Text("👤 Личный кабинет", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        await message.answer(
            "Возраст сохранён!\n\n"
            "Готовы пройти тест?\nНажмите кнопку ниже",
            keyboard=keyboard.get_json()
        )

        await bot.state_dispenser.set(
            message.peer_id,
            TestStates.WAITING_START_AFTER_AGE
        )

    async def handle_wilson(message: Message, bot: Bot):
        try:
            value = int(message.text)
            if value < 1 or value > 21:
                raise ValueError
        except (TypeError, ValueError):
            await message.answer(
                "Введите число от 1 до 21 или нажмите кнопку"
            )
            return

        await process_wilson_value(message, bot, value)

    async def process_wilson_value(message: Message, bot: Bot, value: int):
        test_data = user_sessions[message.peer_id]
        test_data.wilson_position = value

        if value == 16:
            keyboard = Keyboard(one_time=True, inline=False)
            keyboard.add(
                Text("Вариант 1", payload={"support_type": "support"}),
                color=KeyboardButtonColor.SECONDARY,
            )
            keyboard.row()
            keyboard.add(
                Text("Вариант 2", payload={"support_type": "overload"}),
                color=KeyboardButtonColor.SECONDARY,
            )
            await message.answer(
                "Уточнение:\n"
                "Как вы видите человечка под №17 в отношении себя?\n\n"
                "1 — Обнимает и поддерживает Вас\n"
                "2 — Вы несете на себе этого человечка",
                keyboard=keyboard.get_json(),
            )
            await bot.state_dispenser.set(
                message.peer_id,
                TestStates.WAITING_EMOTION_WILSON_SUPPORT,
            )
        else:
            await ask_ecmes(message, bot)

    async def handle_wilson_support(message: Message, bot: Bot):
        mapping = {"1": "support", "2": "overload"}
        support = mapping.get(message.text)
        if support is None:
            await message.answer("❌ Введите 1 или 2 или нажмите кнопку")
            return

        test_data = user_sessions[message.peer_id]
        test_data.wilson_support = support
        await ask_ecmes(message, bot)

    async def ask_ecmes(message: Message, bot: Bot):
        keyboard = Keyboard(one_time=True, inline=False)
        keyboard.add(
            Text("😁 Очень хорошо", payload={"ecmes": "very_good"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text("🙂 Хорошо", payload={"ecmes": "good"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text("😐 Нейтрально", payload={"ecmes": "neutral"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text("😞 Плохо", payload={"ecmes": "bad"}),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text("😭 Очень плохо", payload={"ecmes": "very_bad"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        attachment = None
        try:
            uploader = PhotoMessageUploader(bot.api)
            attachment = await uploader.upload(ECMES_IMAGE_PATH, peer_id=message.peer_id)
        except FileNotFoundError:
            logger.error(f"❌ Не найдена картинка: {ECMES_IMAGE_PATH}")
        except Exception as e:
            logger.exception(f"❌ Не удалось загрузить картинку ECMES: {e}")

        await message.answer(
            "📊 *Как вы себя чувствуете прямо сейчас?*\n\n"
            "1 — 😁 Очень хорошо\n"
            "2 — 🙂 Хорошо\n"
            "3 — 😐 Нейтрально\n"
            "4 — 😞 Плохо\n"
            "5 — 😭 Очень плохо",
            attachment=attachment,
            keyboard=keyboard.get_json(),
        )

        await bot.state_dispenser.set(
            message.peer_id,
            TestStates.WAITING_EMOTION_ECMES,
        )

    async def handle_ecmes(message: Message, bot: Bot):
        text_to_code = {
            "1": "very_good",
            "2": "good",
            "3": "neutral",
            "4": "bad",
            "5": "very_bad",
        }
        ecmes = text_to_code.get(message.text)
        if ecmes is None:
            await message.answer("❌ Введите число от 1 до 5 или нажмите кнопку")
            return

        await finish_emotion_stage(message, bot, ecmes)

    async def finish_emotion_stage(message: Message, bot: Bot, ecmes_code: str):
        test_data = user_sessions[message.peer_id]
        test_data.ecmes_level = ecmes_code

        try:
            ecmes_enum = ECMESLevel(ecmes_code)
            support_enum = None
            if test_data.wilson_support == "support":
                support_enum = WilsonSupportType.SUPPORT
            elif test_data.wilson_support == "overload":
                support_enum = WilsonSupportType.OVERLOAD

            test_data.final_emotion = get_emotion_with_support(
                wilson_position=test_data.wilson_position,
                ecmes_level=ecmes_enum,
                support_type=support_enum,
            )
            logger.info(
                f"🎯 Итог эмоций для {message.peer_id}: "
                f"Уилсон={test_data.wilson_position} "
                f"(support={test_data.wilson_support}), "
                f"ECMES={ecmes_code} → {test_data.final_emotion.value}"
            )
        except Exception as e:
            logger.exception(
                f"❌ Не удалось посчитать итог эмоции для {message.peer_id}: {e}"
            )
            test_data.final_emotion = None

        await show_luria_instruction(message, bot)

    async def show_luria_instruction(message: Message, bot: Bot):
        keyboard = Keyboard(one_time=True, inline=False).add(
            Text("▶️ Пройти далее", payload={"cmd": "luria_start"}),
            color=KeyboardButtonColor.POSITIVE,
        )

        await message.answer(
            "ТЕСТ ЛУРИИ — «10 СЛОВ»\n\n"
            "Сейчас Вы увидите 10 слов. Вам их нужно запомнить.\n\n"
            "У вас будет 1 минута на запоминание.\n"
            "Слова не связаны между собой по смыслу.\n"
            "После прохождения других тестов Вам нужно будет их воспроизвести в любом порядке.\n\n"
            "Когда будете готовы — нажмите кнопку ниже",
            keyboard=keyboard.get_json(),
        )

        await bot.state_dispenser.set(
            message.peer_id,
            TestStates.WAITING_LURIA_INSTRUCTION,
        )

    @bot.on.message(text="/cancel")
    async def cancel(message: Message):
        if _is_bot_message(message):
            return
        cancel_user_tasks(user_sessions, message.peer_id)
        user_sessions.pop(message.peer_id, None)
        await safe_delete_state(bot, message.peer_id)
        await message.answer("❌ Тест отменён")

    logger.info("✅ Хендлеры загружены")