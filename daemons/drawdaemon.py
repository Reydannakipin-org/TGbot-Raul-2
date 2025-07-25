import os
import asyncio
import collections
import signal
import logging
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Union

from aiogram import Bot
from aiogram.types import ChatMember
from aiogram.exceptions import TelegramBadRequest

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from users.models import (
    get_engine,
    Draw, Pair, Settings,
    Participant, Cycle
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# Логирование в консоль и в файл
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Файл
file_handler = logging.FileHandler('drawdaemon.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

should_run = True
engine = get_engine()


def handle_shutdown():
    global should_run
    logger.info('Остановка демона жеребьёвки...')
    should_run = False


def match_pairs(participants, previous_pairs):
    previous_set = set((min(a, b), max(a, b)) for a, b in previous_pairs)
    
    id_map = {p.id: p for p in participants}
    ids = list(id_map.keys())
    random.shuffle(ids)

    used = set((min(a, b), max(a, b)) for a, b in previous_pairs)

    neighbors = collections.defaultdict(set)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if (min(a, b), max(a, b)) not in used:
                neighbors[a].add(b)
                neighbors[b].add(a)

    unmatched = set(ids)
    pairs = []

    while unmatched:
        a = unmatched.pop()
        candidates = neighbors[a] & unmatched
        if not candidates:
            unmatched.add(a)
            break 
        b = random.choice(list(candidates))
        unmatched.remove(b)
        pairs.append([id_map[a], id_map[b]])

    leftovers = [id_map[i] for i in unmatched]
    for lone in leftovers:
        candidates = []
        for pair in pairs:
            if len(pair) >= 3:
                continue
            id_pair = [p.id for p in pair]
            conflict = False
            for pid in id_pair:
                if (min(lone.id, pid), max(lone.id, pid)) in previous_set:
                    conflict = True
                    break
            if not conflict:
                candidates.append(pair)
        if candidates:
            chosen = random.choice(candidates)
            chosen.append(lone)
            logger.info(f"Участник {lone.name} добавлен третьим в пару.")
        else:
            logger.info(f"Участник {lone.name} остался без пары.")

    return pairs


async def get_or_create_cycle(session, actual_participants):
    total_possible = len(actual_participants) * (len(actual_participants) - 1) // 2

    if total_possible == 0:
        return None
    result = await session.execute(
        select(Pair).join(Draw).join(Cycle).order_by(Cycle.id.desc())
    )
    previous_pairs = result.scalars().all()

    unique_pairs = set()
    actual_ids = set(p.id for p in actual_participants)
    for pair in previous_pairs:
        ids = [pair.participant1_id, pair.participant2_id]
        if pair.participant3_id:
            ids.append(pair.participant3_id)
        filtered_ids = [i for i in ids if i in actual_ids]
        for i in range(len(filtered_ids)):
            for j in range(i + 1, len(filtered_ids)):
                unique_pairs.add(tuple(sorted((filtered_ids[i], filtered_ids[j]))))

    if len(unique_pairs) / total_possible >= 0.9:
        logger.info("90% возможных пар среди текущих участников реализовано — создаём новый цикл жеребьёвки.")
        new_cycle = Cycle(start_date=datetime.now().date())
        session.add(new_cycle)
        await session.commit()
        return new_cycle 
    
    result = await session.execute(select(Cycle).order_by(Cycle.id.desc()))
    current_cycle = result.scalars().first()
    if not current_cycle:
        current_cycle = Cycle(start_date=datetime.now().date())
        session.add(current_cycle)
        await session.commit()

    return current_cycle

async def is_user_in_chat(bot: Bot, chat_id: Union[int, str], user_id: int) -> bool:
    try:
        member: ChatMember = await bot.get_chat_member(chat_id, user_id)
        return member.status in ('member', 'administrator', 'creator')
    except TelegramBadRequest:
        return False


async def get_actual_participants(bot: Bot, session, chat_id: Union[int, str]):
    today = datetime.now().date()
    now = datetime.now()
    participants = (await session.execute(
        select(Participant).where(Participant.active == True, Participant.admin == False)
    )).scalars().all()

    actual = []

    for p in participants:
        if p.exclude_start and p.exclude_end:
            if p.exclude_start <= today <= p.exclude_end:
                logger.info(
                    f'Участник {p.name} исключён из участия в жеребьёвке до {p.exclude_end}.'
                )
                continue
        if await is_user_in_chat(bot, chat_id, p.tg_id):
            result = await session.execute(
                select(Draw.draw_date).join(Pair).filter(
                    (Pair.participant1_id == p.id) |
                    (Pair.participant2_id == p.id) |
                    (Pair.participant3_id == p.id)
                ).order_by(Draw.draw_date.desc()).limit(1)
            )
            last_draw_date = result.first()
            if last_draw_date:
#                weeks_passed = (today - last_draw_date[0]).days // 7
                weeks_passed = (now - last_draw_date[0]).total_seconds() // 600 # 300 сек тестовый режим
                #if weeks_passed < p.frequency_individual:
                if weeks_passed < p.frequency_individual:
                    logger.info(
                        f'Участник {p.name} пропускает жеребьёвку — прошло '
                        f'{weeks_passed} недель из {p.frequency_individual}.'
                    )
                    continue
            actual.append(p)
        else:
            logger.info(f'Пользователь {p.name} (id={p.tg_id}) больше не в чате — исключён.')
            p.active = False

    await session.commit()
    return actual

async def refresh_participants_status(bot: Bot, session, chat_id: Union[int, str]):
    participants = (await session.execute(
        select(Participant).where(Participant.active == True)
    )).scalars().all()

    for p in participants:
        try:
            member = await bot.get_chat_member(chat_id, p.tg_id)
            in_chat = await is_user_in_chat(bot, chat_id, p.tg_id)
       

            if not in_chat:
                p.active = False
                logger.info(f'Пользователь {p.name} (id={p.tg_id}) больше не в чате — деактивирован.')
                if p.admin:
                    p.admin = False
                    logger.info(f'Пользователь {p.name} (id={p.tg_id}) вышел из чата и больше не админ.')
                else:
                    logger.info(f'Пользователь {p.name} (id={p.tg_id}) больше не в чате — деактивирован.')
            else:
                was_admin = p.admin
                is_now_admin = member.status in ('administrator', 'creator')
                if was_admin != is_now_admin:
                    p.admin = is_now_admin
                    if is_now_admin:
                        logger.info(f'Пользователь {p.name} стал администратором — обновлено в БД.')
                    else:
                        logger.info(f'Пользователь {p.name} больше не администратор — обновлено в БД.')
        except Exception as e:
            logger.warning(f'Не удалось проверить участника {p.name} (id={p.tg_id}): {e}')
            continue
    await session.commit()


async def save_draw(session, draw_date, current_cycle, pairs):
    draw = Draw(draw_date=draw_date, cycle_id=current_cycle.id)
    session.add(draw)
    await session.flush()

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

    await session.commit()
    logger.info(
        f'Жеребьёвка на {draw_date} завершена. Сформировано пар: {len(pairs)}.'
    )
    return draw


async def perform_draw(bot: Bot, session, draw_date):
    # Проверка существующей жеребьёвки закомментировать для теста
#    existing = await session.execute(select(Draw).filter_by(draw_date=draw_date))
#    if existing.scalars().first():
#        logger.info(f'Жеребьёвка на дату {draw_date} уже проведена.')
#        return None, []
    
    participants = await get_actual_participants(bot, session, CHAT_ID)
    if len(participants) < 2:
        logger.info('Недостаточно участников для жеребьёвки.')
        return None, []

    current_cycle = await get_or_create_cycle(session, participants)


    result = await session.execute(
        select(Pair).join(Draw).filter(Draw.cycle_id == current_cycle.id)
    )
    previous_pairs = result.scalars().all()

    previous_set = set()
    for p in previous_pairs:
        previous_set.add((p.participant1_id, p.participant2_id))
        previous_set.add((p.participant2_id, p.participant1_id))

    
    pairs = []
    for attempt in range(7):
        pairs = match_pairs(participants, previous_set)
        if pairs:
            logger.info(f'Успешно подобраны пары с {attempt + 1}-й попытки.')
        break

    if not pairs:
        logger.info('Нет новых возможных пар. Пробуем fallback жеребьёвку.')
        fallback_pairs = match_pairs(participants, previous_set=set())
        if fallback_pairs:
            logger.info('Fallback жеребьёвка сработала.')
            return await save_draw(session, draw_date, current_cycle, fallback_pairs), fallback_pairs
        else:
            logger.info('Даже fallback не дал результата — участников слишком мало.')
            return None, []


    return await save_draw(session, draw_date, current_cycle, pairs), pairs


async def daemon_loop(bot: Bot):
    global should_run
    logger.info('Запуск демона жеребьёвки...')

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)

    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

    while should_run:
        async with async_session() as session:
            try:
                result = await session.execute(select(Settings))
                settings = result.scalars().first()
                if not settings:
                    await asyncio.sleep(1800)
                    continue
                try:
                    await refresh_participants_status(bot, session, CHAT_ID)
                except Exception as e:
                    logger.warning(f'Ошибка при проверке участников в чате: {e}')
                now = datetime.now()
                logger.info(f'сейчас {now}')

                last_draw = (await session.execute(
                    select(Draw).order_by(Draw.draw_date.desc()).limit(1)
                )).scalars().first()
                need_draw = False
                if not last_draw:
                    need_draw = True
#                elif now >= last_draw.draw_date + timedelta(weeks=settings.frequency_in_weeks):
                elif now >= last_draw.draw_date + timedelta(minutes=settings.frequency_in_weeks*10):
 
                   need_draw = True

                if (need_draw): # and 
                #    now.weekday() == settings.day_of_week and 
                #    12 <= now.hour < 14):
                    logger.info('Проходит жеребьёвка')
                    draw, pairs = await perform_draw(bot, session, now)
                    if pairs:
                        for pair in pairs:
                            p1, p2 = pair[0], pair[1]
                            p3 = pair[2] if len(pair) > 2 else None
                            names = [p1.name, p2.name] + ([p3.name] if p3 else [])
                            msg = 'Ваша группа для ближайшей встречи: ' + ', '.join(names)

                            for p in [p1, p2] + ([p3] if p3 else []):
                                try:
                                    await bot.send_message(int(p.tg_id), msg)
                                except Exception as e:
                                    logger.warning(f'Не удалось отправить сообщение: {e}')

            except Exception as e:
                logger.error(f'Ошибка в демоне жеребьёвки: {e}')

        await asyncio.sleep(120)

    logger.info('Демон жеребьёвки остановлен.')


async def init_db():
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        result = await session.execute(select(Settings))
        settings = result.scalars().first()

        if not settings:
            settings = Settings(day_of_week=2, frequency_in_weeks=2)
            session.add(settings)
            await session.commit()
            logger.info('Настройки созданы: среду, раз в 2 недели.')
        else:
            if settings.day_of_week != 0:
                settings.day_of_week = 0
                await session.commit()
                logger.info('День недели обновлён на понедельник.')
            else:
                logger.info('Настройки уже существуют и день недели — понедельник.')


if __name__ == '__main__':
    asyncio.run(init_db())
