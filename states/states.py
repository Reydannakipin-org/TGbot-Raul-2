from aiogram.fsm.state import State, StatesGroup

class FeedBack(StatesGroup):
    waiting_for_feedback = State()
    waiting_for_comment = State()
    waiting_for_suggestions = State()
    negative_answer = State()

class ExitBot(StatesGroup):
    exit_bot = State()


class Regularity(StatesGroup):
    two_weeks = State()
    three_weeks = State()
    four_weeks = State()