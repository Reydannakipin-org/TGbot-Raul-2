from datetime import date, datetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext

from handlers.main_handlers import BaseHandler
from states.admins import AddUser
from users.models import Participant, get_session, get_engine, Settings


class AdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.setup_handlers()

    def setup_handlers(self):
        self.message_handler(F.text == 'Добавить участника', self.add_user_button_handler)
        self.state_handler(AddUser.waiting_for_user_id, self.process_user_id)
        self.state_handler(AddUser.waiting_for_full_name, self.process_full_name)
        self.message_handler(F.text == 'Удалить участника', self.delete_user_button_handler)
        self.state_handler(AddUser.waiting_for_delete_user_id, self.process_delete_user_id)
        self.message_handler(F.text == 'Список участников', self.list_users_button_handler)
        self.message_handler(F.text == 'Общ регулярность участия', self.regular_pairing_handler)
        self.state_handler(AddUser.waiting_for_frequency, self.process_pairing_frequency)
        self.message_handler(F.text == 'Приостановить участие', self.pause_user_button_handler)
        self.state_handler(AddUser.waiting_for_pause_user_id, self.process_pause_user_id)
        self.state_handler(AddUser.waiting_for_pause_start_date, self.process_pause_start_date)
        self.state_handler(AddUser.waiting_for_pause_end_date, self.process_pause_end_date)

    async def add_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки добавления пользователя"""

        await message.reply("Пожалуйста, введи ID пользователя:")
        await state.set_state(AddUser.waiting_for_user_id)

    async def process_user_id(self, message: types.Message, state: FSMContext):

        try:
            user_id = int(message.text)
            await message.reply("Теперь введи полное имя пользователя:")
            await state.update_data(user_id=user_id)
            await state.set_state(AddUser.waiting_for_full_name)
        except ValueError:
            await message.reply("Ошибка: ID пользователя должен быть числом. Попробуй снова.")

    async def process_full_name(self, message: types.Message, state: FSMContext):

        try:
            data = await state.get_data()
            user_id = data['user_id']
            name = message.text

            engine = get_engine()
            session = get_session(engine)
            existing_user = session.query(Participant).filter_by(tg_id=user_id).first()
            if existing_user:
                await message.reply("Пользователь с таким ID уже существует")
                return
            new_user = Participant(tg_id=user_id, name=name)
            session.add(new_user)
            session.commit()
            await message.reply(
                f"Пользователь успешно добавлен:\n"
                f"ID: {user_id}\n"
                f"Имя: {name}"
            )
            await state.clear()
        except Exception as e:
            await message.reply(f"Произошла ошибка при добавлении пользователя: {str(e)}")
            await state.clear()
        finally:
            session.close()

    async def delete_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки удаления пользователя"""
        await message.reply("Пожалуйста, введи ID пользователя для удаления:")
        await state.set_state(AddUser.waiting_for_delete_user_id)

    async def process_delete_user_id(self, message: types.Message, state: FSMContext):
        """Обработчик удаления пользователя"""
        try:
            user_id = message.text
            engine = get_engine()
            session = get_session(engine)
            user = session.query(Participant).filter_by(tg_id=user_id).first()
            if user:
                session.delete(user)
                session.commit()
                await message.reply(f"Пользователь с ID {user_id} успешно удален")
            else:
                await message.reply("Пользователь с таким ID не найден")
            await state.clear()
        except Exception as e:
            await message.reply(f"Произошла ошибка при удалении пользователя: {str(e)}")
            await state.clear()
        finally:
            session.close()

    async def list_users_button_handler(self, message: types.Message):
        """Обработчик кнопки просмотра списка пользователей"""
        try:
            engine = get_engine()
            session = get_session(engine)
            users = session.query(Participant).all()

            if users:
                user_list = "\n".join([f"ID: {user.tg_id}, Имя: {user.name}" for user in users])
                await message.reply(f"Список участников:\n{user_list}")
            else:
                await message.reply("Список участников пуст")
        except Exception as e:
            await message.reply(f"Произошла ошибка при получении списка пользователей: {str(e)}")
        finally:
            session.close()


    async def regular_pairing_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки регулярности участия"""
        await message.reply("Пожалуйста, введи желаемую частоту формирования пар (в неделях, допустимые значения: 1, 2, 3 или 4):")
        await state.set_state(AddUser.waiting_for_frequency)

    async def process_pairing_frequency(self, message: types.Message, state: FSMContext):
        """
            Обработчик установки желаемой частоты формирования пар (в неделях).
            Допустимые значения: 1, 2, 3 или 4.
            """
        try:
            frequency = int(message.text.strip())
        except ValueError:
            await message.reply("Некорректное значение. Введи число: 1, 2, 3 или 4.")
            return
        if frequency not in (1, 2, 3, 4):
            await message.reply("Недопустимое значение. Допустимые значения: 1, 2, 3 или 4.")
            return
        engine = get_engine()
        session = get_session(engine)
        try:
            settings = session.query(Settings).first()
            if settings:
                settings.frequency_in_weeks = frequency
            else:
                current_day = date.today().weekday()
                settings = Settings(day_of_week=current_day, frequency_in_weeks=frequency)
                session.add(settings)
            session.commit()
        except Exception as e:
            session.rollback()
            await message.reply(f"Ошибка при сохранении настроек: {e}")
            return
        finally:
            session.close()
        await message.reply(f"Частота формирования пар успешно установлена: раз в {frequency} неделю(ю).")
        await state.clear()

    async def pause_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки приостановки участия пользователя"""
        await message.reply("Пожалуйста, введи ID участника, которого нужно приостановить:")
        await state.set_state(AddUser.waiting_for_pause_user_id)

    async def process_pause_user_id(self, message: types.Message, state: FSMContext):
        """Обработчик приостановки участия пользователя"""
        tg_id = message.text.strip()
        if not tg_id.isdigit():
            await message.reply("ID должен быть числом. Попробуй еще раз:")
            return

        await state.update_data(tg_id=tg_id)
        await message.reply(
            "Теперь введи дату начала приостановки в формате ДД.ММ.ГГГГ:\nНапример, 01.08.2023"
        )
        await state.set_state(AddUser.waiting_for_pause_start_date)

    async def process_pause_start_date(self, message: types.Message, state: FSMContext):
        """Обработчик получения даты начала приостановки"""
        date_str = message.text.strip()
        try:
            pause_start = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            await message.reply("Неверный формат даты. Введи дату в формате ДД.ММ.ГГГГ:")
            return

        await state.update_data(pause_start=pause_start)

        await message.reply(
            "Теперь введи дату окончания приостановки в формате ДД.ММ.ГГГГ:\nНапример, 15.08.2023"
        )
        await state.set_state(AddUser.waiting_for_pause_end_date)

    async def process_pause_end_date(self, message: types.Message, state: FSMContext):
        """Обработчик получения даты окончания приостановки"""
        date_str = message.text.strip()
        try:
            pause_end = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            await message.reply("Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
            return
        data = await state.get_data()
        tg_id = data.get("tg_id")
        pause_start = data.get("pause_start")
        if pause_end < pause_start:
            await message.reply("Дата окончания не может быть меньше даты начала. Попробуй ввести даты заново.")
            return
        engine = get_engine()
        session = get_session(engine)

        participant = session.query(Participant).filter_by(tg_id=tg_id).first()
        if not participant:
            await message.reply("Участник с таким ID не найден.")
            await state.clear()
            return
        participant.exclude_start = pause_start
        participant.exclude_end = pause_end
        session.commit()
        await message.reply(f"Участник {participant.name} успешно приостановлен с {pause_start} по {pause_end}.")

        await state.clear()
