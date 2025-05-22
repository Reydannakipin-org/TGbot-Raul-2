import os
from datetime import datetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from dotenv import load_dotenv

from handlers.main_handlers import BaseHandler, MainMenuRolleKeyboard
from states.admins import AddUser
from utils.handler_util import (
    async_add_user,
    async_delete_user,
    async_list_users,
    async_update_frequency,
    async_set_user_pause,
)
from utils.report import generate_report_file

load_dotenv()

REPORTS_DIR = "reports"


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
        self.message_handler(F.text == 'Выгрузить отчет', self.export_report_handler)
        self.message_handler(F.text == 'Выгрузить отчет', self.export_report_handler)
        self.state_handler(AddUser.waiting_for_pause_user_id, self.process_pause_user_id)
        self.state_handler(AddUser.waiting_for_pause_start_date, self.process_pause_start_date)
        self.state_handler(AddUser.waiting_for_pause_end_date, self.process_pause_end_date)

    async def add_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки добавления пользователя"""
        await message.reply("Пожалуйста, введи ID пользователя:")
        await state.set_state(AddUser.waiting_for_user_id)

    async def process_user_id(self, message: types.Message, state: FSMContext):
        """Обработчик добавления пользователя"""
        try:
            user_id = int(message.text)
            await message.reply("Теперь введи полное имя пользователя:")
            await state.update_data(user_id=user_id)
            await state.set_state(AddUser.waiting_for_full_name)
        except ValueError:
            await message.reply("Ошибка: ID пользователя должен быть числом. Попробуй снова.")

    async def process_full_name(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_id = data.get('user_id')
        name = message.text
        result = await async_add_user(user_id, name)
        if result == "exists":
            await message.reply("Пользователь с таким ID уже существует")
        elif result == "added":
            await message.reply(
                f"Пользователь успешно добавлен:\n"
                f"ID: {user_id}\n"
                f"Имя: {name}",
                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard()
            )
        else:
            await message.reply("Произошла ошибка при добавлении пользователя.",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        await state.clear()

    async def delete_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки удаления пользователя"""
        await message.reply("Пожалуйста, введи ID пользователя для удаления:")
        await state.set_state(AddUser.waiting_for_delete_user_id)

    async def export_report_handler(self, message: types.Message):
        """Обработчик кнопки 'Выгрузить отчет' — вызывает генератор Excel и отправляет файл"""

        try:
            stream = await generate_report_file()
            os.makedirs(REPORTS_DIR, exist_ok=True)
            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"random_coffee_report_{now_str}.xlsx"
            filepath = os.path.join(REPORTS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(stream.read())
            file_to_send = FSInputFile(path=filepath)
            await message.answer_document(file_to_send, caption="Вот отчет по жеребьевкам",
                                          reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())

        except Exception as e:
            await message.reply(f"Произошла ошибка при формировании отчета: {e}",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())

    async def process_delete_user_id(self, message: types.Message, state: FSMContext):
        """Обработчик удаления пользователя"""
        try:
            user_id = int(message.text)
        except ValueError:
            await message.reply("Ошибка: ID должен быть числом.")
            return
        success = await async_delete_user(user_id)
        if success:
            await message.reply(f"Пользователь с ID {user_id} успешно удален",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        else:
            await message.reply("Пользователь с таким ID не найден",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        await state.clear()

    async def list_users_button_handler(self, message: types.Message):
        """Обработчик кнопки просмотра списка пользователей"""
        users = await async_list_users()
        if users:
            user_lines = []
            for user in users:
                status = "Активен" if user.active else "Неактивен"
                admin_tag = ", админ" if user.admin else ""
                user_lines.append(f"ID: {user.tg_id}, Имя: {user.name} ({status}{admin_tag})")
            await message.reply(f"Список участников:\n" + "\n".join(user_lines),
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        else:
            await message.reply("Список участников пуст",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())

    async def regular_pairing_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки регулярности участия"""
        await message.reply(
            "Пожалуйста, введи желаемую частоту формирования пар (в неделях, допустимые значения: 1, 2, 3 или 4):"
        )
        await state.set_state(AddUser.waiting_for_frequency)

    async def process_pairing_frequency(self, message: types.Message, state: FSMContext):
        """Обработчик установки желаемой частоты формирования пар (в неделях).
            Допустимые значения: 1, 2, 3 или 4."""
        try:
            frequency = int(message.text.strip())
        except ValueError:
            await message.reply("Некорректное значение. Введи число: 1, 2, 3 или 4.")
            return
        if frequency not in (1, 2, 3, 4):
            await message.reply("Недопустимое значение. Допустимые значения: 1, 2, 3 или 4.")
            return
        success = await async_update_frequency(frequency)
        if success:
            await message.reply(f"Частота формирования пар успешно установлена: раз в {frequency} неделю(ю).",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        else:
            await message.reply("Ошибка при обновлении настроек.",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        await state.clear()

    async def pause_user_button_handler(self, message: types.Message, state: FSMContext):
        """Обработчик кнопки приостановки участия пользователя"""
        await message.reply("Пожалуйста, введи ID участника, которого нужно приостановить:")
        await state.set_state(AddUser.waiting_for_pause_user_id)

    async def process_pause_user_id(self, message: types.Message, state: FSMContext):
        """Обработчик приостановки участия пользователя"""
        tg_id_text = message.text.strip()
        if not tg_id_text.isdigit():
            await message.reply("ID должен быть числом. Попробуй еще раз:")
            return
        await state.update_data(tg_id=int(tg_id_text))
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
        success = await async_set_user_pause(tg_id, pause_start, pause_end)
        if success:
            await message.reply(f"Участник с ID {tg_id} успешно приостановлен с {pause_start} по {pause_end}.",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        else:
            await message.reply("Участник с таким ID не найден.",
                                reply_markup=MainMenuRolleKeyboard(role='admin').get_keyboard())
        await state.clear()
