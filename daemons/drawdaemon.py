import os
import asyncio
import signal
import logging
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Union


from aiogram import Bot
from aiogram.types import ChatMember
from aiogram.exceptions import TelegramBadRequest

from users.models import (
    get_session, get_engine,
    Draw, Pair, Settings,
    Participant, Cycle
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

should_run = True


def handle_shutdown():
    global should_run
    logger.info('Остановка демона жеребьёвки...')
    should_run = False


def match_pairs(participants, previous_pairs):
    random.shuffle(participants)
    available = participants[:]

    pairs = []
    used_ids = set()

    while len(available) >= 2:
        p1 = available.pop(0)
        p2_candidates = [
            p for p in available
            if (
                p.id, p1.id
            ) not in previous_pairs and (p1.id, p.id) not in previous_pairs
        ]
        if not p2_candidates:
            available.insert(0, p1)
            break

        p2 = random.choice(p2_candidates)
        available.remove(p2)
        pairs.append([p1, p2])
        used_ids.add(p1.id)
        used_ids.add(p2.id)

    while available and pairs:
        extra = available.pop()
        candidates = [pair for pair in pairs if len(pair) < 3]
        if not candidates:
            logger.info(
                f"Участник {extra.name} остался без пары."
            )
            break
        chosen_pair = random.choice(candidates)
        chosen_pair.append(extra)
        logger.info(f"Участник {extra.name} добавлен третьим в пару.")

    for lone in available:
        logger.info(
            f"Недостаточно участников для пары — {lone.name} остался без пары."
        )

    return pairs


def get_or_create_cycle(session):
    participants = session.query(Participant).filter_by(active=True).all()
    total_possible = len(participants) * (len(participants) - 1) // 2

    previous_pairs = session.query(Pair).join(Draw).join(Cycle).order_by(
        Cycle.start_date.desc()
    ).all()
    unique_pairs = set()
    for pair in previous_pairs:
        unique_pairs.add(tuple(sorted((pair.participant1_id,
                                       pair.participant2_id))))

    if total_possible == 0 or len(unique_pairs) / total_possible >= 0.75:
        logger.info(
            "75% пар реализовано — создаём новый цикл жеребьёвки."
        )
        new_cycle = Cycle(start_date=datetime.now().date())
        session.add(new_cycle)
        session.commit()
        return new_cycle

    current_cycle = session.query(Cycle).order_by(
        Cycle.start_date.desc()
    ).first()
    if not current_cycle:
        current_cycle = Cycle(start_date=datetime.now().date())
        session.add(current_cycle)
        session.commit()

    return current_cycle


async def is_user_in_chat(bot: Bot,
                          chat_id: Union[int, str],
                          user_id: int) -> bool:
    try:
        member: ChatMember = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest:
        return False


async def get_actual_participants(bot: Bot, session, chat_id: Union[int, str]):
    participants = session.query(Participant).filter_by(active=True,
                                                        admin=False).all()
    actual = []
    today = datetime.now().date()
    
    for p in participants:
        if await is_user_in_chat(bot, chat_id, p.tg_id):
            actual.append(p)
        else:
            logger.info(f"Пользователь {p.name} (id={p.tg_id})"
                        "больше не в чате — исключён из жеребьёвки.")
            p.active = False
        last_draw_date = session.query(Draw.draw_date).join(Pair).filter(
            (Pair.participant1_id == p.id) |
            (Pair.participant2_id == p.id) |
            (Pair.participant3_id == p.id)
        ).order_by(Draw.draw_date.desc()).first()
        if last_draw_date:
            weeks_passed = (today - last_draw_date[0]).days // 7
            if weeks_passed < p.frequency_individual:
                logger.info(
                    f"Участник {p.name} пропускает жеребьёвку — прошло "
                    f"{weeks_passed} недель из необходимых {p.frequency_individual}."
                )
                continue

    session.commit()
    return actual


def save_draw(session, draw_date, current_cycle, pairs):
    draw = Draw(draw_date=draw_date, cycle_id=current_cycle.id)
    session.add(draw)
    session.flush()

    for pair_tuple in pairs:
        p1 = pair_tuple[0]
        p2 = pair_tuple[1]
        p3 = pair_tuple[2] if len(pair_tuple) > 2 else None
        pair = Pair(
            draw_id=draw.id,
            participant1_id=p1.id,
            participant2_id=p2.id,
            participant3_id=p3.id if p3 else None
        )
        session.add(pair)

    session.commit()
    logger.info(
        f'Жеребьёвка на {draw_date} завершена. Сформировано пар: {len(pairs)}.'
    )
    return draw


async def perform_draw(bot: Bot, session, draw_date):
    if session.query(Draw).filter_by(draw_date=draw_date).first():
        logger.info(f'Жеребьёвка на дату {draw_date} уже проведена.')
        return None, []

    participants = await get_actual_participants(bot, session, CHAT_ID)
    if len(participants) < 2:
        logger.info('Недостаточно участников для жеребьёвки.')
        return None, []

    current_cycle = get_or_create_cycle(session)
    previous_pairs = session.query(Pair).join(Draw).filter(
        Draw.cycle_id == current_cycle.id
    ).all()
    previous_set = {(
        p.participant1_id, p.participant2_id
    ) for p in previous_pairs}
    previous_set |= {(
        p.participant2_id, p.participant1_id
    ) for p in previous_pairs}

    pairs = match_pairs(participants, previous_set)

    if not pairs:
        logger.info('Нет новых возможных пар для жеребьёвки.')
        return None, []

    return save_draw(session, draw_date, current_cycle, pairs), pairs


async def daemon_loop(bot: Bot):
    global should_run
    logger.info('Запуск демона жеребьёвки...')

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)

    engine = get_engine()

    while should_run:
        session = get_session(engine)
        try:
            settings = session.query(Settings).first()
            if settings:
                now = datetime.now()
                last_draw = session.query(
                    Draw
                ).order_by(Draw.draw_date.desc()).first()

                need_draw = False

                if not last_draw:
                    need_draw = True
                elif now.date() >= last_draw.draw_date + timedelta(
                    weeks=settings.frequency_in_weeks
                ):
                    need_draw = True

                if now.weekday() == settings.day_of_week and need_draw:
                    logger.info(
                        "Проходит жеребьёвка"
                    )
                    draw, pairs = await perform_draw(bot,
                                                     session,
                                                     datetime.now())
                    if pairs:
                        for pair in pairs:
                            p1, p2 = pair[0], pair[1]
                            p3 = pair[2] if len(pair) > 2 else None
                            names = [p1.name, p2.name] + (
                                [p3.name] if p3 else []
                            )
                            msg = (
                                "Ваша группа для ближайцшей встречи: "
                                + ", ".join(names)
                            )

                            for p in [p1, p2] + ([p3] if p3 else []):
                                try:
                                    await bot.send_message(int(p.tg_id), msg)
                                except Exception as e:
                                    logger.warning(
                                        "Не удалось отправить"
                                        f"сообщение участнику: {e}"
                                        )

        finally:
            session.close()

        await asyncio.sleep(1800)

    logger.info('Демон жеребьёвки остановлен.')


def init_db():
    session = get_session(get_engine())
    if session.query(Settings).first() is None:
        settings = Settings(day_of_week=2, frequency_in_weeks=2)
        session.add(settings)
        session.commit()
        print("Настройки созданы: понедельник, раз в 2 недели.")
    else:
        print("Настройки уже существуют.")
    session.close()


if __name__ == '__main__':
    init_db()
