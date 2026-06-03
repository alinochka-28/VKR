from pathlib import Path

from sqlalchemy import text
from vkbottle.bot import Bot
import asyncio
import logging

from config.config import VK_TOKEN
from config.database import engine, async_session
from models import Base
from handlers.bot_handlers import setup_handlers
from handlers.profile import setup_profile_handlers

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

bot = Bot(token=VK_TOKEN)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_category(filename: str) -> str:
    filename_lower = filename.lower()
    if "adult" in filename_lower:
        return "adult"
    elif "child" in filename_lower:
        return "child"
    else:
        return "unknown"


async def insert_images():
    images_path = Path("assets/raven")

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

    async with async_session() as session:
        for image_file in images_path.iterdir():
            if image_file.is_file() and image_file.suffix.lower() in image_extensions:
                image_name = image_file.name
                category = get_category(image_name)

                await session.execute(
                    text("""
                         INSERT INTO raven_tests (image, answer, category)
                         VALUES (:image, :answer, :category) ON CONFLICT (image) DO NOTHING
                         """),
                    {
                        "image": image_name,
                        "answer": 0,
                        "category": category
                    }
                )

        await session.commit()

def main():
    logger.info("🚀 Запуск бота...")

    asyncio.run(init_db())

    # asyncio.run(insert_images())

    setup_profile_handlers(bot)
    setup_handlers(bot)

    bot.run_forever()


if __name__ == "__main__":
    main()