from datetime import date, datetime
from sqlalchemy import (
    Boolean, Column,
    Date, DateTime,
    Integer, String, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine():
    return create_async_engine('sqlite+aiosqlite:///random_coffee.db',
                               echo=False)


def get_session(engine):
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )()


class Cycle(Base):
    __tablename__ = 'cycles'

    id = Column(Integer, primary_key=True)
    start_date = Column(Date, nullable=False)

    draws = relationship("Draw", back_populates="cycle")


class Participant(Base):
    __tablename__ = 'participants'

    id = Column(Integer, primary_key=True)
    tg_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    admin = Column(Boolean, default=False)
    frequency_individual = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    exclude_start = Column(Date, nullable=True)
    exclude_end = Column(Date, nullable=True)
    added_at = Column(DateTime,
                      default=datetime.now,
                      nullable=False)  


    feedbacks = relationship("Feedback",
                             back_populates="participant",
                             cascade="all, delete-orphan")
    pictures = relationship("Picture",
                            back_populates="participant",
                            cascade="all, delete-orphan")

    def is_available(self, check_date: date):
        if not self.active:
            return False
        if self.exclude_start and self.exclude_end:
            return not (self.exclude_start <= check_date <= self.exclude_end)
        return True

    def __repr__(self):
        return f"<{self.name} ({'admin' if self.admin else 'user'})>"


class Draw(Base):
    __tablename__ = 'draws'

    id = Column(Integer, primary_key=True)
    draw_date = Column(DateTime, nullable=False, default=datetime.now)
    cycle_id = Column(Integer, ForeignKey('cycles.id'))

    cycle = relationship("Cycle", back_populates="draws")
    pairs = relationship("Pair", back_populates="draw")
    feedbacks = relationship("Feedback", back_populates="draw",
                             cascade="all, delete-orphan")


class Pair(Base):
    __tablename__ = 'pairs'

    id = Column(Integer, primary_key=True)
    draw_id = Column(Integer, ForeignKey('draws.id'))
    participant1_id = Column(Integer, ForeignKey('participants.id'))
    participant2_id = Column(Integer, ForeignKey('participants.id'))
    participant3_id = Column(Integer, ForeignKey('participants.id'), nullable=True)

    draw = relationship("Draw", back_populates="pairs")
    participant1 = relationship("Participant", foreign_keys=[participant1_id])
    participant2 = relationship("Participant", foreign_keys=[participant2_id])
    participant3 = relationship("Participant", foreign_keys=[participant3_id])



class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False)
    frequency_in_weeks = Column(Integer, nullable=False)


class Feedback(Base):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True)
    draw_id = Column(Integer, ForeignKey('draws.id'), nullable=False)
    participant_id = Column(Integer,
                            ForeignKey('participants.id'),
                            nullable=False)
    success = Column(Boolean, nullable=True)
    rating = Column(Boolean, nullable=True)
    comment = Column(String, nullable=True)
    skip_reason = Column(String, nullable=True)

    participant = relationship("Participant", back_populates="feedbacks")
    draw = relationship("Draw", back_populates="feedbacks")


class Picture(Base):
    __tablename__ = 'pictures'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer,
                            ForeignKey('participants.id'),
                            nullable=True)
    file_id = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    participant = relationship("Participant", back_populates="pictures")
