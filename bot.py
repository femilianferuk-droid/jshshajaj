import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler
import json
import os
import asyncio
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SEARCH, GET_ID, GET_USERNAME = range(3)

class UserInfoBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.users_cache = {}  # Кэш для хранения информации о пользователях
        
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # ConversationHandler для поиска пользователей
        search_conv = ConversationHandler(
            entry_points=[
                CommandHandler("search", self.search_user),
                CallbackQueryHandler(self.start_search, pattern="^search_user$")
            ],
            states={
                SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_search_choice)
                ],
                GET_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_by_id)
                ],
                GET_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_by_username)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_search)],
            allow_reentry=True
        )
        
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("info", self.get_user_info))
        self.application.add_handler(CommandHandler("id", self.get_my_id))
        self.application.add_handler(CommandHandler("get", self.get_user))
        self.application.add_handler(search_conv)
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
    async def start(self, update: Update, context: CallbackContext):
        """Обработчик команды /start"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Сохраняем информацию о пользователе
        user_data = self.collect_user_info(user, chat)
        self.save_user_info(user_data)
        
        # Создаем клавиатуру с кнопками
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
👋 Привет, {user.first_name}!

🤖 Я - бот для сбора информации и создания зеркал.

📋 Доступные функции:
• 👤 Получить вашу информацию
• 🔍 Найти другого пользователя
• 🪞 Создать зеркало-бот
• 🆔 Получить свой/чужой ID
• 📊 Статистика
• 🆘 Помощь

Используйте кнопки ниже или команды:
/info - Ваша информация
/search - Найти пользователя
/id - Ваш ID
/get - Информация о пользователе
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def get_my_id(self, update: Update, context: CallbackContext):
        """Показать ID пользователя"""
        user = update.effective_user
        await update.message.reply_text(
            f"🆔 Ваш ID: <code>{user.id}</code>\n"
            f"👤 Ваш username: @{user.username or 'не указан'}\n\n"
            f"Чтобы узнать ID другого пользователя:\n"
            f"• Перешлите мне его сообщение\n"
            f"• Используйте /search\n"
            f"• Или используйте /get @username",
            parse_mode='HTML'
        )
    
    async def get_user(self, update: Update, context: CallbackContext):
        """Получить информацию о пользователе по команде /get"""
        if not context.args:
            await update.message.reply_text(
                "Использование:\n"
                "/get @username - найти по username\n"
                "/get 123456789 - найти по ID\n"
                "/get me - информация о себе"
            )
            return
        
        identifier = context.args[0]
        
        if identifier.lower() == 'me':
            await self.get_user_info(update, context)
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
    
    async def search_user(self, update: Update, context: CallbackContext):
        """Начать поиск пользователя"""
        keyboard = [
            ["🔍 Поиск по ID", "🔍 Поиск по username"],
            ["❌ Отмена"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "Выберите тип поиска:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return SEARCH
    
    async def start_search(self, update: Update, context: CallbackContext):
        """Начать поиск из callback"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            ["🔍 Поиск по ID", "🔍 Поиск по username"],
            ["❌ Отмена"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await query.edit_message_text(
            "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "Выберите тип поиска:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return SEARCH
    
    async def handle_search_choice(self, update: Update, context: CallbackContext):
        """Обработка выбора типа поиска"""
        choice = update.message.text
        
        if choice == "❌ Отмена":
            await update.message.reply_text("Поиск отменен.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
        elif choice == "🔍 Поиск по ID":
            await update.message.reply_text(
                "Введите ID пользователя (только цифры):",
                reply_markup=ReplyKeyboardRemove()
            )
            return GET_ID
        
        elif choice == "🔍 Поиск по username":
            await update.message.reply_text(
                "Введите username пользователя (без @):",
                reply_markup=ReplyKeyboardRemove()
            )
            return GET_USERNAME
        
        else:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов.")
            return SEARCH
    
    async def search_by_id(self, update: Update, context: CallbackContext, user_id=None):
        """Поиск пользователя по ID"""
        if user_id is None:
            try:
                user_id = int(update.message.text.strip())
            except ValueError:
                await update.message.reply_text("❌ Неверный формат ID. Введите только цифры.")
                return GET_ID
        
        try:
            # Пытаемся получить информацию о пользователе
            user = await context.bot.get_chat(user_id)
            await self.send_user_info(update, context, user)
            
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            
            # Проверяем кэш
            cached_info = self.get_cached_user_info(user_id)
            if cached_info:
                await self.send_cached_info(update, cached_info)
            else:
                error_msg = f"❌ Не удалось найти пользователя с ID: {user_id}\n\n"
                error_msg += "Возможные причины:\n"
                error_msg += "• Пользователь не существует\n"
                error_msg += "• Пользователь заблокировал бота\n"
                error_msg += "• ID указан неверно\n\n"
                error_msg += "Попробуйте поиск по username или перешлите сообщение пользователя."
                
                await update.message.reply_text(error_msg)
        
        return ConversationHandler.END
    
    async def search_by_username(self, update: Update, context: CallbackContext, username=None):
        """Поиск пользователя по username"""
        if username is None:
            username = update.message.text.strip()
            if username.startswith('@'):
                username = username[1:]
        
        if not username:
            await update.message.reply_text("❌ Username не может быть пустым.")
            return GET_USERNAME
        
        try:
            # Пытаемся получить информацию о пользователе
            user = await context.bot.get_chat(f"@{username}")
            await self.send_user_info(update, context, user)
            
        except Exception as e:
            logger.error(f"Error getting user by username @{username}: {e}")
            
            # Проверяем кэш по username
            cached_info = self.get_cached_user_info_by_username(username)
            if cached_info:
                await self.send_cached_info(update, cached_info)
            else:
                error_msg = f"❌ Не удалось найти пользователя @{username}\n\n"
                error_msg += "Возможные причины:\n"
                error_msg += "• Пользователь не существует\n"
                error_msg += "• Username указан неверно\n"
                error_msg += "• Пользователь изменил username\n\n"
                error_msg += "Попробуйте поиск по ID или перешлите сообщение пользователя."
                
                await update.message.reply_text(error_msg)
        
        return ConversationHandler.END
    
    async def send_user_info(self, update: Update, context: CallbackContext, user):
        """Отправка информации о найденном пользователе"""
        user_data = self.collect_user_info(user, None)
        self.save_user_info(user_data)
        self.cache_user_info(user_data)
        
        info_text = self.format_user_info(user_data)
        
        # Добавляем кнопки для взаимодействия
        keyboard = []
        
        # Кнопка для добавления в контакты (если есть username)
        if user_data.get('username'):
            keyboard.append([InlineKeyboardButton("📨 Написать", url=f"https://t.me/{user_data['username']}")])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Поиск еще", callback_data="search_user"),
            InlineKeyboardButton("👤 Моя информация", callback_data="get_info")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.reply_text(info_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def send_cached_info(self, update, cached_info):
        """Отправка кэшированной информации"""
        info_text = "📄 <b>ИНФОРМАЦИЯ ИЗ КЭША</b>\n\n"
        info_text += f"👤 <b>Имя:</b> {cached_info.get('first_name', 'Неизвестно')}\n"
        info_text += f"📛 <b>Фамилия:</b> {cached_info.get('last_name', 'Не указана')}\n"
        info_text += f"📌 <b>Username:</b> @{cached_info.get('username', 'не указан')}\n"
        info_text += f"🆔 <b>ID:</b> <code>{cached_info.get('user_id')}</code>\n"
        info_text += f"📅 <b>Последний раз в сети:</b> {cached_info.get('last_seen', 'неизвестно')}\n\n"
        info_text += "⚠️ <i>Информация может быть устаревшей</i>"
        
        await update.reply_text(info_text, parse_mode='HTML')
    
    def get_cached_user_info(self, user_id):
        """Получение информации из кэша по ID"""
        cache_file = "users_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    return cache.get(str(user_id))
            except:
                return None
        return None
    
    def get_cached_user_info_by_username(self, username):
        """Получение информации из кэша по username"""
        cache_file = "users_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    for user_id, info in cache.items():
                        if info.get('username') == username:
                            return info
            except:
                return None
        return None
    
    def cache_user_info(self, user_data):
        """Сохранение информации в кэш"""
        cache_file = "users_cache.json"
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                try:
                    cache = json.load(f)
                except:
                    cache = {}
        else:
            cache = {}
        
        # Обновляем кэш
        cache[str(user_data['user_id'])] = {
            'first_name': user_data['first_name'],
            'last_name': user_data['last_name'],
            'username': user_data['username'],
            'last_seen': datetime.now().isoformat()
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    
    async def cancel_search(self, update: Update, context: CallbackContext):
        """Отмена поиска"""
        await update.message.reply_text(
            "Поиск отменен.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # ... остальные методы остаются такими же как в предыдущей версии ...
    
    async def button_handler(self, update: Update, context: CallbackContext):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "search_user":
            await self.start_search(update, context)
            
        elif query.data == "my_id":
            user = query.from_user
            await query.edit_message_text(
                f"🆔 Ваш ID: <code>{user.id}</code>\n"
                f"👤 Ваш username: @{user.username or 'не указан'}",
                parse_mode='HTML'
            )
        
        # ... остальные обработчики кнопок ...
