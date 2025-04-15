from aiogram import Router, F
from aiogram import types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart

from keyboards.reply_kb import (
    MainMenuRolleKeyboard,
    YesNoKeyboard
)
from config import config
# from utils.google_sheets import get_sheet
from utils.lexicon import YES_NO


# TODO:
#  apscheduler - библиотека планировщика задач с ним можно выставить периодичность создания пары
#                                                             (пока только прочитал поверхностно)
#  ПОЛЬЗОВАТЕЛЬ:
#     Реализовать Возможность приостановить участие
#     Реализовать Возможность выйти
#     Оставить отзыв (ссылка на google form) или фотографию
#     Настройка регулярности индивидуального участия в жеребьевке (непонятно какой интервал)
#  АДМИН:
#     Реализовать возможность добавить пользователя в список участников
#     Реализовать возможность удалить пользователя из списка участников
#     Настройка общей регулярности формирования пар 1 раз в 2 недели
#     Показывать список участников
#  БОТ:
#     Загрузка данных в google sheets
#  ПС:
#     Над неймингом надо поработать
#     Меньше хардкода
#


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
        self.message_handler(CommandStart(), self.start_command_access_rights)
        self.message_handler(F.text.in_(YES_NO.keys()), self.handle_main_menu_roles)

    async def start_command_access_rights(self, message: types.Message):
        """Хендлер команды /start, проверяющий является ли пользователь участником чата config.CHAT_ID"""
        user_id = message.from_user.id
        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID, user_id=user_id)
        if chat_user.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]:
            yes_no = YesNoKeyboard().get_keyboard()
            await message.answer('согласие на обработку персональных данных:', reply_markup=yes_no)
        else:
            await message.answer('у вас нет прав доступа к боту')

    async def handle_main_menu_roles(self, message: types.Message):
        """Хендлер кнопок главного меню, выдающий две клавиатуры в зависимости от роли пользователя"""
        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID, user_id=message.from_user.id)
        role = 'admin' if chat_user.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR] else 'member'
        keyboard = MainMenuRolleKeyboard(role).get_keyboard()
        await message.answer('меню администратора', reply_markup=keyboard)