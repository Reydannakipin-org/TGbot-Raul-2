from aiogram import types
from aiogram.types import Message

from database.db import Database
from aiogram.fsm.context import FSMContext


async def add_user_button_handler(message: types.Message, state: FSMContext):

    await message.reply("Пожалуйста, введите ID пользователя:")
    await state.set_state("waiting_for_user_id")
async def process_user_id(message: types.Message, state: FSMContext):

    try:
        user_id = int(message.text)
        await message.reply("Теперь введите полное имя пользователя:")
        await state.update_data(user_id=user_id)
        await state.set_state("waiting_for_full_name")
    except ValueError:
        await message.reply("Ошибка: ID пользователя должен быть числом. Попробуйте снова.")
async def process_full_name(message: types.Message, state: FSMContext):

    try:
        data = await state.get_data()
        user_id = data['user_id']
        full_name = message.text
        db = Database('users.db')
        db.add_user(telegram_id=user_id, full_name=full_name)
        await message.reply(
            f"Пользователь успешно добавлен:\n"
            f"ID: {user_id}\n"
            f"Имя: {full_name}"
        )
        await state.clear()
    except Exception as e:
        await message.reply(f"Произошла ошибка при добавлении пользователя: {str(e)}")
        await state.clear()



async def delete_user_button_handler(message: types.Message, state: FSMContext):

    await message.reply("Пожалуйста, введите ID пользователя для удаления:")
    await state.set_state("waiting_for_delete_user_id")

async def process_delete_user_id(message: types.Message, state: FSMContext):

    try:
        user_id = int(message.text)
        db = Database('users.db')
        db.delete_user(telegram_id=user_id)
        await message.reply(f"Пользователь с ID {user_id} успешно удален")
        await state.clear()
    except ValueError:
        await message.reply("Ошибка: ID пользователя должен быть числом. Попробуйте снова.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при удалении пользователя: {str(e)}")
        await state.clear()


async def list_users_button_handler(message: types.Message):

    users = db.get_users()
    if users:
        user_list = "\n".join([f"ID: {user[0]}, Имя: {user[1]}" for user in users])
        await message.reply(f"Список участников:\n{user_list}")
    else:
        await message.reply("Список участников пуст")


async def regular_pairing_handler(message: Message, state: FSMContext):

    try:
        # Ask user for pairing frequency
        await message.reply("Пожалуйста, введите желаемую частоту формирования пар (в днях):")
        await state.set_state("waiting_for_frequency")
    except Exception as e:
        await message.reply(f"Произошла ошибка при настройке регулярности: {str(e)}")
async def process_pairing_frequency(message: Message, state: FSMContext):

    try:
        frequency = int(message.text)
        if frequency <= 0:
            await message.reply("Частота должна быть положительным числом. Попробуйте снова.")
            return
        # Update the pairing frequency in the database
        db = Database('users.db')
        db.update_pairing_frequency(frequency=frequency)
        await message.reply(
            f"Общая регулярность формирования пар успешно установлена на 1 раз в {frequency} дней"
        )
        await state.clear()
    except ValueError:
        await message.reply("Ошибка: частота должна быть числом. Попробуйте снова.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при настройке регулярности: {str(e)}")
        await state.clear()