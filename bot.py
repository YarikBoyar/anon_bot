import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
import random

# Настройки
API_TOKEN = 'ВАШ_API_ТОКЕН'

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Клавиатура
builder = ReplyKeyboardBuilder()
builder.add(KeyboardButton(text="🔍 Найти собеседника"))
builder.add(KeyboardButton(text="🛑 Завершить диалог"))
builder.add(KeyboardButton(text="⚠️ Пожаловаться"))
keyboard = builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

# Подключение к БД
async def get_db():
    async with aiosqlite.connect('anon_chat.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                user1_id INTEGER,
                user2_id INTEGER,
                active INTEGER DEFAULT 1
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS queue (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        await db.commit()
        return db

# Обработчик старта
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это анонимный чат.\n"
        "Нажми 'Найти собеседника' для старта.",
        reply_markup=keyboard
    )

# Поиск собеседника
@dp.message(F.text == "🔍 Найти собеседника")
async def find_companion(message: Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect('anon_chat.db') as db:
        # Проверка на активную сессию
        existing = await db.execute_fetchall(
            'SELECT * FROM sessions WHERE user1_id = ? OR user2_id = ? AND active = 1',
            (user_id, user_id)
        )
        if existing:
            return await message.answer("У вас уже есть активный диалог!")
        
        # Проверка очереди
        queue = await db.execute_fetchall('SELECT * FROM queue')
        queue_users = [q[0] for q in queue]
        
        if user_id in queue_users:
            return await message.answer("Вы уже в очереди!")
        
        # Добавление в очередь
        await db.execute('INSERT INTO queue (user_id) VALUES (?)', (user_id,))
        await db.commit()
        
        await message.answer("Добавлены в очередь. Поиск собеседника...")

        # Поиск пары
        if len(queue) >= 2:
            users = queue_users[:2]
            await db.execute('DELETE FROM queue WHERE user_id IN (?, ?)', users)
            await db.execute('INSERT INTO sessions (user1_id, user2_id) VALUES (?, ?)', users)
            await db.commit()
            
            for uid in users:
                await bot.send_message(uid, "✅ Собеседник найден! Пишите")

# Обработка сообщений
@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect('anon_chat.db') as db:
        # Поиск сессии
        session = await db.execute_fetchone(
            'SELECT user1_id, user2_id FROM sessions WHERE (user1_id = ? OR user2_id = ?) AND active = 1',
            (user_id, user_id)
        )
        if not session:
            return
        
        companion_id = session[1] if session[0] == user_id else session[0]
        await message.copy_to(companion_id, caption="Аноним: ")

# Обработка медиа
@dp.message(F.photo | F.video | F.document)
async def handle_media(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect('anon_chat.db') as db:
        session = await db.execute_fetchone(
            'SELECT user1_id, user2_id FROM sessions WHERE (user1_id = ? OR user2_id = ?) AND active = 1',
            (user_id, user_id)
        )
        if not session:
            return
        
        companion_id = session[1] if session[0] == user_id else session[0]
        await message.copy_to(companion_id)

# Завершение диалога
@dp.message(F.text == "🛑 Завершить диалог")
async def stop_dialog(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect('anon_chat.db') as db:
        await db.execute(
            'UPDATE sessions SET active = 0 WHERE user1_id = ? OR user2_id = ?',
            (user_id, user_id)
        )
        await db.commit()
        await message.answer("Диалог завершен. Нажмите 'Найти собеседника' снова", reply_markup=keyboard)

# Пожаловаться
@dp.message(F.text == "⚠️ Пожаловаться")
async def report_user(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect('anon_chat.db') as db:
        session = await db.execute_fetchone(
            'SELECT user1_id, user2_id FROM sessions WHERE (user1_id = ? OR user2_id = ?) AND active = 1',
            (user_id, user_id)
        )
        if not session:
            return await message.answer("Нет активного диалога для жалобы")
        
        companion_id = session[1] if session[0] == user_id else session[0]
        await bot.ban_chat_member(chat_id=companion_id, user_id=companion_id)
        await message.answer("Жалоба отправлена. Пользователь заблокирован")

# Логирование
logging.basicConfig(level=logging.INFO)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())