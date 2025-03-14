import os
import re
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import *

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")  # Загружает переменные из .env
API_TOKEN = str(os.getenv("TOKEN"))  # Получает значение

# Настройки

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

class TaskStates(StatesGroup):
    ADD_DESCRIPTION = State()
    ADD_DEADLINE = State()
    PROCESS_TASK = State()
    DELETE_TASK = State()

def init_db():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Не выполнено',
            deadline TEXT,
            category TEXT,
            priority TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def format_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')

async def send_reminders():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM tasks WHERE status = 'Не выполнено' AND deadline IS NOT NULL"
    )
    tasks = cursor.fetchall()
    conn.close()
    for task in tasks:
        user_id = task[1]
        deadline = datetime.strptime(task[5], '%Y-%m-%d')
        now = datetime.now()
        delta = deadline - now
        if delta.days <= 1 or delta.total_seconds() <= 3600:
            await bot.send_message(
                user_id,
                f"⚠️ Напоминание: Задача '{task[2]}' завершается {format_date(task[5])}!"
            )

async def start_scheduler():
    scheduler.add_job(send_reminders, 'interval', minutes=10)
    scheduler.start()

# Регистрация хендлеров
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для управления задачами. Используйте /help для справки.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="/add")],
                [KeyboardButton(text="/list")],
                [KeyboardButton(text="/delete")],
                [KeyboardButton(text="/help")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/add — добавить задачу\n"
        "/list — показать все задачи\n"
        "/active — активные задачи\n"
        "/completed — завершенные задачи\n"
        "/due — задачи с дедлайном\n"
        "/delete [ID] — удалить задачу\n"
        "/clear — очистить список\n"
        "/export — скачать CSV\n"
    )

@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await message.answer("Название задачи:")
    await state.set_state(TaskStates.ADD_DESCRIPTION)
    
@dp.message(StateFilter(TaskStates.ADD_DESCRIPTION))
async def process_name(message: Message, state: FSMContext):
    await message.answer("add_description")
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer("Описание (или /skip):")
    await state.set_state(TaskStates.ADD_DEADLINE)

@dp.message(StateFilter(TaskStates.ADD_DEADLINE))
async def process_skip_description(message: Message, state: FSMContext):
    await message.answer("not skip description")
    description = message.text.strip() if message.text != "/skip" else ''
    await state.update_data(description=description)
    await message.answer("Дедлайн (YYYY-MM-DD) или /skip:")
    await state.set_state(TaskStates.PROCESS_TASK)


@dp.message(TaskStates.PROCESS_TASK)
async def process_deadline(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    description = data.get('description', '')
    deadline = message.text.strip() if message.text != "/skip" else None

    add_task(
        user_id=message.from_user.id,
        name=name,
        description=description,
        deadline=deadline
    )
    await message.answer(f"Задача '{name}' добавлена!")
    await state.clear()

@dp.message(Command("list"))
async def cmd_list(message: Message):
    tasks = get_user_tasks(user_id=message.from_user.id)
    if not tasks:
        await message.answer("Задачи отсутствуют.")
        return
    msg = "Список задач:\n"
    for task in tasks:
        status = task[3]
        deadline = format_date(task[5]) if task[5] else "—"
        msg += f"• {task[2]} ({task[0]}) [{status}]\n   Дедлайн: {deadline}\n"
    await message.answer(msg)

@dp.message(Command("active"))
async def cmd_active(message: Message):
    tasks = get_user_tasks(user_id=message.from_user.id, status='Не выполнено')
    if not tasks:
        await message.answer("Активных задач нет.")
        return
    msg = "Активные задачи:\n"
    for task in tasks:
        deadline = format_date(task[5]) if task[5] else "—"
        msg += f"• {task[2]} (Дедлайн: {deadline})\n"
    await message.answer(msg)

@dp.message(Command("completed"))
async def cmd_completed(message: Message):
    tasks = get_user_tasks(user_id=message.from_user.id, status='Выполнено')
    if not tasks:
        await message.answer("Завершенных задач нет.")
        return
    msg = "Завершенные задачи:\n"
    for task in tasks:
        msg += f"• {task[2]} (Выполнено: {task[7]})\n"
    await message.answer(msg)

@dp.message(Command("due"))
async def cmd_due(message: Message):
    tasks = get_user_tasks(user_id=message.from_user.id)
    due_tasks = [task for task in tasks if task[5]]
    if not due_tasks:
        await message.answer("Задачи с дедлайном отсутствуют.")
        return
    msg = "Задачи с дедлайном:\n"
    for task in due_tasks:
        deadline = datetime.strptime(task[5], '%Y-%m-%d')
        delta = deadline - datetime.now()
        msg += f"• {task[2]} (Осталось: {delta.days} дней)\n"
    await message.answer(msg)

@dp.message(F.text.startswith("/delete"))
async def cmd_delete(message: Message, state: FSMContext):
    await message.answer("Укажите ID задачи через пробел.")
    await state.set_state(TaskStates.DELETE_TASK)


@dp.message(TaskStates.DELETE_TASK)
async def cmd_add(message: Message, state: FSMContext):
    try:
        task_ids = list(map(int, message.text.split()))
        print(task_ids)
        for task_id in task_ids:
            delete_task(user_id=message.from_user.id, task_id=task_id)
            await message.answer(f"Задача с ID {task_id} удалена.")
            await state.clear()
    except (ValueError, IndexError):
        await message.answer("Укажите ID задачи через пробел или -1 чтобы выйти")
    

    

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM tasks WHERE user_id = ?",
        (message.from_user.id,)
    )
    conn.commit()
    conn.close()
    await message.answer("Все задачи удалены.")

@dp.message(Command("export"))
async def cmd_export(message: Message):
    user_id = message.from_user.id
    tasks = get_user_tasks(user_id=user_id)
    if not tasks:
        await message.answer("Нет задач для экспорта.")
        return

    # Создаем временный файл
    filename = f"{user_id}_tasks.csv"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("ID,Название,Статус,Дедлайн\n")
        for task in tasks:
            f.write(f"{task[0]},{task[2]},{task[3]},{task[5]}\n")

    # Отправляем файл через InputFile с путём
    await message.answer_document(document=FSInputFile(filename))  # [[1]][[6]]
    os.remove(filename)  # Удаляем файл после отправки
    
async def main():
    init_db()
    dp.startup.register(start_scheduler)
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())  # Запуск асинхронной функции [[3]][[4]]