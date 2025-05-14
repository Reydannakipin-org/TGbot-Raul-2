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

from users.models import get_session, get_engine, Draw, Pair, Settings, Participant, Cycle


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

should_run = True

def handle_shutdown():
    global should_run
    logger.info('Остановка демона жеребьёвки...')
    should_run = False

def match_pairs(participants, previous_pairs):
    available_ids = {p.id for p in participants}
    id_to_participant = {p.id: p for p in participants}
    random.shuffle(participants)

    pairs = []
    while available_ids:
        p1_id = available_ids.pop()
        p1 = id_to_participant[p1_id]

        possible_partners = [
            p for p in participants
            if p.id in available_ids and (p1.id, p.id) not in previous_pairs and (p.id, p1.id) not in previous_pairs
        ]

        if possible_partners:
            p2 = random.choice(possible_partners)
            available_ids.remove(p2.id)
            pairs.append((p1, p2))
        else:
            logger.info(f"Не удалось найти пару для участника {p1.name}. Останется без пары в этой жеребьёвке.")

    return pairs

def get_or_create_cycle(session):
    participants = session.query(Participant).filter_by(active=True).all()
    total_possible = len(participants) * (len(participants) - 1) // 2

    previous_pairs = session.query(Pair).join(Draw).join(Cycle).order_by(Cycle.start_date.desc()).all()
    unique_pairs = set()
    for pair in previous_pairs:
        unique_pairs.add(tuple(sorted((pair.participant1_id, pair.participant2_id))))

    if total_possible == 0 or len(unique_pairs) / total_possible >= 0.75:
        logger.info("75% пар реализовано или участников мало — создаём новый цикл жеребьёвки.")
        new_cycle = Cycle(start_date=datetime.now().date())
        session.add(new_cycle)
        session.commit()
        return new_cycle

    current_cycle = session.query(Cycle).order_by(Cycle.start_date.desc()).first()
    if not current_cycle:
        current_cycle = Cycle(start_date=datetime.now().date())
        session.add(current_cycle)
        session.commit()

    return current_cycle

async def is_user_in_chat(bot: Bot, chat_id: Union[int, str], user_id: int) -> bool:
    try:
        member: ChatMember = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest:
        return False

async def get_actual_participants(bot: Bot, session, chat_id: Union[int, str]):
    participants = session.query(Participant).filter_by(active=True, admin=False).all()
    actual = []
    for p in participants:
        if await is_user_in_chat(bot, chat_id, p.tg_id):
            actual.append(p)
        else:
            logger.info(f"Пользователь {p.name} (id={p.telegram_id}) больше не в чате — исключён из жеребьёвки.")
            p.active = False
    session.commit()
    return actual

def save_draw(session, draw_date, current_cycle, pairs):
    draw = Draw(draw_date=draw_date, cycle_id=current_cycle.id)
    session.add(draw)
    session.flush()

    for p1, p2 in pairs:
        pair = Pair(draw_id=draw.id, participant1_id=p1.id, participant2_id=p2.id)
        session.add(pair)

    session.commit()
    logger.info(f'Жеребьёвка на {draw_date} завершена. Сформировано пар: {len(pairs)}.')
    return draw

async def perform_draw(bot: Bot, session, draw_date):
#    if session.query(Draw).filter_by(draw_date=draw_date).first():
#        logger.info(f'Жеребьёвка на дату {draw_date} уже проведена.')
#        return None, []

    participants = await get_actual_participants(bot, session, CHAT_ID)
    if len(participants) < 2:
        logger.info('Недостаточно участников для жеребьёвки.')
        return None, []

    current_cycle = get_or_create_cycle(session)
    previous_pairs = session.query(Pair).join(Draw).filter(Draw.cycle_id == current_cycle.id).all()
    previous_set = {(p.participant1_id, p.participant2_id) for p in previous_pairs}
    previous_set |= {(p.participant2_id, p.participant1_id) for p in previous_pairs}

    pairs = match_pairs(participants, previous_set)

    if not pairs:
        logger.info('Нет новых возможных пар для жеребьёвки.')
        return None, []

    return save_draw(session, draw_date, current_cycle, pairs), pairs

from datetime import datetime, timedelta

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
                last_draw = session.query(Draw).order_by(Draw.draw_date.desc()).first()

                need_draw = False

                # --- КОСТЫЛЬ: жеребьёвка каждые 3 минуты ---
                if not last_draw:
                    need_draw = True
                else:
                    if (now - last_draw.draw_date).total_seconds() >= 600:
                        need_draw = True

                # --- ОРИГИНАЛЬНАЯ ЛОГИКА ПО ДНЯМ И НЕДЕЛЯМ ---
                # if not last_draw:
                #     need_draw = True
                # elif now.date() >= last_draw.draw_date + timedelta(weeks=settings.frequency_in_weeks):
                #     need_draw = True

                # if now.weekday() == settings.day_of_week and need_draw:
                if need_draw:
                    logger.info("Проходит жеребьёвка (тестовый режим: каждые 3 минуты)")
                    draw, pairs = await perform_draw(bot, session, datetime.now())
                    if pairs:
                        for p1, p2 in pairs:
                            try:
                                await bot.send_message(int(p1.tg_id), f"Ваша пара на сегодня: {p2.name}")
                                await bot.send_message(int(p2.tg_id), f"Ваша пара на сегодня: {p1.name}")
                            except Exception as e:
                                logger.warning(f"Не удалось отправить сообщение участнику: {e}")

        finally:
            session.close()

        await asyncio.sleep(30)  # Проверяем каждые 30 секунд (можно и чаще)
    
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
