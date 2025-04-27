from aiogram import Router, F
from aiogram import types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.reply_kb import (
    MainMenuRolleKeyboard,
    FeedBackKeyboard, RegularityKeyboard
)
from config import config
from states.states import FeedBack
from utils.lexicon import BUTTONS, text
from utils.handler_util import update_frequency_in_weeks


class BaseHandler(Router):
    def __init__(self):
        super().__init__()


    def message_handler(self, message, handler):
        self.message(message)(handler)


    def callback_handler(self, callback, handler):
        self.callback_query(callback)(handler)


    def state_handler(self, state, handler):
        self.message(state)(handler)


class MainHandler(BaseHandler):
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
            await message.answer(text=text['permission'][0], reply_markup=yes_no)
        else:
            await message.answer(text=text['permission'][1])


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
        self.message_handler(F.text.in_(BUTTONS['first']), self.handle_feed)
        self.state_handler(FeedBack.waiting_for_feedback,self.waiting_for_feedback)
        self.state_handler(FeedBack.waiting_for_comment,self.handle_feedback)
        self.state_handler(FeedBack.waiting_for_suggestions,self.handle_feedback)
        self.state_handler(FeedBack.negative_answer,self.handle_feedback)

        self.message_handler(F.text == 'Отправка фото',self.handle_ask_for_media)
        self.message_handler(F.photo, self.handle_media)

        self.message_handler(F.text == 'Регулярность участия', self.handle_regularity)
        self.message_handler(F.text.in_(BUTTONS['regular']), self.handle_regular_period)
        self.message_handler(F.text == 'Просмотр уведомлений', self.handle_view_notifications)
        self.message_handler(F.text == 'Выйти из бота', self.handle_exit)


    async def feedback_first_step(self, message: types.Message):
        await message.answer(
            text=text['feedback_first_step'],
            reply_markup=FeedBackKeyboard(buttons=BUTTONS['first']).get_keyboard())


    async def handle_feed(self, message: types.Message, state: FSMContext):
        """Хендлер о результате встречи в зависимости от ответа выдает результат"""
        if message.text == BUTTONS['first'][0]:
            await message.answer(
                text=text['handle_feed'][0],
                reply_markup=FeedBackKeyboard(buttons=BUTTONS['positive']).get_keyboard())
            await state.set_state(FeedBack.waiting_for_feedback)
        else:
            await message.answer(
                text=text['handle_feed'][1])
            await state.set_state(FeedBack.negative_answer)


    async def waiting_for_feedback(self, message: types.Message, state: FSMContext):
        """Хендлер для ответа на вопрос о положительном или отрицательном результате встречи"""
        if message.text == BUTTONS['positive'][0]:
            await message.answer(
                text=text['waiting_for_feedback'][0])
            await state.set_state(FeedBack.waiting_for_comment)
        else:
            await state.set_state(FeedBack.waiting_for_suggestions)
            await message.answer(text=text['waiting_for_feedback'][1])


    async def handle_feedback(self, message: types.Message, state: FSMContext):
        """Загружает все отзывы в файл пока что"""
        # comment = message.text
        # async with async_session as session:
        #     new_comment = Comment(comment_text=comment)
        #     session.add(new_comment)
        #     await session.commit()
        await message.answer(text=text['handle_feedback'],reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())
        await state.clear()


    async def handle_ask_for_media(self, message: types.Message):
        """Хендлер для загрузки фото/видео файлов в папку проекта (нужно в бд)"""
        await message.answer(text=text['handle_ask_for_media'])


    async def handle_media(self, message: types.Message):
        """Хендлер для загрузки фото/видео файлов в папку проекта (нужно в бд)"""
        file = await message.bot.get_file(message.photo[-1].file_id)
        file_path = Path('media/photos') / file.file_path.split("/")[-1]

        await message.bot.download_file(file.file_path, file_path)

        await message.answer(text=text['handle_media'],reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())

#             ------------------------РЕГУЛЯРНОСТЬ-------------------------------------

    async def handle_regularity(self, message: types.Message):
        await message.answer(text=text['handle_regularity'],reply_markup=RegularityKeyboard().get_keyboard())


    async def handle_regular_period(self, message: types.Message, session: AsyncSession):
        if message.text == BUTTONS['regular'][0]:
            await update_frequency_in_weeks(session=session,weeks=2)
            await message.answer(text='Вы установили 1 раз в 2 недели')
        if message.text == BUTTONS['regular'][1]:
            await update_frequency_in_weeks(session=session, weeks=3)
            await message.answer(text='Вы установили 1 раз в 3 недели')
        if message.text == BUTTONS['regular'][2]:
            await update_frequency_in_weeks(session=session, weeks=4)
            await message.answer(text='Вы установили 1 раз в 4 недели')


    async def handle_view_notifications(self, message: types.Message):
        await message.answer(text=text['handle_view_notifications'])

#   -------------------ВЫХОД ИЗ БОТА------------------------------------

    async def handle_exit(self, message: types.Message):
        await message.answer(
            text=text['handle_exit'][0],
            reply_markup=FeedBackKeyboard(buttons=BUTTONS['first']).get_keyboard())
        #Подключить состояние exit_bot
        # if message.text == BUTTONS['first'][0]:
        #     await message.answer(
        #         text=text['handle_exit'][1])
        # else:
        #     await message.answer(text=text['handle_exit'][2],reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard())


















