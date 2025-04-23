import os
from aiogram import Router, F
from aiogram import types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path

from keyboards.reply_kb import (
    MainMenuRolleKeyboard,
    FeedBackKeyboard, RegularityKeyboard
)
from config import config
from states.feedback import FeedBack
from utils.lexicon import feedback,regularity
# from utils.google_sheets import get_sheet



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


class BaseHandler(Router):
    def __init__(self):
        super().__init__()

    def message_handler(self, message, handler):
        self.message(message)(handler)

    def callback_handler(self, callback, handler):
        self.callback_query(callback)(handler)

    def state_handler(self, state, handler):
        self.message(state)(handler)

class KeyboardHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.setup_handlers()

    def setup_handlers(self):
        self.message_handler(CommandStart(), self.start_command_access_rights)
        self.message_handler(F.text == 'Согласен', self.handle_main_menu_roles)


    async def start_command_access_rights(self, message: types.Message):
        """Хендлер команды /start, проверяющий является ли пользователь участником чата config.CHAT_ID"""
        user_id = message.from_user.id
        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID, user_id=user_id)
        if chat_user.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]:
            yes_no = MainMenuRolleKeyboard(role='accept').get_keyboard()
            await message.answer('согласие на обработку персональных данных:', reply_markup=yes_no)
        else:
            await message.answer('у вас нет прав доступа к боту')

    async def handle_main_menu_roles(self, message: types.Message):
        """Хендлер кнопок главного меню, выдающий две клавиатуры в зависимости от роли пользователя"""
        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID, user_id=message.from_user.id)
        role = 'member' if chat_user.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR] else 'admin'
        keyboard = MainMenuRolleKeyboard(role).get_keyboard()
        await message.answer(text='Меню', reply_markup=keyboard)



class  FeedBackHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.setup_handlers()

    def setup_handlers(self):
        self.message_handler(F.text == 'Обратная связь по встрече', self.feedback_first_step)
        self.message_handler(F.text.in_(feedback['first']), self.handle_feed)
        self.state_handler(FeedBack.waiting_for_feedback,self.waiting_for_feedback)
        self.state_handler(FeedBack.waiting_for_comment,self.handle_feedback)
        self.state_handler(FeedBack.waiting_for_suggestions,self.handle_feedback)
        self.state_handler(FeedBack.negative_answer,self.handle_feedback)

        self.message_handler(F.text == 'Отправка фото',self.handle_ask_for_media)
        self.message_handler(F.photo, self.handle_media)

        self.message_handler(F.text == 'Регулярность участия', self.handle_regularity)
        self.message_handler(F.text.in_(regularity['regular']), self.handle_regular_period)
        self.message_handler(F.text == 'Просмотр уведомлений', self.handle_view_notifications)
        self.message_handler(F.text == 'Выйти из бота', self.handle_exit)


    async def feedback_first_step(self, message: types.Message):
        await message.answer(
            text='Состоялась ли у тебя последняя запланированная встреча?',
            reply_markup=FeedBackKeyboard(buttons=feedback['first']).get_keyboard())


    async def handle_feed(self, message: types.Message, state: FSMContext):
        """Хендлер о результате встречи в зависимости от ответа выдает результат"""
        if message.text == feedback['first'][0]:
            await message.answer(
                text='Была ли встреча положительной или имеются точки роста?',
                reply_markup=FeedBackKeyboard(buttons=feedback['positive']).get_keyboard())
            await state.set_state(FeedBack.waiting_for_feedback)
        else:
            await message.answer(
                text='Укажи причины отсутствия встречи на текущий момент и возможные запланированные даты встреч в поле для сообщений')
            await state.set_state(FeedBack.negative_answer)



    async def waiting_for_feedback(self, message: types.Message, state: FSMContext):
        """Хендлер для ответа на вопрос о положительном или отрицательном результате встречи"""
        if message.text == feedback['positive'][0]:
            await message.answer(
                text='Если хочешь оставить какие-либо комментарии и пожелания укажи в поле для сообщения ниже')
            await state.set_state(FeedBack.waiting_for_comment)
        else:
            await state.set_state(FeedBack.waiting_for_suggestions)
            await message.answer(text='Оставь, пожалуйста, комментарии и пожелания в поле для сообщений')

    async def handle_feedback(self, message: types.Message,state: FSMContext):
        """Загружает все отзывы в файл пока что"""
        with open('comments.txt', 'a', encoding='utf-8') as f:
            f.write(f'Комментарий: {message.text}\n')
        await message.answer(text=f'Спасибо за обратную связь!',reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())
        await state.clear()

    async def handle_ask_for_media(self, message: types.Message):
        """Хендлер для загрузки фото/видео файлов в папку проекта (нужно в бд)"""
        await message.answer(text='Ты можешь отправить фото/видео,используя прикрепление или отправку медиафайлов')


    async def handle_media(self, message: types.Message):
        """Хендлер для загрузки фото/видео файлов в папку проекта (нужно в бд)"""
        file = await message.bot.get_file(message.photo[-1].file_id)
        file_path = Path('media/photos') / file.file_path.split("/")[-1]

        await message.bot.download_file(file.file_path, file_path)

        await message.answer(text='Спасибо тебе,отличное фото!',reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())

#             ------------------------РЕГУЛЯРНОСТЬ-------------------------------------

    async def handle_regularity(self, message: types.Message):
        await message.answer(text='Выбор регулярности участия',reply_markup=RegularityKeyboard().get_keyboard())


    async def handle_regular_period(self, message: types.Message):
        if message.text == regularity['regular'][0]:
            await message.answer(text='2 недели')
        if message.text == regularity['regular'][1]:
            await message.answer(text='3 недели')
        if message.text == regularity['regular'][2]:
            await message.answer(text='4 недели')

    async def handle_view_notifications(self, message: types.Message):
        await message.answer(text='Просмотр уведомлений')

#   -------------------ВЫХОД ИЗ БОТА------------------------------------

    async def handle_exit(self, message: types.Message):
        await message.answer(
            text='Нам очень печально это читать(\nНо,ты точно уверен,что хочешь исключиться из списка участников Random Coffe',
            reply_markup=FeedBackKeyboard(buttons=feedback['first']).get_keyboard())
        #Подключить состояние exit_bot
        # if message.text == feedback['first'][0]:
        #     await message.answer(
        #         text='Очень жаль(\nНу что же , если передумаешь и захочешь вернуться,пиши в личке администратору и мы что нибудь придумаем!')
        # else:
        #     await message.answer(text='Фуух)\nЗначит опечатка и встречаемся дальше',reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())


















