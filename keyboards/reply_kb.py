from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from utils.lexicon import menu_buttons, YES_NO


class ReplyBuilder:
    def __init__(self, buttons, rows=1):
        self.keyboard = ReplyKeyboardBuilder()
        self.rows = rows
        self.add_buttons(buttons)
    def add_buttons(self, buttons):
        for button in buttons:
            self.keyboard.add(KeyboardButton(text=button))
    def get_keyboard(self):
        return self.keyboard.adjust(self.rows).as_markup(resize_keyboard=True)


class MainMenuRolleKeyboard(ReplyBuilder):
    """Инициализирует клавиатуру с кнопками в зависимости от роли."""

    def __init__(self, role):
        super().__init__(menu_buttons[role], rows=2)


class YesNoKeyboard(ReplyBuilder):
    """Инициализирует клавиатуру с кнопками Да/Нет."""

    def __init__(self):
        super().__init__(YES_NO.keys(), rows=2)
