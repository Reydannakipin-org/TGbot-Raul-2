import asyncio
import signal
import logging
from datetime import datetime, timedelta
from users.models import get_session, get_engine, Draw, Pair, Settings, Participant, Cycle
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

should_run = True

def handle_shutdown():
    global should_run
    logger.info('Остановка демона жеребьёвки...')
    should_run = False

def match_pairs(participants, previous_pairs):
    """Составляем новые пары, избегая повторов."""
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
    """Возвращает текущий цикл или создаёт новый, если нужно."""
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

def perform_draw(session, draw_date):
    """Основная функция жеребьёвки."""
    if session.query(Draw).filter_by(draw_date=draw_date).first():
        logger.info(f'Жеребьёвка на дату {draw_date} уже проведена.')
        return None, []

    participants = session.query(Participant).filter_by(active=True, admin=False).all()
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

    draw = Draw(draw_date=draw_date, cycle_id=current_cycle.id)
    session.add(draw)
    session.flush()  # чтобы получить draw.id

    for p1, p2 in pairs:
        pair = Pair(draw_id=draw.id, participant1_id=p1.id, participant2_id=p2.id)
        session.add(pair)

    session.commit()
    logger.info(f'Жеребьёвка на {draw_date} завершена. Сформировано пар: {len(pairs)}.')
    return draw, pairs

async def daemon_loop():
    """Цикл работы демона жеребьёвки."""
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
                if not last_draw:
                    need_draw = True
                elif now.date() >= last_draw.draw_date + timedelta(weeks=settings.frequency_in_weeks):
                    need_draw = True

                if now.weekday() == settings.day_of_week and need_draw:
                    perform_draw(session, now.date())
        finally:
            session.close()

        await asyncio.sleep(86400)  # 24 часа

    logger.info('Демон жеребьёвки остановлен.')


def init_db():

    session = get_session(get_engine())

    if session.query(Settings).first() is None:
        settings = Settings(day_of_week=0, frequency_in_weeks=2)
        session.add(settings)
        session.commit()
        print("Настройки созданы: понедельник, раз в 2 недели.")
    else:
        print("Настройки уже существуют.")

    session.close()


if __name__ == '__main__':
    init_db()
    asyncio.run(daemon_loop())
