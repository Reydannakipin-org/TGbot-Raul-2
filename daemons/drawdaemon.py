import asyncio
import signal
import logging
from datetime import datetime, timedelta
from users.models import get_session, get_engine, Draw, Pair, Settings, Participant
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

should_run = True

def handle_shutdown():
    global should_run
    logger.info('Остановка демона жеребьёвки...')
    should_run = False

def perform_draw(session, draw_date):
    participants = session.query(Participant).filter_by(active=True).all()
    if len(participants) < 2:
        logger.info('Недостаточно участников для жеребьёвки.')
        return None, []

    previous_pairs = session.query(Pair).all()
    previous_set = {(p.participant1_id, p.participant2_id) for p in previous_pairs}
    previous_set |= {(p.participant2_id, p.participant1_id) for p in previous_pairs}

    random.shuffle(participants)
    pairs = []
    used_ids = set()

    for i, p1 in enumerate(participants):
        if p1.id in used_ids:
            continue
        for j in range(i + 1, len(participants)):
            p2 = participants[j]
            if p2.id in used_ids:
                continue
            if (p1.id, p2.id) not in previous_set:
                pairs.append((p1, p2))
                used_ids.update([p1.id, p2.id])
                break

    if not pairs:
        logger.info('Нет новых возможных пар.')
        return None, []

    draw = Draw(draw_date=draw_date)
    session.add(draw)
    session.flush()

    for p1, p2 in pairs:
        pair = Pair(draw_id=draw.id, participant1_id=p1.id, participant2_id=p2.id)
        session.add(pair)

    session.commit()
    logger.info(f'Жеребьёвка проведена на дату {draw_date}. Пары сохранены.')
    return draw, pairs

async def daemon_loop():
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
                if now.weekday() == settings.day_of_week:
                    last_draw = session.query(Draw).order_by(Draw.draw_date.desc()).first()
                    should_draw = (
                        not last_draw or
                        now.date() >= last_draw.draw_date + timedelta(weeks=settings.frequency_in_weeks)
                    )
                    if should_draw:
                        # Используем теперь правильную дату
                        if session.query(Draw).filter_by(draw_date=now.date()).first():
                            logger.info(f'Жеребьёвка на дату {now.date()} уже проведена.')
                        else:
                            perform_draw(session, now.date())
        finally:
            session.close()

        await asyncio.sleep(86400)

    logger.info('Демон жеребьёвки завершён.')

if __name__ == '__main__':
    asyncio.run(daemon_loop())
