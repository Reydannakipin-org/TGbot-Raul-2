from aiogram import Router
from aiogram import types
from aiogram.filters import Command

from keyboards.reply_kb import MenuKeyboard, UserKeyboard, AdminKeyboard


ALLOWED_USERS = [
    11111111
]


class BaseHandler(Router):
    def __init__(self):
        super().__init__()

    def message_handler(self, message, handler):
        self.message(message)(handler)

    def callback_handler(self, callback, handler):
        self.callback_query(callback)(handler)


class KeyboardHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.setup_handlers()

    def setup_handlers(self):
        self.message_handler(Command("start"), self.start_command)
        self.message_handler(lambda m: m.text == "👤 Меню пользователя", self.handle_user)
        self.message_handler(lambda m: m.text == "👨‍💼 Меню администратора", self.handle_admin)

    async def start_command(self, message: types.Message):
        keyboard = MenuKeyboard().get_keyboard()
        await message.answer("Выберите действие:", reply_markup=keyboard)

    async def handle_user(self, message: types.Message):
        """Обработчик кнопок пользовательского меню"""
        keyboard = UserKeyboard().get_keyboard()
        await message.answer("Выберите действие:", reply_markup=keyboard)

    async def handle_admin(self, message: types.Message):
        """Обработчик кнопок административного меню"""
        if message.from_user.id not in ALLOWED_USERS:
            await message.answer("У вас нет прав администратора")
            return
        keyboard = AdminKeyboard().get_keyboard()
        await message.answer("Меню администратора:", reply_markup=keyboard)