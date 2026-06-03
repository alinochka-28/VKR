from vkbottle.bot import Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from config.database import async_session
from models import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)


async def show_main_menu(message: Message, is_authorized: bool = False):
    keyboard = Keyboard(one_time=False, inline=False)

    keyboard.add(Text("Начать тест", payload={"cmd": "start_test"}), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("👤 Личный кабинет", payload={"cmd": "profile"}), color=KeyboardButtonColor.SECONDARY)

    if is_authorized:
        greeting = "С возвращением!"
    else:
        greeting = "Привет! Я когнитивный чат-бот."

    await message.answer(
        f"{greeting}\n\n"
        f"Выберите действие:",
        keyboard=keyboard.get_json()
    )


async def check_user_exists(vk_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.vk_id == vk_id)
        )
        user = result.scalar_one_or_none()
        return user is not None


async def get_user_age(vk_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(User.age).where(User.vk_id == vk_id)
        )
        age = result.scalar_one_or_none()
        return age


async def save_user(vk_id: int, age: int):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.vk_id == vk_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(vk_id=vk_id, age=age)
            session.add(user)
            await session.commit()
            logger.info(f"✅ Новый пользователь сохранён: vk_id={vk_id}, age={age}")
            return True
        else:
            logger.info(f"👤 Пользователь уже существует: vk_id={vk_id}")
            return False