from aiogram.fsm.state import State, StatesGroup


class AddUser(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_full_name = State()
    waiting_for_delete_user_id = State()
    waiting_for_frequency = State()
    waiting_for_pause_user_id = State()
    waiting_for_pause_start_date = State()
    waiting_for_pause_end_date = State()