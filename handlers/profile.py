from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle import PhotoMessageUploader
from sqlalchemy import select, desc
from config.database import async_session
from models import TestSession, User
from services.radar_chart import save_radar_to_tempfile
from services.scoring_service import calculate_all_scores
from services.cognitive_service import RAVEN_TASKS_COUNT
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)


RADAR_PERIODS = {
    "day": ("📅 За день", timedelta(days=1)),
    "week": ("🗓 За неделю", timedelta(days=7)),
    "month": ("📆 За месяц", timedelta(days=30)),
    "all": ("♾ За всё время", None),
}


def setup_profile_handlers(bot: Bot):

    @bot.on.message(payload={"cmd": "profile"})
    async def show_profile(message: Message):
        user_age = None
        try:
            async with async_session() as session:
                stmt = select(User).where(User.vk_id == message.peer_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user is not None:
                    user_age = user.age
        except Exception as e:
            logger.exception(f"❌ Ошибка чтения пользователя: {e}")

        keyboard = Keyboard(inline=True)
        keyboard.add(
            Text("📊 История тестов", payload={"cmd": "profile_history"}),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
        keyboard.add(
            Text("📈 Динамика", payload={"cmd": "profile_dynamics"}),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
        keyboard.add(
            Text("🕸 Радар-чарт", payload={"cmd": "profile_radar"}),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
        keyboard.add(
            Text("🔙 На главную", payload={"cmd": "back_to_start"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        age_line = (
            f"Ваш возраст: {user_age}\n\n"
            if user_age is not None
            else "Возраст: не указан\n\n"
        )

        await message.answer(
            "👤 Личный кабинет\n\n"
            f"{age_line}"
            "Здесь вы можете посмотреть историю своих тестов, "
            "сравнить результаты с прошлым прохождением и посмотреть средние показатели за разные периоды.",
            keyboard=keyboard.get_json(),
        )

    @bot.on.message(payload={"cmd": "profile_history"})
    async def show_history(message: Message):
        try:
            async with async_session() as session:
                stmt = (
                    select(TestSession)
                    .where(TestSession.vk_id == message.peer_id)
                    .order_by(desc(TestSession.date))
                    .limit(5)
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()
        except Exception as e:
            logger.exception(f"❌ Ошибка чтения истории: {e}")
            await message.answer("⚠️ Не удалось загрузить историю.")
            return

        keyboard = Keyboard(inline=True).add(
            Text("🔙 Назад", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        if not sessions:
            await message.answer(
                "📭 У вас пока нет пройденных тестов.\n"
                "Начните с главного меню.",
                keyboard=keyboard.get_json(),
            )
            return

        history_text = "История тестов (последние 5)\n\n"
        for i, sess in enumerate(sessions, 1):
            date_str = sess.date.strftime("%d.%m.%Y %H:%M") if sess.date else "—"
            history_text += f"{i}. {date_str}\n"
            history_text += (
                f"Уилсон: {sess.wilson_result} | "
                f"ECMES: {sess.ecmes_result}/5\n"
                f"Лурия: {sess.luria_result}/10 | "
                f"Равен: {float(sess.raven_time_result):.1f}с, "
                f"ошибок {sess.raven_errors_result}\n"
                f"Шульте: {float(sess.schulte_time_result):.1f}с, "
                f"ошибок {sess.schulte_errors_result}\n\n"
            )

        await message.answer(history_text, keyboard=keyboard.get_json())

    @bot.on.message(payload={"cmd": "profile_dynamics"})
    async def show_dynamics(message: Message):
        back_kb = Keyboard(inline=True).add(
            Text("🔙 Назад", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        try:
            async with async_session() as session:
                stmt = (
                    select(TestSession)
                    .where(TestSession.vk_id == message.peer_id)
                    .order_by(desc(TestSession.date))
                    .limit(2)
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()
        except Exception as e:
            logger.exception(f"❌ Ошибка чтения динамики: {e}")
            await message.answer(
                "⚠️ Не удалось загрузить данные.",
                keyboard=back_kb.get_json(),
            )
            return

        if len(sessions) < 2:
            await message.answer(
                "📈 Для отображения динамики нужно пройти хотя бы 2 теста.",
                keyboard=back_kb.get_json(),
            )
            return

        current = sessions[0]
        previous = sessions[1]

        def diff_line(label: str, cur, prev, suffix: str = "", reverse: bool = False):
            try:
                cur_v = float(cur)
                prev_v = float(prev)
            except (TypeError, ValueError):
                return None
            d = cur_v - prev_v
            if abs(d) < 1e-6:
                return f"➖ {label}: без изменений"
            improved = (d < 0) if reverse else (d > 0)
            arrow = "📈" if improved else "📉"
            sign = "+" if d > 0 else ""
            if cur_v.is_integer() and prev_v.is_integer():
                return f"{arrow} {label}: {sign}{int(d)}{suffix}"
            return f"{arrow} {label}: {sign}{d:.1f}{suffix}"

        lines = []
        lines.append(diff_line("Лурия", current.luria_result, previous.luria_result, " слов"))
        lines.append(diff_line(
            "Равен время",
            current.raven_time_result, previous.raven_time_result,
            " сек", reverse=True,
        ))
        lines.append(diff_line(
            "Равен ошибки",
            current.raven_errors_result, previous.raven_errors_result,
            "", reverse=True,
        ))
        lines.append(diff_line(
            "Шульте время",
            current.schulte_time_result, previous.schulte_time_result,
            " сек", reverse=True,
        ))
        lines.append(diff_line(
            "Шульте ошибки",
            current.schulte_errors_result, previous.schulte_errors_result,
            "", reverse=True,
        ))

        changes_text = "\n".join(l for l in lines if l) or "📊 Результаты стабильны"

        await message.answer(
            f"Динамика результатов\n\n"
            f"Сравнение с предыдущим тестом:\n{changes_text}",
            keyboard=back_kb.get_json(),
        )

    @bot.on.message(payload={"cmd": "profile_radar"})
    async def show_radar_menu(message: Message):
        keyboard = Keyboard(inline=True)
        for code in ("day", "week", "month", "all"):
            label, _ = RADAR_PERIODS[code]
            keyboard.add(
                Text(label, payload={"cmd": "profile_radar_period", "period": code}),
                color=KeyboardButtonColor.PRIMARY,
            )
            keyboard.row()
        keyboard.add(
            Text("🔙 Назад", payload={"cmd": "profile"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        await message.answer(
            "🕸 *Радар-чарт*\n\n"
            "Выберите период — посчитаю средние баллы по 5 показателям "
            "и пришлю график.",
            keyboard=keyboard.get_json(),
        )

    def _session_to_scores(sess: TestSession, age: int) -> dict:
        raven_errors = int(sess.raven_errors_result or 0)
        raven_correct = max(0, RAVEN_TASKS_COUNT - raven_errors)

        return calculate_all_scores(
            schulte_errors=int(sess.schulte_errors_result or 0),
            schulte_time_sec=float(sess.schulte_time_result or 0),
            luria_recalled=int(sess.luria_result or 0),
            raven_correct=raven_correct,
            raven_total=RAVEN_TASKS_COUNT,
            raven_total_time_sec=float(sess.raven_time_result or 0),
            age=age,
        )

    @bot.on.message(
        func=lambda m: isinstance(m.get_payload_json(), dict)
        and m.get_payload_json().get("cmd") == "profile_radar_period"
    )
    async def show_radar_for_period(message: Message):
        peer_id = message.peer_id
        payload = message.get_payload_json() or {}
        period_code = payload.get("period")

        if period_code not in RADAR_PERIODS:
            return

        period_label, delta = RADAR_PERIODS[period_code]
        back_kb = Keyboard(inline=True).add(
            Text("🔙 Назад", payload={"cmd": "profile_radar"}),
            color=KeyboardButtonColor.SECONDARY,
        )

        try:
            async with async_session() as session:
                user_stmt = select(User).where(User.vk_id == peer_id)
                user_res = await session.execute(user_stmt)
                user = user_res.scalar_one_or_none()
                user_age = (user.age if user is not None else None) or 18

                stmt = select(TestSession).where(TestSession.vk_id == peer_id)
                if delta is not None:
                    since = datetime.utcnow() - delta
                    stmt = stmt.where(TestSession.date >= since)
                stmt = stmt.order_by(desc(TestSession.date))

                result = await session.execute(stmt)
                sessions = result.scalars().all()
        except Exception as e:
            logger.exception(f"❌ Ошибка чтения сессий для радара: {e}")
            await message.answer(
                "⚠️ Не удалось загрузить данные.",
                keyboard=back_kb.get_json(),
            )
            return

        if not sessions:
            await message.answer(
                f"📭 За период «{period_label}» пройденных тестов нет.\n"
                "Пройдите тест, чтобы появились данные.",
                keyboard=back_kb.get_json(),
            )
            return

        all_scores = [_session_to_scores(s, user_age) for s in sessions]
        keys = ("attention", "perception", "memory", "thinking", "imagination")
        avg_scores = {
            k: round(sum(s[k] for s in all_scores) / len(all_scores), 1)
            for k in keys
        }

        n = len(all_scores)
        word = "тест" if n == 1 else ("теста" if 2 <= n <= 4 else "тестов")
        subtitle = f"{period_label} · усреднено по {n} {word}"

        summary = (
            f"🕸 *Радар-чарт* ({period_label.lower()})\n\n"
            f"Учтено: *{n}* {word}\n\n"
            f"🧠 Внимание: *{avg_scores['attention']}/10*\n"
            f"👁 Восприятие: *{avg_scores['perception']}/10*\n"
            f"📚 Память: *{avg_scores['memory']}/10*\n"
            f"💭 Мышление: *{avg_scores['thinking']}/10*\n"
            f"🎨 Воображение: *{avg_scores['imagination']}/10*"
        )
        await message.answer(summary)

        radar_path = None
        try:
            radar_path = save_radar_to_tempfile(
                avg_scores,
                title="Средние когнитивные показатели",
                subtitle=subtitle,
            )
            uploader = PhotoMessageUploader(bot.api)
            attachment = await uploader.upload(radar_path, peer_id=peer_id)
            await bot.api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message="📊 Ваш радар-чарт:",
                attachment=attachment,
                keyboard=back_kb.get_json(),
            )
        except Exception as e:
            logger.exception(f"❌ Не удалось отправить радар {peer_id}: {e}")
            await message.answer(
                "⚠️ Не удалось построить график.",
                keyboard=back_kb.get_json(),
            )
        finally:
            if radar_path:
                try:
                    os.remove(radar_path)
                except OSError:
                    pass

    logger.info("✅ Хендлеры личного кабинета загружены")