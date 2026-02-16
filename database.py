import os
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, BigInteger, Date, Boolean, DateTime, Text, select, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///sttec.db")

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    group_name = Column(String(50), nullable=True)
    full_name = Column(String(255), nullable=True)
    last_notify_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class GroupSettings(Base):
    __tablename__ = "group_settings"
    
    group_name = Column(String(50), primary_key=True)
    current_headman_id = Column(BigInteger, nullable=True)
    current_duty_id = Column(BigInteger, nullable=True)
    notify_enabled = Column(Boolean, default=True)

class GroupPin(Base):
    __tablename__ = "group_pins"
    
    group_name = Column(String(50), primary_key=True)
    pin_code = Column(String(20), nullable=False)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(50), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    is_headman = Column(Boolean, default=False)
    is_sick = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Homework(Base):
    __tablename__ = "homework"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(50), nullable=False, index=True)
    subject_name = Column(String(255), nullable=False)
    homework_text = Column(Text, nullable=False)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self, url: str = DATABASE_URL):
        self.engine = create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            pool_pre_ping=True
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        await self.engine.dispose()
    
    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        group_name: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> User:
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                if username is not None:
                    user.username = username
                if group_name is not None:
                    user.group_name = group_name
                if full_name is not None:
                    user.full_name = full_name
            else:
                user = User(
                    user_id=user_id,
                    username=username,
                    group_name=group_name,
                    full_name=full_name
                )
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            return result.scalar_one_or_none()
    
    async def mark_user_notified_today(self, user_id: int):
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.last_notify_date = date.today()
                await session.commit()
    
    async def get_users_by_group(self, group_name: str) -> List[User]:
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.group_name == group_name)
            )
            return list(result.scalars().all())
    
    async def upsert_group_settings(
        self,
        group_name: str,
        current_headman_id: Optional[int] = None,
        current_duty_id: Optional[int] = None,
        notify_enabled: Optional[bool] = None
    ) -> GroupSettings:
        async with self.async_session() as session:
            result = await session.execute(
                select(GroupSettings).where(GroupSettings.group_name == group_name)
            )
            settings = result.scalar_one_or_none()
            
            if settings:
                if current_headman_id is not None:
                    settings.current_headman_id = current_headman_id
                if current_duty_id is not None:
                    settings.current_duty_id = current_duty_id
                if notify_enabled is not None:
                    settings.notify_enabled = notify_enabled
            else:
                settings = GroupSettings(
                    group_name=group_name,
                    current_headman_id=current_headman_id,
                    current_duty_id=current_duty_id,
                    notify_enabled=notify_enabled if notify_enabled is not None else True
                )
                session.add(settings)
            
            await session.commit()
            await session.refresh(settings)
            return settings
    
    async def get_group_settings(self, group_name: str) -> Optional[GroupSettings]:
        async with self.async_session() as session:
            result = await session.execute(
                select(GroupSettings).where(GroupSettings.group_name == group_name)
            )
            return result.scalar_one_or_none()
    
    async def set_group_pin(self, group_name: str, pin_code: str, created_by: int) -> GroupPin:
        async with self.async_session() as session:
            result = await session.execute(
                select(GroupPin).where(GroupPin.group_name == group_name)
            )
            pin = result.scalar_one_or_none()
            
            if pin:
                pin.pin_code = pin_code
                pin.created_by = created_by
                pin.created_at = datetime.utcnow()
            else:
                pin = GroupPin(
                    group_name=group_name,
                    pin_code=pin_code,
                    created_by=created_by
                )
                session.add(pin)
            
            await session.commit()
            await session.refresh(pin)
            return pin
    
    async def verify_pin(self, group_name: str, pin_code: str) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(GroupPin).where(GroupPin.group_name == group_name)
            )
            pin = result.scalar_one_or_none()
            return pin is not None and pin.pin_code == pin_code
    
    async def get_pin(self, group_name: str) -> Optional[GroupPin]:
        async with self.async_session() as session:
            result = await session.execute(
                select(GroupPin).where(GroupPin.group_name == group_name)
            )
            return result.scalar_one_or_none()
    
    async def upsert_student(
        self,
        group_name: str,
        user_id: int,
        full_name: str,
        is_headman: bool = False,
        is_sick: bool = False
    ) -> Student:
        async with self.async_session() as session:
            result = await session.execute(select(Student).where(Student.user_id == user_id))
            student = result.scalar_one_or_none()
            
            if student:
                student.group_name = group_name
                student.full_name = full_name
                student.is_headman = is_headman
                student.is_sick = is_sick
            else:
                student = Student(
                    group_name=group_name,
                    user_id=user_id,
                    full_name=full_name,
                    is_headman=is_headman,
                    is_sick=is_sick
                )
                session.add(student)
            
            await session.commit()
            await session.refresh(student)
            return student
    
    async def get_student(self, user_id: int) -> Optional[Student]:
        async with self.async_session() as session:
            result = await session.execute(select(Student).where(Student.user_id == user_id))
            return result.scalar_one_or_none()
    
    async def get_students_by_group(self, group_name: str) -> List[Student]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Student).where(Student.group_name == group_name)
            )
            return list(result.scalars().all())
    
    async def reset_all_sick_flags(self):
        async with self.async_session() as session:
            await session.execute(
                update(Student)
                .where(Student.is_sick.is_(True))
                .values(is_sick=False)
            )
            await session.commit()
    
    async def set_homework(
        self,
        group_name: str,
        subject_name: str,
        homework_text: str,
        created_by: Optional[int] = None
    ) -> Homework:
        async with self.async_session() as session:
            homework = Homework(
                group_name=group_name,
                subject_name=subject_name,
                homework_text=homework_text,
                created_by=created_by
            )
            session.add(homework)
            await session.commit()
            await session.refresh(homework)
            return homework
    
    async def get_homework_by_group(self, group_name: str) -> List[Homework]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Homework)
                .where(Homework.group_name == group_name)
                .order_by(Homework.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def delete_homework(self, homework_id: int):
        async with self.async_session() as session:
            await session.execute(delete(Homework).where(Homework.id == homework_id))
            await session.commit()
    
    async def clear_homework_by_subject(self, group_name: str, subject_name: str):
        async with self.async_session() as session:
            await session.execute(
                delete(Homework)
                .where(Homework.group_name == group_name)
                .where(Homework.subject_name == subject_name)
            )
            await session.commit()
