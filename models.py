from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Numeric, Boolean
from datetime import datetime

from config.database import Base


class User(Base):
    __tablename__ = "users"
    vk_id = Column(Integer, primary_key=True)
    age = Column(Integer, nullable=True)
    consent_given = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TestSession(Base):
    __tablename__ = "test_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vk_id = Column(Integer, ForeignKey("users.vk_id"))
    date = Column(DateTime, default=datetime.utcnow)
    wilson_result = Column(Integer, nullable=False)            # 1..21
    ecmes_result = Column(Integer, nullable=False)             # 1..5
    luria_result = Column(Integer, nullable=False)             # сколько слов вспомнил (0..10)
    schulte_time_result = Column(Numeric, nullable=False)      # секунды
    schulte_errors_result = Column(Integer, nullable=False)    # количество ошибок
    raven_time_result = Column(Numeric, nullable=False)  # секунды
    raven_errors_result = Column(Integer, nullable=False)  # сколько правильно (0..N)


class WordBank(Base):
    __tablename__ = "word_bank"
    id = Column(Integer, primary_key=True)
    word = Column(String(50), unique=True, nullable=False)
    difficulty = Column(Integer, default=1)  # 1-легкие, 2-средние, 3-сложные
    created_at = Column(DateTime, default=datetime.utcnow)


class RavenTest(Base):
    __tablename__ = "raven_tests"
    id = Column(Integer, primary_key=True)
    image = Column(String(50), unique=True, nullable=False)   # имя файла, напр. adult_task_5.jpg
    answer = Column(Integer, nullable=False)                  # правильный вариант 1..answers_count
    answers_count = Column(Integer, nullable=False)           # сколько вариантов ответа у задания
    category = Column(String(20), nullable=False)             # 'adult' / 'child'
    created_at = Column(DateTime, default=datetime.utcnow)