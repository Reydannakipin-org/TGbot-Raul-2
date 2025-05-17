from aiogram import Router, F, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from pathlib import Path
from sqlalchemy import or_, select  

from keyboards.reply_kb import (
    ExitKeyboard, FeedBackKeyboard,
    MainMenuRolleKeyboard, RegularityKeyboard
)
from datetime import datetime
from config import config
from states.states import FeedBack
from utils.lexicon import BUTTONS, text
from users.models import (
    Participant, get_engine, get_session,
    Picture, Pair, Draw, Feedback
)


class BaseHandler(Router):
    def __init__(self):
        super().__init__()

    def message_handler(self, filter, handler):
        self.message(filter)(handler)

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
        user = message.from_user
        user_id = user.id

        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID,
                                                      user_id=user_id)
        if chat_user.status not in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        ):
            return await message.answer(text=text['permission'][1])

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=str(user_id))
            )
            participant = result.scalars().first()

            if not participant:
                yes_no = MainMenuRolleKeyboard(role='accept').get_keyboard()
                return await message.answer(text=text['permission'][0],
                                            reply_markup=yes_no)

        return await self.handle_main_menu_roles(message)

    async def handle_main_menu_roles(self, message: types.Message):
        user = message.from_user
        user_id = user.id
        display_name = " ".join(filter(None,
                                       [user.first_name, user.last_name]))

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=str(user_id))
            )
            participant = result.scalars().first()

            if not participant:
                chat_user = await message.bot.get_chat_member(
                    chat_id=config.CHAT_ID, user_id=user_id
                )
                new_p = Participant(
                    tg_id=str(user_id),
                    name=display_name,
                    admin=(chat_user.status in (ChatMemberStatus.ADMINISTRATOR,
                                                ChatMemberStatus.CREATOR)),
                    active=True,
                )
                session.add(new_p)
                await session.commit()

        chat_user = await message.bot.get_chat_member(chat_id=config.CHAT_ID,
                                                      user_id=user_id)
        role = 'admin' if chat_user.status in (
            ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR
        ) else 'member'
        keyboard = MainMenuRolleKeyboard(role).get_keyboard()
        await message.answer(text='Меню', reply_markup=keyboard)


class FeedBackHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.setup_handlers()

    def setup_handlers(self):
        self.message_handler(F.text == 'Обратная связь по встрече',
                             self.feedback_first_step)
        self.message_handler(F.text.in_(BUTTONS['first']),
                             self.handle_feed)
        self.state_handler(FeedBack.waiting_for_feedback,
                           self.waiting_for_feedback)
        self.state_handler(FeedBack.waiting_for_comment,
                           self.handle_feedback)
        self.state_handler(FeedBack.waiting_for_suggestions,
                           self.handle_feedback)
        self.state_handler(FeedBack.negative_answer,
                           self.handle_feedback)

        self.message_handler(F.text == 'Отправка фото',
                             self.handle_ask_for_media)
        self.message_handler(F.photo, self.handle_media)

        self.message_handler(F.text == 'Регулярность участия',
                             self.handle_regularity)
        self.message_handler(F.text.in_(BUTTONS['regular']),
                             self.handle_regular_period)
        self.message_handler(F.text == 'Просмотр уведомлений',
                             self.handle_view_notifications)

        self.message_handler(F.text == 'Выйти из бота', self.handle_exit)
        self.message_handler(F.text == 'Выйти', self.confirm_exit)
        self.message_handler(F.text == 'Остаться', self.cancel_exit)

    async def feedback_first_step(self, message: types.Message,
                                  state: FSMContext):
        tg_id = str(message.from_user.id)

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=tg_id)
            )
            participant = result.scalars().first()

            if not participant:
                await message.answer("Вы не зарегистрированы в системе.")
                return

            result = await session.execute(
                select(Pair, Draw)
                .join(Draw, Pair.draw_id == Draw.id)
                .filter(
                    (Pair.participant1_id == participant.id) |
                    (Pair.participant2_id == participant.id)
                )
                .order_by(Draw.draw_date.desc())
            )
            pair_with_draw = result.first()

            if not pair_with_draw:
                await message.answer("У вас не было встреч, чтобы оставить отзыв.")
                return

            pair, draw = pair_with_draw

            result = await session.execute(
                select(Feedback)
                .filter_by(draw_id=draw.id, participant_id=participant.id)
            )
            feedback = result.scalars().first()

            if feedback and feedback.success is not None:
                await message.answer(
                    "Вы уже оставили отзыв на последнюю встречу. Спасибо!"
                )
                return

        await state.update_data(draw_id=draw.id, participant_id=participant.id)

        await message.answer(
            text=text['feedback_first_step'],
            reply_markup=FeedBackKeyboard(
                buttons=BUTTONS['first']).get_keyboard()
        )

    async def handle_feed(self, message: types.Message, state: FSMContext):
        tg_id = str(message.from_user.id)

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=tg_id)
            )
            participant = result.scalars().first()

            result = await session.execute(
                select(Pair, Draw)
                .join(Draw, Pair.draw_id == Draw.id)
                .filter(
                    (Pair.participant1_id == participant.id) |
                    (Pair.participant2_id == participant.id)
                )
                .order_by(Draw.draw_date.desc())
            )
            pair_with_draw = result.first()

            pair, draw = pair_with_draw

            if message.text not in BUTTONS['first']:
                await message.answer(
                    "Пожалуйста, выберите один из предложенных вариантов."
                )
                return

            feedback = Feedback(draw_id=draw.id, participant_id=participant.id)
            session.add(feedback)

            if message.text == BUTTONS['first'][0]:
                feedback.success = True
                await session.commit()
                await state.update_data(draw_id=draw.id,
                                        participant_id=participant.id)
                await message.answer(
                    text=text['handle_feed'][0],
                    reply_markup=FeedBackKeyboard(
                        buttons=BUTTONS['positive']
                    ).get_keyboard()
                )
                await state.set_state(FeedBack.waiting_for_feedback)
            else:  # Встреча не состоялась
                feedback.success = False
                await session.commit()
                await state.update_data(draw_id=draw.id,
                                        participant_id=participant.id)
                await message.answer(text=text['handle_feed'][1])
                await state.set_state(FeedBack.waiting_for_skip_reason)

    async def waiting_for_feedback(self,
                                   message: types.Message,
                                   state: FSMContext):
        if message.text not in BUTTONS['positive']:
            await message.answer(
                "Пожалуйста, выберите одну из предложенных оценок."
            )
            return

        await state.update_data(rating_text=message.text)

        if message.text == BUTTONS['positive'][0]:
            await message.answer(text=text['waiting_for_feedback'][0])
            await state.set_state(FeedBack.waiting_for_comment)
        else:
            await message.answer(text=text['waiting_for_feedback'][1])
            await state.set_state(FeedBack.waiting_for_suggestions)

    async def handle_feedback(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        draw_id = data.get('draw_id')
        participant_id = data.get('participant_id')

        if not draw_id or not participant_id:
            await message.answer("Произошла ошибка. Попробуйте снова позже.")
            await state.clear()
            return

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Feedback)
                .filter_by(draw_id=draw_id, participant_id=participant_id)
            )
            feedback = result.scalars().first()

            if not feedback:
                await message.answer("Не удалось найти отзыв. Попробуйте ещё раз.")
                await state.clear()
                return

            state_name = await state.get_state()

            if state_name == FeedBack.waiting_for_comment:
                feedback.comment = message.text
            elif state_name == FeedBack.waiting_for_suggestions:
                feedback.skip_reason = message.text

            rating_text = data.get("rating_text")
            if rating_text:
                feedback.rating = (rating_text == BUTTONS['positive'][0])

            await session.commit()

        await message.answer(
            text=text['handle_feedback'],
            reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard()
        )
        await state.clear()

    async def handle_ask_for_media(self, message: types.Message):
        await message.answer(text=text['handle_ask_for_media'])

    async def handle_media(self, message: types.Message):
        user_id = str(message.from_user.id)
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await message.bot.get_file(file_id)
        file_path = Path('media/photos')
        file_path.mkdir(parents=True, exist_ok=True)
        full_path = file_path / file.file_path.split("/")[-1]
        await message.bot.download_file(file.file_path, full_path)

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=user_id)
            )
            participant = result.scalars().first()

            if participant:
                new_picture = Picture(
                    participant_id=participant.id,
                    file_id=file_id,
                    uploaded_at=datetime.utcnow()
                )
                session.add(new_picture)
                await session.commit()

        await message.answer(
            text=text['handle_media'],
            reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard()
        )

    async def handle_regularity(self, message: types.Message):
        await message.answer(
            text=text['handle_regularity'],
            reply_markup=RegularityKeyboard().get_keyboard()
        )

    async def handle_regular_period(self, message: types.Message):
        user_id = str(message.from_user.id)

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=user_id)
            )
            participant = result.scalars().first()

            if message.text == BUTTONS['regular'][0]:
                participant.frequency_individual = 2
                response = 'Вы установили 1 раз в 2 недели'
            elif message.text == BUTTONS['regular'][1]:
                participant.frequency_individual = 3
                response = 'Вы установили 1 раз в 3 недели'
            else:
                participant.frequency_individual = 4
                response = 'Вы установили 1 раз в 4 недели'

            await session.commit()

        await message.answer(text=response)

    async def handle_view_notifications(self, message: types.Message):
        await message.answer(text=text['handle_view_notifications'])
        user_id = str(message.from_user.id)

        async with get_session(get_engine()) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=user_id)
            )
            participant = result.scalars().first()

            if not participant:
                await message.answer("Вы ещё не участвуете в жеребьёвках.")
                return

            result = await session.execute(
                select(Pair)
                .join(Draw)
                .filter(
                    or_(
                        Pair.participant1_id == participant.id,
                        Pair.participant2_id == participant.id
                    )
                )
                .order_by(Draw.draw_date.desc())
            )
            last_pair = result.scalars().first()

            if last_pair:
                if last_pair.participant1_id == participant.id:
                    partner = last_pair.participant2
                else:
                    partner = last_pair.participant1

                if partner:
                    await message.answer(f"Ваша ближайшая пара: {partner.name}")
            else:
                await message.answer("Ваша ближайшая пара пока не определена.")
        session.close()

    async def handle_exit(self, message: types.Message):
        await message.answer(
            text=text['handle_exit'][0],
            reply_markup=ExitKeyboard(buttons=BUTTONS['exit']).get_keyboard()
        )

    async def confirm_exit(self, message: types.Message):
        user_id = str(message.from_user.id)
        engine = get_engine()
        async with get_session(engine) as session:
            result = await session.execute(
                select(Participant).filter_by(tg_id=user_id)
            )
            participant = result.scalars().first()
            if participant:
                await session.delete(participant)
                await session.commit()

        await message.answer(
            "Вы вышли из участия. Возвращайтесь когда будете готовы!",
            reply_markup=types.ReplyKeyboardRemove()
        )

    async def cancel_exit(self, message: types.Message):
        await message.answer(
            "Рады, что вы остаетесь с нами 😊",
            reply_markup=MainMenuRolleKeyboard(role='member').get_keyboard()
        )
