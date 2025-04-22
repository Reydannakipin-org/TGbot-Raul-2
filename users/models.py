from datetime import date
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Date, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import random

Base = declarative_base()

def get_engine():
    return create_engine('sqlite:///random_coffee.db')

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

class Participant(Base):
    __tablename__ = 'participants'

    id = Column(Integer, primary_key=True)
    tg_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    admin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    exclude_start = Column(Date, nullable=True)
    exclude_end = Column(Date, nullable=True)

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
    draw_date = Column(Date, nullable=False)

    pairs = relationship("Pair", back_populates="draw")

class Pair(Base):
    __tablename__ = 'pairs'

    id = Column(Integer, primary_key=True)
    draw_id = Column(Integer, ForeignKey('draws.id'))
    participant1_id = Column(Integer, ForeignKey('participants.id'))
    participant2_id = Column(Integer, ForeignKey('participants.id'))

    draw = relationship("Draw", back_populates="pairs")
    participant1 = relationship("Participant", foreign_keys=[participant1_id])
    participant2 = relationship("Participant", foreign_keys=[participant2_id])

class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False)  # 0 - Monday, 6 - Sunday
    frequency_in_weeks = Column(Integer, nullable=False)

def perform_draw(session, draw_date: date):
    participants = session.query(Participant).all()
    available = [p for p in participants if p.is_available(draw_date)]
    random.shuffle(available)

    # Получим все прошлые пары
    past_pairs = set()
    for pair in session.query(Pair).all():
        key = tuple(sorted([pair.participant1_id, pair.participant2_id]))
        past_pairs.add(key)

    pairs = []
    used_ids = set()
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            p1 = available[i]
            p2 = available[j]
            key = tuple(sorted([p1.id, p2.id]))
            if p1.id in used_ids or p2.id in used_ids:
                continue
            if key in past_pairs:
                continue
            pairs.append((p1, p2))
            used_ids.add(p1.id)
            used_ids.add(p2.id)
            break

    draw = Draw(draw_date=draw_date)
    session.add(draw)
    session.flush()

    for p1, p2 in pairs:
        pair = Pair(draw_id=draw.id, participant1_id=p1.id, participant2_id=p2.id)
        session.add(pair)

    session.commit()
    return draw, pairs
