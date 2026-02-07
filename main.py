import asyncio
import logging
import json
import sqlite3
from datetime import datetime
from typing import Dict, List

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, WebAppInfo, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8275977683:AAHMfOEC5Plw_tlSJsExMchzKXteyR9Qcc4"  # Получите у @BotFather
# Для локального тестирования
WEBAPP_URL = "http://localhost:8000/webapp.html"
# Для публикации: https://ваш-сайт.com/webapp.html

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Класс для работы с базой данных
class TapDatabase:
    def __init__(self, db_path="tap_game.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                coins INTEGER DEFAULT 0,
                total_taps INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    def get_player(self, user_id: int) -> Dict:
        """Получить данные игрока"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return {}
    
    def create_player(self, user_id: int, username: str = "") -> Dict:
        """Создать нового игрока"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO players (user_id, username, coins, total_taps, created_at, last_active)
            VALUES (?, ?, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (user_id, username))
        
        conn.commit()
        conn.close()
        
        return {
            'user_id': user_id,
            'username': username,
            'display_name': '',
            'coins': 0,
            'total_taps': 0
        }
    
    def save_player(self, player_data: Dict) -> bool:
        """Сохранить данные игрока"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO players 
                (user_id, username, display_name, coins, total_taps, last_active)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                player_data['user_id'],
                player_data.get('username', ''),
                player_data.get('display_name', ''),
                player_data.get('coins', 0),
                player_data.get('total_taps', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            return False
    
    def add_tap(self, user_id: int) -> Dict:
        """Добавить тап игроку"""
        player = self.get_player(user_id)
        if not player:
            player = self.create_player(user_id)
        
        player['coins'] = player.get('coins', 0) + 1
        player['total_taps'] = player.get('total_taps', 0) + 1
        
        self.save_player(player)
        return player
    
    def set_display_name(self, user_id: int, display_name: str) -> bool:
        """Установить отображаемое имя"""
        try:
            # Проверяем уникальность имени
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id FROM players WHERE display_name = ? AND user_id != ?', 
                         (display_name, user_id))
            if cursor.fetchone():
                conn.close()
                return False
            
            cursor.execute('''
                UPDATE players 
                SET display_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (display_name, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка установки имени: {e}")
            return False
    
    def get_top_players(self, limit: int = 10) -> List[Dict]:
        """Получить топ игроков"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, display_name, coins, total_taps 
            FROM players 
            WHERE display_name IS NOT NULL AND display_name != ''
            ORDER BY coins DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for idx, row in enumerate(rows, 1):
            data = dict(row)
            # Используем display_name если есть, иначе username
            name = data.get('display_name') or data.get('username') or f"Игрок_{data['user_id']}"
            result.append({
                'user_id': data['user_id'],
                'name': name,
                'coins': data['coins'],
                'total_taps': data['total_taps'],
                'rank': idx
            })
        
        return result
    
    def get_player_rank(self, user_id: int) -> int:
        """Получить ранг игрока"""
        player = self.get_player(user_id)
        if not player or player.get('coins', 0) == 0:
            return 999
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) + 1 FROM players 
            WHERE coins > ?
        ''', (player.get('coins', 0),))
        
        rank = cursor.fetchone()[0]
        conn.close()
        return rank

# Инициализация базы данных
db = TapDatabase()

def format_number(num: int) -> str:
    """Форматировать число"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or ""
    
    logger.info(f"Пользователь {user_id} начал игру")
    
    # Получаем или создаем игрока
    player = db.get_player(user_id)
    if not player:
        player = db.create_player(user_id, username)
    else:
        # Обновляем username если изменился
        if username and player.get('username') != username:
            player['username'] = username
            db.save_player(player)
    
    # Проверяем, есть ли у игрока имя
    has_name = bool(player.get('display_name'))
    
    if not has_name:
        # Предлагаем установить имя
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎮 Играть без имени",
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✏️ Установить имя",
                        callback_data="set_name"
                    )
                ]
            ]
        )
        
        await message.answer(
            "👋 <b>Добро пожаловать в TapCoin!</b>\n\n"
            "<i>Простой кликер в стиле Notcoin</i>\n\n"
            "Чтобы играть с именем, нажми 'Установить имя'.\n"
            "Или начни играть сразу:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        # Имя уже есть, показываем меню
        display_name = player.get('display_name', f"Игрок_{user_id}")
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 ТАПАТЬ!",
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
                    )
                ],
                [
                    InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top"),
                    InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
                ],
                [
                    InlineKeyboardButton(text="✏️ Сменить имя", callback_data="change_name")
                ]
            ]
        )
        
        await message.answer(
            f"👋 <b>С возвращением, {display_name}!</b>\n\n"
            f"💰 <b>Баланс:</b> {format_number(player.get('coins', 0))} монет\n"
            f"👆 <b>Тапов:</b> {format_number(player.get('total_taps', 0))}\n\n"
            "Нажми кнопку ниже, чтобы продолжить играть!",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

@router.callback_query(F.data == "set_name")
async def set_name_handler(callback_query: CallbackQuery):
    """Установить имя"""
    await callback_query.answer()
    
    await callback_query.message.edit_text(
        "✏️ <b>Установите имя</b>\n\n"
        "Как вас будут видеть другие игроки?\n\n"
        "<i>Отправьте мне сообщение с вашим именем (2-20 символов)</i>",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "change_name")
async def change_name_handler(callback_query: CallbackQuery):
    """Сменить имя"""
    await callback_query.answer()
    
    await callback_query.message.edit_text(
        "✏️ <b>Смена имени</b>\n\n"
        "Введите новое имя (2-20 символов):",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text)
async def handle_name_input(message: Message):
    """Обработка ввода имени"""
    user_id = message.from_user.id
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 20:
        await message.answer(
            "⚠️ <b>Неверная длина имени!</b>\n\n"
            "Имя должно быть от 2 до 20 символов.\n"
            "Попробуйте еще раз:",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Проверяем, можно ли установить имя
    success = db.set_display_name(user_id, name)
    
    if success:
        player = db.get_player(user_id)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎮 Начать играть!",
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
                    )
                ]
            ]
        )
        
        await message.answer(
            f"✅ <b>Отлично, {name}!</b>\n\n"
            "Теперь ваше имя будет отображаться в таблице лидеров.\n\n"
            "Нажмите кнопку ниже, чтобы начать играть:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            "❌ <b>Имя уже занято!</b>\n\n"
            "Это имя уже использует другой игрок.\n"
            "Пожалуйста, выберите другое имя:",
            parse_mode=ParseMode.HTML
        )

@router.callback_query(F.data == "stats")
async def stats_handler(callback_query: CallbackQuery):
    """Показать статистику"""
    user_id = callback_query.from_user.id
    player = db.get_player(user_id)
    rank = db.get_player_rank(user_id)
    
    display_name = player.get('display_name') or player.get('username') or f"Игрок_{user_id}"
    
    stats_text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 <b>Имя:</b> {display_name}\n"
        f"💰 <b>Монеты:</b> {format_number(player.get('coins', 0))}\n"
        f"👆 <b>Всего тапов:</b> {format_number(player.get('total_taps', 0))}\n"
        f"🏆 <b>Ранг:</b> #{rank}\n\n"
        f"🕐 <b>В игре с:</b> {player.get('created_at', '')[:10]}"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 Продолжить игру", callback_data="play"),
                InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top")
            ]
        ]
    )
    
    await callback_query.message.edit_text(stats_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback_query.answer()

@router.callback_query(F.data == "top")
async def top_handler(callback_query: CallbackQuery):
    """Показать топ игроков"""
    top_players = db.get_top_players(10)
    user_id = callback_query.from_user.id
    player = db.get_player(user_id)
    user_rank = db.get_player_rank(user_id)
    
    top_text = "🏆 <b>Топ 10 игроков</b>\n\n"
    
    for i, p in enumerate(top_players, 1):
        medal = ""
        if i == 1: medal = "🥇"
        elif i == 2: medal = "🥈"
        elif i == 3: medal = "🥉"
        else: medal = f"{i}."
        
        name = p['name'][:15]
        if len(p['name']) > 15:
            name = p['name'][:12] + "..."
        
        coins = format_number(p['coins'])
        
        # Выделяем текущего пользователя
        if p['user_id'] == user_id:
            top_text += f"<b>{medal} {name}: {coins} монет ⭐</b>\n"
        else:
            top_text += f"{medal} {name}: {coins} монет\n"
    
    top_text += f"\n<b>Ваш ранг:</b> #{user_rank}\n"
    top_text += f"<b>Ваши монеты:</b> {format_number(player.get('coins', 0))}\n\n"
    
    # Общая статистика
    conn = sqlite3.connect("tap_game.db")
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(coins) FROM players')
    total_coins = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(total_taps) FROM players')
    total_taps = cursor.fetchone()[0] or 0
    
    conn.close()
    
    top_text += f"📈 <b>Общая статистика</b>\n"
    top_text += f"👥 Игроков: {total_players}\n"
    top_text += f"💰 Всего монет: {format_number(total_coins)}\n"
    top_text += f"👆 Всего тапов: {format_number(total_taps)}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="top")],
            [
                InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats"),
                InlineKeyboardButton(text="🎮 Играть", callback_data="play")
            ]
        ]
    )
    
    await callback_query.message.edit_text(top_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback_query.answer()

@router.callback_query(F.data == "play")
async def play_handler(callback_query: CallbackQuery):
    """Вернуться к игре"""
    user_id = callback_query.from_user.id
    player = db.get_player(user_id)
    
    has_name = bool(player.get('display_name'))
    
    if has_name:
        display_name = player.get('display_name')
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 ПРОДОЛЖИТЬ ТАПАТЬ",
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
                    )
                ]
            ]
        )
        
        await callback_query.message.edit_text(
            f"Нажми кнопку ниже, чтобы продолжить игру, {display_name}!",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎮 Играть без имени",
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
                    )
                ],
                [
                    InlineKeyboardButton(text="✏️ Установить имя", callback_data="set_name")
                ]
            ]
        )
        
        await callback_query.message.edit_text(
            "Вы можете играть без имени или установить его:",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    await callback_query.answer()

@router.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    """Обработка данных из WebApp"""
    try:
        data = json.loads(message.web_app_data.data)
        user_id = data.get("user_id")
        action = data.get("action")
        
        logger.info(f"WebApp запрос от {user_id}: {action}")
        
        response = {}
        
        if action == "tap":
            # Обработка тапа
            player = db.add_tap(user_id)
            response = {
                "success": True,
                "coins": player['coins'],
                "total_taps": player['total_taps'],
                "coins_added": 1
            }
            
        elif action == "get_state":
            # Получить состояние игрока
            player = db.get_player(user_id)
            if not player:
                player = db.create_player(user_id)
            
            response = {
                "success": True,
                "coins": player.get('coins', 0),
                "total_taps": player.get('total_taps', 0),
                "display_name": player.get('display_name', ''),
                "has_name": bool(player.get('display_name'))
            }
            
        elif action == "get_top":
            # Получить топ игроков
            top_players = db.get_top_players(10)
            response = {
                "success": True,
                "top_players": top_players
            }
            
        elif action == "set_name_from_app":
            # Установить имя из WebApp
            name = data.get("name", "").strip()
            if 2 <= len(name) <= 20:
                success = db.set_display_name(user_id, name)
                response = {
                    "success": success,
                    "message": "Имя установлено" if success else "Имя занято"
                }
            else:
                response = {
                    "success": False,
                    "message": "Имя должно быть 2-20 символов"
                }
        
        # Отправляем ответ обратно в WebApp
        await message.answer(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Ошибка обработки WebApp: {e}")
        await message.answer(json.dumps({"success": False, "error": str(e)}))

@router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help"""
    help_text = (
        "ℹ️ <b>Помощь по игре</b>\n\n"
        "🎮 <b>Как играть:</b>\n"
        "1. Установите имя (опционально)\n"
        "2. Нажмите кнопку 'ТАПАТЬ!'\n"
        "3. Тапайте по экрану в WebApp\n"
        "4. Зарабатывайте монеты\n\n"
        
        "📱 <b>WebApp работает прямо в Telegram</b>\n"
        "• Не нужно ничего скачивать\n"
        "• Сохраняется автоматически\n"
        "• Работает на всех устройствах\n\n"
        
        "🏆 <b>Таблица лидеров</b>\n"
        "• Соревнуйтесь с другими игроками\n"
        "• Поднимайтесь в рейтинге\n"
        "• Показывает топ-10 игроков\n\n"
        
        "💾 <b>Сохранение прогресса</b>\n"
        "• Все данные сохраняются на компьютере\n"
        "• Имя нужно установить один раз\n"
        "• Прогресс не теряется\n\n"
        
        "🔄 <b>Команды бота:</b>\n"
        "/start - Начать игру\n"
        "/stats - Ваша статистика\n"
        "/help - Эта справка"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 НАЧАТЬ ИГРАТЬ", callback_data="play")]
        ]
    )
    
    await message.answer(help_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def main():
    """Запуск бота"""
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())