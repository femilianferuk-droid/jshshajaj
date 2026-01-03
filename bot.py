#!/usr/bin/env python3
"""
Telegram Bot для сбора информации о пользователях и создания зеркал
"""

import os
import sys
import json
import logging
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Проверяем версию Python
if sys.version_info < (3, 7):
    print("Требуется Python 3.7 или выше")
    sys.exit(1)

# Настройка путей
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(DATA_DIR / 'bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ConversationHandler,
        filters,
        ContextTypes
    )
    from telegram.constants import ParseMode
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Установите зависимости: pip install python-telegram-bot")
    sys.exit(1)

# Состояния для диалогов
SEARCH, GET_ID, GET_USERNAME, WAITING_TOKEN = range(4)

class UserInfoBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.users_file = DATA_DIR / "users.json"
        self.cache_file = DATA_DIR / "cache.json"
        self.mirrors_file = DATA_DIR / "mirrors.json"
        self.setup_handlers()
        self.load_data()
        
    def load_data(self):
        """Загрузка данных из файлов"""
        self.users_data = self.load_json(self.users_file)
        self.cache_data = self.load_json(self.cache_file)
        self.mirrors_data = self.load_json(self.mirrors_file)
        
    def load_json(self, filepath: Path) -> dict:
        """Загрузка JSON файла"""
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_json(self, filepath: Path, data: dict):
        """Сохранение в JSON файл"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        
        # ConversationHandler для поиска пользователей
        search_conv = ConversationHandler(
            entry_points=[
                CommandHandler("search", self.start_search_command),
                CallbackQueryHandler(self.start_search_callback, pattern="^search_user$")
            ],
            states={
                SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_search_choice)
                ],
                GET_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_by_id_input)
                ],
                GET_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_by_username_input)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True
        )
        
        # ConversationHandler для создания зеркала
        mirror_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.create_mirror, pattern="^create_mirror$"),
                CommandHandler("mirror", self.create_mirror_command)
            ],
            states={
                WAITING_TOKEN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_token)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        # Регистрация всех обработчиков
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("info", self.get_user_info))
        self.application.add_handler(CommandHandler("id", self.get_my_id))
        self.application.add_handler(CommandHandler("get", self.get_user))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("help", self.show_help))
        self.application.add_handler(search_conv)
        self.application.add_handler(mirror_conv)
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик пересланных сообщений для получения ID
        self.application.add_handler(MessageHandler(filters.FORWARDED, self.handle_forwarded))
        
        # Обработчик остальных сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Сохраняем информацию о пользователе
        user_data = self.collect_user_info(user, chat)
        self.save_user_info(user_data)
        
        # Создаем клавиатуру
        keyboard = [
            [
                InlineKeyboardButton("👤 Моя информация", callback_data="get_info"),
                InlineKeyboardButton("🔍 Найти пользователя", callback_data="search_user")
            ],
            [
                InlineKeyboardButton("🪞 Создать зеркало", callback_data="create_mirror"),
                InlineKeyboardButton("🆔 Мой ID", callback_data="my_id")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                InlineKeyboardButton("🆘 Помощь", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
👋 Привет, {user.mention_html()}!

🤖 <b>Я - бот для сбора информации и создания зеркал</b>

📋 <b>Доступные функции:</b>
• 👤 Получить вашу информацию
• 🔍 Найти другого пользователя
• 🪞 Создать зеркало-бот
• 🆔 Получить ID пользователя
• 📊 Статистика использования

<b>Основные команды:</b>
/start - Запустить бота
/info - Ваша информация
/search - Найти пользователя
/id - Ваш ID
/get - Найти по ID или username
/mirror - Создать зеркало
/stats - Статистика
/help - Помощь

📌 <i>Для получения ID пользователя - перешлите мне его сообщение</i>
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def get_my_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать ID пользователя"""
        user = update.effective_user
        
        text = f"""
<b>👤 Ваша информация:</b>

🆔 <b>ID:</b> <code>{user.id}</code>
📌 <b>Username:</b> @{user.username or 'не указан'}
👤 <b>Имя:</b> {user.first_name}
📛 <b>Фамилия:</b> {user.last_name or 'не указана'}
⭐ <b>Premium:</b> {'Да' if getattr(user, 'is_premium', False) else 'Нет'}

<b>Как найти другого пользователя:</b>
1. Перешлите мне его сообщение
2. Используйте /search
3. Используйте /get @username
4. Используйте /get 123456789
        """
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    async def get_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получить информацию о пользователе"""
        if not context.args:
            await update.message.reply_text(
                "<b>Использование команды /get:</b>\n\n"
                "/get @username - найти по username\n"
                "/get 123456789 - найти по ID\n"
                "/get me - информация о себе\n\n"
                "<i>Примеры:</i>\n"
                "/get @username\n"
                "/get 123456789\n"
                "/get me",
                parse_mode=ParseMode.HTML
            )
            return
        
        identifier = context.args[0]
        
        if identifier.lower() == 'me':
            await self.show_user_info(update, update.effective_user)
            return
        
        try:
            # Пробуем как ID
            user_id = int(identifier)
            await self.search_by_id(update, context, user_id)
        except ValueError:
            # Пробуем как username
            if identifier.startswith('@'):
                identifier = identifier[1:]
            await self.search_by_username(update, context, identifier)
    
    async def start_search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать поиск из команды"""
        keyboard = [
            ["🔍 Поиск по ID", "🔍 Поиск по username"],
            ["❌ Отмена"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "Выберите тип поиска:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return SEARCH
    
    async def start_search_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать поиск из callback"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            ["🔍 Поиск по ID", "🔍 Поиск по username"],
            ["❌ Отмена"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await query.message.reply_text(
            "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "Выберите тип поиска:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return SEARCH
    
    async def handle_search_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа поиска"""
        choice = update.message.text
        
        if choice == "❌ Отмена":
            await update.message.reply_text("Поиск отменен.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
        elif choice == "🔍 Поиск по ID":
            await update.message.reply_text(
                "Введите ID пользователя (только цифры):\n\n"
                "<i>Пример: 123456789</i>",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.HTML
            )
            return GET_ID
        
        elif choice == "🔍 Поиск по username":
            await update.message.reply_text(
                "Введите username пользователя (без @):\n\n"
                "<i>Пример: username</i>",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.HTML
            )
            return GET_USERNAME
        
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите один из вариантов.",
                reply_markup=ReplyKeyboardRemove()
            )
            return SEARCH
    
    async def search_by_id_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск по ID (ввод)"""
        try:
            user_id = int(update.message.text.strip())
            await self.search_by_id(update, context, user_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Неверный формат ID</b>\n\n"
                "ID должен содержать только цифры.\n"
                "<i>Пример: 123456789</i>",
                parse_mode=ParseMode.HTML
            )
            return GET_ID
        
        return ConversationHandler.END
    
    async def search_by_username_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск по username (ввод)"""
        username = update.message.text.strip()
        
        if username.startswith('@'):
            username = username[1:]
        
        if not username:
            await update.message.reply_text(
                "❌ <b>Username не может быть пустым</b>",
                parse_mode=ParseMode.HTML
            )
            return GET_USERNAME
        
        await self.search_by_username(update, context, username)
        return ConversationHandler.END
    
    async def search_by_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Поиск пользователя по ID"""
        try:
            # Пытаемся получить информацию о пользователе
            user = await context.bot.get_chat(user_id)
            await self.show_user_info(update, user)
            
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            
            # Проверяем кэш
            cached_info = self.cache_data.get(str(user_id))
            if cached_info:
                await self.show_cached_info(update, cached_info)
            else:
                error_text = f"""
❌ <b>Не удалось найти пользователя с ID:</b> <code>{user_id}</code>

<b>Возможные причины:</b>
• Пользователь не существует
• Пользователь заблокировал бота
• ID указан неверно
• Пользователь является приватным

<b>Попробуйте:</b>
• Поиск по username
• Переслать сообщение пользователя
• Убедиться в правильности ID
                """
                
                keyboard = [[InlineKeyboardButton("🔄 Попробовать снова", callback_data="search_user")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    error_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
    
    async def search_by_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
        """Поиск пользователя по username"""
        try:
            # Пытаемся получить информацию о пользователе
            user = await context.bot.get_chat(f"@{username}")
            await self.show_user_info(update, user)
            
        except Exception as e:
            logger.error(f"Error getting user by username @{username}: {e}")
            
            # Проверяем кэш по username
            cached_info = None
            for user_id, info in self.cache_data.items():
                if info.get('username') == username:
                    cached_info = info
                    break
            
            if cached_info:
                await self.show_cached_info(update, cached_info)
            else:
                error_text = f"""
❌ <b>Не удалось найти пользователя @{username}</b>

<b>Возможные причины:</b>
• Пользователь не существует
• Username указан неверно
• Пользователь изменил username
• Username является приватным

<b>Попробуйте:</b>
• Поиск по ID
• Переслать сообщение пользователя
• Убедиться в правильности username
                """
                
                keyboard = [[InlineKeyboardButton("🔄 Попробовать снова", callback_data="search_user")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    error_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
    
    async def handle_forwarded(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка пересланных сообщений"""
        if not update.message.forward_from:
            await update.message.reply_text(
                "❌ <b>Не удалось получить информацию о пользователе</b>\n\n"
                "Пользователь скрыл информацию в настройках приватности.",
                parse_mode=ParseMode.HTML
            )
            return
        
        user = update.message.forward_from
        await self.show_user_info(update, user)
    
    async def show_user_info(self, update: Update, user):
        """Показать информацию о пользователе"""
        user_data = self.collect_user_info(user, None)
        
        # Сохраняем в основную базу и кэш
        self.save_user_info(user_data)
        
        # Обновляем кэш
        self.cache_data[str(user.id)] = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'last_seen': datetime.now().isoformat()
        }
        self.save_json(self.cache_file, self.cache_data)
        
        # Формируем информацию
        info_text = self.format_user_info(user_data)
        
        # Создаем клавиатуру
        keyboard = []
        
        # Кнопка для написания сообщения (если есть username)
        if user.username:
            keyboard.append([
                InlineKeyboardButton("📨 Написать сообщение", url=f"https://t.me/{user.username}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔍 Поиск другого", callback_data="search_user"),
            InlineKeyboardButton("👤 Моя информация", callback_data="get_info")
        ])
        
        keyboard.append([
            InlineKeyboardButton("📋 JSON формат", callback_data=f"json_{user.id}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'message'):
            await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await update.reply_text(info_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    async def show_cached_info(self, update: Update, cached_info: dict):
        """Показать кэшированную информацию"""
        info_text = f"""
📄 <b>ИНФОРМАЦИЯ ИЗ КЭША</b>

👤 <b>Имя:</b> {cached_info.get('first_name', 'Неизвестно')}
📛 <b>Фамилия:</b> {cached_info.get('last_name', 'Не указана')}
📌 <b>Username:</b> @{cached_info.get('username', 'не указан')}
🆔 <b>ID:</b> <code>{cached_info.get('user_id', 'Неизвестно')}</code>
📅 <b>Последнее обновление:</b> {datetime.fromisoformat(cached_info.get('last_seen', datetime.now().isoformat())).strftime('%Y-%m-%d %H:%M')}

⚠️ <i>Информация может быть устаревшей</i>
        """
        
        await update.reply_text(info_text, parse_mode=ParseMode.HTML)
    
    def collect_user_info(self, user, chat) -> dict:
        """Сбор информации о пользователе"""
        user_data = {
            'user_id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'language_code': user.language_code,
            'is_premium': user.is_premium if hasattr(user, 'is_premium') else False,
            'is_bot': user.is_bot,
            'chat_id': chat.id if chat else None,
            'chat_type': chat.type if chat else None,
            'timestamp': datetime.now().isoformat(),
            'has_phone_number': False,
            'phone_number': None
        }
        
        # Пытаемся получить номер телефона
        if hasattr(user, 'phone_number') and user.phone_number:
            user_data['phone_number'] = user.phone_number
            user_data['has_phone_number'] = True
        
        return user_data
    
    def format_user_info(self, user_data: dict) -> str:
        """Форматирование информации о пользователе"""
        phone_text = f"📱 <b>Телефон:</b> {user_data['phone_number']}\n" if user_data['phone_number'] else "📱 <b>Телефон:</b> Не указан\n"
        premium_text = "⭐ <b>Premium:</b> Да\n" if user_data['is_premium'] else "⭐ <b>Premium:</b> Нет\n"
        bot_text = "🤖 <b>Бот:</b> Да\n" if user_data['is_bot'] else "🤖 <b>Бот:</b> Нет\n"
        
        info_text = f"""
📊 <b>ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ</b>

👤 <b>Основная информация:</b>
🆔 <b>ID:</b> <code>{user_data['user_id']}</code>
👤 <b>Имя:</b> {user_data['first_name']}
📛 <b>Фамилия:</b> {user_data['last_name'] or 'Не указана'}
📌 <b>Username:</b> @{user_data['username'] or 'не указан'}
🌐 <b>Язык:</b> {user_data['language_code']}
{premium_text}{bot_text}{phone_text}
📅 <b>Дата запроса:</b> {datetime.fromisoformat(user_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        if user_data.get('chat_id'):
            info_text += f"💬 <b>ID чата:</b> <code>{user_data['chat_id']}</code>\n"
            info_text += f"📋 <b>Тип чата:</b> {user_data['chat_type']}\n"
        
        return info_text
    
    def save_user_info(self, user_data: dict):
        """Сохранение информации о пользователе"""
        user_id = str(user_data['user_id'])
        
        # Загружаем существующие данные
        if not self.users_data:
            self.users_data = {}
        
        # Обновляем данные
        if user_id not in self.users_data:
            self.users_data[user_id] = []
        
        self.users_data[user_id].append(user_data)
        
        # Сохраняем
        self.save_json(self.users_file, self.users_data)
    
    async def get_user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о текущем пользователе"""
        user = update.effective_user
        chat = update.effective_chat
        
        user_data = self.collect_user_info(user, chat)
        self.save_user_info(user_data)
        
        info_text = self.format_user_info(user_data)
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Найти другого", callback_data="search_user"),
                InlineKeyboardButton("🪞 Создать зеркало", callback_data="create_mirror")
            ],
            [
                InlineKeyboardButton("📋 JSON формат", callback_data=f"json_{user.id}"),
                InlineKeyboardButton("📊 Статистика", callback_data="stats")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    async def create_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда создания зеркала"""
        await self.create_mirror(update, context)
    
    async def create_mirror(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать процесс создания зеркала"""
        instruction_text = """
🪞 <b>СОЗДАНИЕ ЗЕРКАЛА БОТА</b>

<b>Инструкция:</b>
1. Создайте нового бота через <a href="https://t.me/BotFather">@BotFather</a>
2. Отправьте команду /newbot
3. Выберите имя бота
4. Выберите username бота (должен заканчиваться на 'bot')
5. Получите токен бота
6. Отправьте токен мне

<b>Формат токена:</b>
<code>1234567890:ABCdefGHIjklMNoPQRsTUVwxyZ</code>

⚠️ <b>Внимание:</b>
• Никому не передавайте свой токен!
• Это создаст полную копию этого бота
• Копия будет работать на вашем токене

<b>Отправьте токен бота:</b>
        """
        
        if hasattr(update, 'callback_query'):
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(instruction_text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(instruction_text, parse_mode=ParseMode.HTML)
        
        return WAITING_TOKEN
    
    async def process_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка полученного токена"""
        token = update.message.text.strip()
        
        # Проверка формата токена
        if not self.is_valid_token(token):
            await update.message.reply_text(
                "❌ <b>Неверный формат токена!</b>\n\n"
                "Токен должен быть в формате:\n"
                "<code>1234567890:ABCdefGHIjklMNoPQRsTUVwxyZ</code>\n\n"
                "Пожалуйста, отправьте действительный токен:",
                parse_mode=ParseMode.HTML
            )
            return WAITING_TOKEN
        
        # Пробуем создать зеркало
        await update.message.reply_text("🔄 <b>Создаю зеркало...</b>", parse_mode=ParseMode.HTML)
        
        try:
            mirror_dir = await self.create_mirror_bot(token, update.effective_user.id)
            
            success_text = f"""
✅ <b>Зеркало успешно создано!</b>

<b>Информация:</b>
📁 Папка: <code>{mirror_dir}</code>
👤 Создатель: {update.effective_user.mention_html()}
📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>Для запуска:</b>
1. Перейдите в папку <code>{mirror_dir}</code>
2. Установите зависимости: <code>pip install python-telegram-bot</code>
3. Запустите бота: <code>python bot.py</code>

⚠️ <b>Внимание:</b>
• Никому не передавайте папку с зеркалом
• В ней содержится ваш токен
• Запускайте только на доверенных устройствах
            """
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"Error creating mirror: {e}")
            await update.message.reply_text(
                f"❌ <b>Ошибка при создании зеркала:</b>\n\n<code>{str(e)}</code>",
                parse_mode=ParseMode.HTML
            )
        
        return ConversationHandler.END
    
    async def create_mirror_bot(self, token: str, creator_id: int) -> str:
        """Создание зеркала бота"""
        # Создаем имя для папки
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mirror_dir = BASE_DIR / f"mirror_{timestamp}"
        mirror_dir.mkdir(exist_ok=True)
        
        # Копируем текущий файл бота
        current_file = Path(__file__)
        shutil.copy(current_file, mirror_dir / "bot.py")
        
        # Создаем конфигурационный файл
        config_content = f'''#!/usr/bin/env python3
"""
Зеркало Telegram бота
Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Создатель: {creator_id}
"""

import os
import sys

# Токен бота
TOKEN = "{token}"

# ID администраторов (добавьте свои)
ADMIN_IDS = [{creator_id}]

# Запуск бота
if __name__ == "__main__":
    # Добавляем токен в аргументы
    sys.argv.append(TOKEN)
    
    # Импортируем и запускаем бота
    from bot import UserInfoBot
    
    print(f"🚀 Запуск зеркала-бота...")
    print(f"👤 Создатель: {creator_id}")
    print(f"📅 Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    bot = UserInfoBot(TOKEN)
    bot.run()
'''
        
        with open(mirror_dir / "config.py", "w", encoding="utf-8") as f:
            f.write(config_content)
        
        # Создаем файл запуска
        launcher_content = f'''#!/usr/bin/env python3
"""
Запуск зеркала-бота
"""
import subprocess
import sys
import os

print("🚀 Запуск зеркала-бота...")

# Запускаем бота
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "bot.py"])
'''
        
        with open(mirror_dir / "launch.py", "w", encoding="utf-8") as f:
            f.write(launcher_content)
        
        # Создаем README
        readme_content = f"""# Зеркало Telegram бота

## Информация
- Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Создатель: {creator_id}
- Токен: {token[:10]}...{token[-10:]}

## Установка и запуск

### 1. Установите зависимости:
```bash
pip install python-telegram-bot
