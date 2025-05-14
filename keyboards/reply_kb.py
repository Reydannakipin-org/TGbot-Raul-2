from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from typing import Union
from utils.lexicon import MENU_BUTTONS, BUTTONS


class ReplyBuilder:
    def __init__(self, buttons, rows=1):
        self.keyboard = ReplyKeyboardBuilder()
        self.rows = rows
        self.add_buttons(buttons)
    def add_buttons(self, buttons):
        for button in buttons:
            self.keyboard.add(KeyboardButton(text=button))
    def get_keyboard(self, is_one_time: bool = True):
        return self.keyboard.adjust(self.rows).as_markup(resize_keyboard=True, one_time_keyboard=is_one_time)


class MainMenuRolleKeyboard(ReplyBuilder):
    """Инициализирует клавиатуру с кнопками в зависимости от роли."""

    def __init__(self, role: Union[str, None]):
        super().__init__(MENU_BUTTONS[role], rows=2)


class FeedBackKeyboard(ReplyBuilder):
    def __init__(self, buttons: Union[list[str],str]):
        super().__init__(buttons, rows=2)


class RegularityKeyboard(ReplyBuilder):
    def __init__(self):
        super().__init__(BUTTONS['regular'], rows=1)


class ExitKeyboard(ReplyBuilder):
    def __init__(self, buttons: Union[list[str],str]):
        super().__init__(buttons, rows=2)