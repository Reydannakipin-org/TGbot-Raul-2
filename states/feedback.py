from aiogram.fsm.state import State, StatesGroup

class FeedBack(StatesGroup):
    waiting_for_feedback = State()
    waiting_for_comment = State()
    waiting_for_suggestions = State()
    negative_answer = State()

class ExitBot(StatesGroup):
    waiting_for_exit = State()