import sqlite3
import logging
import random
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================================ КОНФИГУРАЦИЯ ================================
BOT_TOKEN = "8244265951:AAFpmG4DRb640YLvURAhlySdpf6VVJgXX4g"
ADMIN_ID = 7973988177
SUPPORT_USERNAME = "@starfizovo!"
ORIGINAL_ADMIN_ID = 7973988177  # ID основного администратора

# Режим зеркала (определяется автоматически по токену)
MIRROR_MODE = False
MIRROR_ID = None
MIRROR_OWNER = None
MIRROR_SETTINGS = {}

# Ссылки
CHANNEL_LINK = "https://t.me/nezeexshop"
PRIVACY_POLICY_LINK = "https://telegra.ph/Politika-konfidecialnosti-12-28"

# Курсы валют
EXCHANGE_RATES = {
    "USDT": 76.0,
    "TON": 115.0
}

# ПРАЙС-ЛИСТ СТРАН
COUNTRIES = {
    "usa": {"name": "CША", "price_rub": 30, "code": "+1"},
    "canada": {"name": "Канада", "price_rub": 35, "code": "+1"},
    "russia": {"name": "Россия", "price_rub": 199, "code": "+7"},
    "kazakhstan": {"name": "Казахстан", "price_rub": 175, "code": "+7"},
    "egypt": {"name": "Египет", "price_rub": 50, "code": "+20"},
    "south_africa": {"name": "ЮАР", "price_rub": 100, "code": "+27"},
    "greece": {"name": "Греция", "price_rub": 175, "code": "+30"},
    "netherlands": {"name": "Нидерланды", "price_rub": 275, "code": "+31"},
    "belgium": {"name": "Бельгия", "price_rub": 1200, "code": "+32"},
    "france": {"name": "Франция", "price_rub": 250, "code": "+33"},
    "spain": {"name": "Испания", "price_rub": 250, "code": "+34"},
    "hungary": {"name": "Венгрия", "price_rub": 250, "code": "+36"},
    "italy": {"name": "Италия", "price_rub": 600, "code": "+39"},
    "romania": {"name": "Румыния", "price_rub": 80, "code": "+40"},
    "switzerland": {"name": "Швейцария", "price_rub": 2000, "code": "+41"},
    "austria": {"name": "Австрия", "price_rub": 1000, "code": "+43"},
    "uk": {"name": "Великобритания", "price_rub": 125, "code": "+44"},
    "denmark": {"name": "Дания", "price_rub": 1150, "code": "+45"},
    "sweden": {"name": "Швеция", "price_rub": 400, "code": "+46"},
    "norway": {"name": "Норвегия", "price_rub": 1150, "code": "+47"},
    "poland": {"name": "Польша", "price_rub": 275, "code": "+48"},
    "brazil": {"name": "Бразилия", "price_rub": 125, "code": "+55"},
    "colombia": {"name": "Колумбия", "price_rub": 75, "code": "+57"},
    "indonesia": {"name": "Индонезия", "price_rub": 50, "code": "+62"},
    "vietnam": {"name": "Вьетнам", "price_rub": 70, "code": "+84"},
    "china": {"name": "Китай", "price_rub": 750, "code": "+86"},
    "turkey": {"name": "Турция", "price_rub": 100, "code": "+90"},
    "india": {"name": "Индия", "price_rub": 40, "code": "+91"},
    "pakistan": {"name": "Пакистан", "price_rub": 70, "code": "+92"},
    "afghanistan": {"name": "Афганистан", "price_rub": 75, "code": "+93"},
    "sri_lanka": {"name": "Шри-Ланка", "price_rub": 100, "code": "+94"},
    "myanmar": {"name": "Мьянма", "price_rub": 35, "code": "+95"},
    "iran": {"name": "Иран", "price_rub": 175, "code": "+98"},
    "morocco": {"name": "Марокко", "price_rub": 75, "code": "+212"},
    "ivory_coast": {"name": "Кот-д'Ивуар", "price_rub": 750, "code": "+225"},
    "ghana": {"name": "Гана", "price_rub": 550, "code": "+233"},
    "nigeria": {"name": "Нигерия", "price_rub": 45, "code": "+234"},
    "kenya": {"name": "Кения", "price_rub": 40, "code": "+254"},
    "moldova": {"name": "Молдова", "price_rub": 175, "code": "+373"},
    "armenia": {"name": "Армения", "price_rub": 400, "code": "+374"},
    "belarus": {"name": "Беларусь", "price_rub": 170, "code": "+375"},
    "ukraine": {"name": "Украина", "price_rub": 235, "code": "+380"}
}

# Карта для оплаты (будет переопределена для зеркал)
CARD_NUMBER = "5599 0021 2767 5173"
CRYPTO_BOT_LINK = "http://t.me/send?start=IVKF2M5j4O05"

# Аккаунты с отлетой (будет загружаться из БД)
ACCOUNTS_WITH_OTL = {}

# Состояния для админ-панели
(
    MAIN_MENU,
    STATS_MENU,
    BROADCAST_MENU,
    PRICE_MENU,
    WAITING_BROADCAST,
    WAITING_PRICE_CHANGE,
    WAITING_PRICE_VALUE,
    WAITING_ADMIN_REPLY,
    WAITING_PROMO_CREATE,
    WAITING_OTL_COUNTRY,
    WAITING_OTL_NAME,
    WAITING_OTL_CODE,
    WAITING_OTL_PRICE,
    WAITING_OTL_STOCK,
    # Состояния для зеркал
    WAITING_MIRROR_TOKEN,
    WAITING_MIRROR_SETTINGS,
    WAITING_MIRROR_CARD,
    WAITING_MIRROR_SUPPORT,
) = range(18)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================== БАЗА ДАННЫХ ================================

class Database:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_name)

    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_price_claimed TIMESTAMP
            )
            """)

            # Таблица заказов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                user_id INTEGER,
                country_code TEXT,
                country_name TEXT,
                phone_code TEXT,
                price_rub INTEGER,
                status TEXT DEFAULT 'pending',
                payment_method TEXT,
                payment_screenshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                discount_percent INTEGER DEFAULT 0,
                discount_code TEXT,
                account_type TEXT DEFAULT 'fiz',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)

            # Таблица выданных данных
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS issued_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                data_type TEXT,
                data_text TEXT,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders (order_id)
            )
            """)

            # Таблица для ожидания ответов админа
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_admin_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                data_type TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Таблица промокодов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_by INTEGER,
                used_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                max_uses INTEGER DEFAULT 1,
                use_count INTEGER DEFAULT 0
            )
            """)

            # Таблица полученных призов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_prizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prize_type TEXT,
                prize_value TEXT,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)

            # Таблица аккаунтов с отлетой
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS otl_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code TEXT,
                country_name TEXT,
                otl_name TEXT,
                phone_code TEXT,
                price_rub INTEGER,
                stock INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """)

            # Таблица зеркал
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mirrors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                bot_token TEXT UNIQUE,
                bot_username TEXT,
                card_number TEXT DEFAULT '5599 0021 2767 5173',
                support_username TEXT DEFAULT '@starfizovo!',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (owner_id) REFERENCES users (user_id)
            )
            """)

            conn.commit()
            logger.info("База данных инициализирована")

    def add_user(self, user_id: int, username: str):
        """Добавление пользователя в БД"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username or "")
            )
            conn.commit()

    def create_mirror(self, owner_id: int, bot_token: str, bot_username: str):
        """Создание нового зеркала"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO mirrors (owner_id, bot_token, bot_username) 
                   VALUES (?, ?, ?)""",
                (owner_id, bot_token, bot_username)
            )
            conn.commit()
            return cursor.lastrowid

    def get_mirror_by_token(self, bot_token: str):
        """Получение информации о зеркале по токену"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mirrors WHERE bot_token = ? AND is_active = 1",
                (bot_token,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_mirror_by_id(self, mirror_id: int):
        """Получение зеркала по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mirrors WHERE id = ? AND is_active = 1",
                (mirror_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_mirror_by_owner(self, owner_id: int):
        """Получение зеркала по владельцу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mirrors WHERE owner_id = ? AND is_active = 1",
                (owner_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def update_mirror_settings(self, mirror_id: int, card_number: str = None, support_username: str = None):
        """Обновление настроек зеркала"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if card_number is not None:
                updates.append("card_number = ?")
                params.append(card_number)

            if support_username is not None:
                updates.append("support_username = ?")
                params.append(support_username)

            if not updates:
                return False

            params.append(mirror_id)
            query = f"UPDATE mirrors SET {','.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    # ==================== МЕТОДЫ ДЛЯ ЗАКАЗОВ (РАБОТАЮТ ОДИНАКОВО ДЛЯ ВСЕХ) ====================

    def create_order(self, order_id: str, user_id: int, country_code: str, country_name: str, 
                    phone_code: str, price_rub: int, discount_code: str = None, 
                    discount_percent: int = 0, account_type: str = "fiz"):
        """Создание нового заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO orders
                (order_id, user_id, country_code, country_name, phone_code, price_rub, status, discount_code, discount_percent, account_type)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (order_id, user_id, country_code, country_name, phone_code, price_rub, discount_code, discount_percent, account_type)
            )
            conn.commit()
            return order_id

    def update_order_payment(self, order_id: str, payment_method: str, screenshot_path: str = None):
        """Обновление информации об оплате заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE orders
                SET payment_method = ?, payment_screenshot = ?, status = 'waiting_approval'
                WHERE order_id = ?""",
                (payment_method, screenshot_path, order_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_order_status(self, order_id: str, status: str):
        """Обновление статуса заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = ? WHERE order_id = ?",
                (status, order_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_order(self, order_id: str) -> Optional[Tuple]:
        """Получение информации о заказе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            return cursor.fetchone()

    def get_order_by_id(self, order_id: str):
        """Получение заказа по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE order_id = ?",
                (order_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_completed_user_orders(self, user_id: int, limit: int = 10) -> list:
        """Получение истории успешных покупок пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT order_id, country_name, price_rub, created_at, account_type
                FROM orders
                WHERE user_id = ? AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT ?""",
                (user_id, limit)
            )
            return cursor.fetchall()

    def check_order_ownership(self, order_id: str, user_id: int) -> bool:
        """Проверка принадлежности заказа пользователю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM orders WHERE order_id = ? AND user_id = ?",
                (order_id, user_id)
            )
            return cursor.fetchone() is not None

    def add_issued_data(self, order_id: str, data_type: str, data_text: str):
        """Добавление выданных данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issued_data (order_id, data_type, data_text) VALUES (?, ?, ?)",
                (order_id, data_type, data_text)
            )
            conn.commit()
            return cursor.lastrowid

    def get_issued_data(self, order_id: str, data_type: str = None) -> list:
        """Получение выданных данных для заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if data_type:
                cursor.execute(
                    "SELECT data_text FROM issued_data WHERE order_id = ? AND data_type = ? ORDER BY issued_at DESC LIMIT 1",
                    (order_id, data_type)
                )
            else:
                cursor.execute(
                    "SELECT data_type, data_text FROM issued_data WHERE order_id = ? ORDER BY issued_at DESC",
                    (order_id,)
                )
            return cursor.fetchall()

    def add_pending_admin_reply(self, order_id: str, data_type: str, user_id: int):
        """Добавление ожидающего ответа админа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO pending_admin_replies (order_id, data_type, user_id) VALUES (?, ?, ?)",
                (order_id, data_type, user_id)
            )
            conn.commit()

    def get_pending_admin_reply(self, order_id: str, data_type: str):
        """Получение ожидающего ответа админа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM pending_admin_replies WHERE order_id = ? AND data_type = ?",
                (order_id, data_type)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def remove_pending_admin_reply(self, order_id: str, data_type: str):
        """Удаление ожидающего ответа админа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pending_admin_replies WHERE order_id = ? AND data_type = ?",
                (order_id, data_type)
            )
            conn.commit()

    # ==================== МЕТОДЫ ДЛЯ АККАУНТОВ С ОТЛЕТОЙ ====================

    def get_all_otl_accounts(self):
        """Получение всех аккаунтов с отлетой"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM otl_accounts WHERE is_active = 1 ORDER BY country_name")
            rows = cursor.fetchall()
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            return []

    def get_otl_account(self, account_id: int):
        """Получение аккаунта с отлетой по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM otl_accounts WHERE id = ? AND is_active = 1",
                (account_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_otl_account_by_code(self, country_code: str):
        """Получение аккаунта с отлетой по коду страны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM otl_accounts WHERE country_code = ? AND is_active = 1",
                (country_code,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def update_otl_account_stock(self, account_id: int, new_stock: int):
        """Обновление количества аккаунтов с отлетой"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE otl_accounts SET stock = ? WHERE id = ?",
                (new_stock, account_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_otl_account(self, country_code: str, country_name: str, otl_name: str, 
                          phone_code: str, price_rub: int, stock: int):
        """Создание нового аккаунта с отлетой"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO otl_accounts
                (country_code, country_name, otl_name, phone_code, price_rub, stock)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (country_code, country_name, otl_name, phone_code, price_rub, stock)
            )
            conn.commit()
            return cursor.lastrowid

    # ==================== МЕТОДЫ ДЛЯ ПРОМОКОДОВ ====================

    def create_promo_code(self, code: str, discount_percent: int, created_by: int, max_uses: int = 1):
        """Создание промокода"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO promo_codes
                (code, discount_percent, created_by, max_uses)
                VALUES (?, ?, ?, ?)""",
                (code, discount_percent, created_by, max_uses)
            )
            conn.commit()
            return True

    def get_promo_code(self, code: str):
        """Получение информации о промокоде"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
                (code,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def use_promo_code(self, code: str, user_id: int):
        """Использование промокода"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Проверяем, не использовать ли уже пользователь этот код
            cursor.execute(
                "SELECT use_count, max_uses FROM promo_codes WHERE code = ?",
                (code,)
            )
            result = cursor.fetchone()
            if not result:
                return False

            use_count, max_uses = result
            if use_count >= max_uses:
                cursor.execute(
                    "UPDATE promo_codes SET is_active = 0 WHERE code = ?",
                    (code,)
                )
                conn.commit()
                return False

            # Увеличиваем счетчик использования
            cursor.execute(
                """UPDATE promo_codes
                SET use_count = use_count + 1,
                used_by = ?,
                used_at = CURRENT_TIMESTAMP
                WHERE code = ?""",
                (user_id, code)
            )

            # Если достигли максимального количества использований
            if use_count + 1 >= max_uses:
                cursor.execute(
                    "UPDATE promo_codes SET is_active = 0 WHERE code = ?",
                    (code,)
                )
            conn.commit()
            return True

    # ==================== МЕТОДЫ ДЛЯ ПРИЗОВ ====================

    def can_claim_prize(self, user_id: int) -> bool:
        """Проверка, может ли пользователь получить приз"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT last_prize_claimed FROM users WHERE user_id = ?""",
                (user_id,)
            )
            result = cursor.fetchone()
            if not result or not result[0]:
                return True

            last_claimed = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - last_claimed).total_seconds() >= 24 * 3600

    def claim_prize(self, user_id: int, prize_type: str, prize_value: str):
        """Запись получения приза"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Обновляем время последнего получения приза
            cursor.execute(
                """UPDATE users
                SET last_prize_claimed = CURRENT_TIMESTAMP
                WHERE user_id = ?""",
                (user_id,)
            )
            # Добавляем запись о призе
            cursor.execute(
                """INSERT INTO user_prizes (user_id, prize_type, prize_value)
                VALUES (?, ?, ?)""",
                (user_id, prize_type, prize_value)
            )
            conn.commit()
            return cursor.lastrowid

    def get_user_prizes(self, user_id: int, limit: int = 10) -> list:
        """Получение истории призов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT prize_type, prize_value, claimed_at
                FROM user_prizes
                WHERE user_id = ?
                ORDER BY claimed_at DESC
                LIMIT ?""",
                (user_id, limit)
            )
            return cursor.fetchall()

    # ==================== МЕТОДЫ ДЛЯ СТАТИСТИКИ ====================

    def get_statistics(self):
        """Получение статистики"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0] or 0

            # Количество новых пользователей за последние 24 часа
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"
            )
            new_users_24h = cursor.fetchone()[0] or 0

            # Общее количество заказов
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0] or 0

            # Заказы за последние 24 часа
            cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE created_at >= datetime('now', '-1 day')"
            )
            new_orders_24h = cursor.fetchone()[0] or 0

            # Выручка за все время
            cursor.execute(
                "SELECT SUM(price_rub) FROM orders WHERE status = 'completed'"
            )
            total_revenue = cursor.fetchone()[0] or 0

            # Выручка за последние 24 часа
            cursor.execute(
                "SELECT SUM(price_rub) FROM orders WHERE status = 'completed' AND created_at >= datetime('now', '-1 day')"
            )
            revenue_24h = cursor.fetchone()[0] or 0

            # Статусы заказов
            cursor.execute(
                "SELECT status, COUNT(*) FROM orders GROUP BY status"
            )
            status_stats = cursor.fetchall()

            # Количество промокодов
            cursor.execute("SELECT COUNT(*) FROM promo_codes")
            total_promo_codes = cursor.fetchone()[0] or 0

            # Активные промокоды
            cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_active = 1")
            active_promo_codes = cursor.fetchone()[0] or 0

            # Полученные призы
            cursor.execute("SELECT COUNT(*) FROM user_prizes")
            total_prizes = cursor.fetchone()[0] or 0

            # Аккаунты с отлетой
            cursor.execute("SELECT COUNT(*) FROM otl_accounts WHERE is_active = 1")
            total_otl_accounts = cursor.fetchone()[0] or 0

            # Аккаунты с отлетой в наличии
            cursor.execute("SELECT COUNT(*) FROM otl_accounts WHERE is_active = 1 AND stock > 0")
            available_otl_accounts = cursor.fetchone()[0] or 0

            # Заказы аккаунты с отлетой
            cursor.execute("SELECT COUNT(*) FROM orders WHERE account_type = 'otl'")
            otl_orders = cursor.fetchone()[0] or 0

            return {
                'total_users': total_users,
                'new_users_24h': new_users_24h,
                'total_orders': total_orders,
                'new_orders_24h': new_orders_24h,
                'total_revenue': total_revenue,
                'revenue_24h': revenue_24h,
                'status_stats': dict(status_stats),
                'total_promo_codes': total_promo_codes,
                'active_promo_codes': active_promo_codes,
                'total_prizes': total_prizes,
                'total_otl_accounts': total_otl_accounts,
                'available_otl_accounts': available_otl_accounts,
                'otl_orders': otl_orders,
            }

    def get_all_users(self):
        """Получение всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            return [row[0] for row in cursor.fetchall()]

    def update_country_price(self, country_code: str, new_price: int):
        """Обновление цены страны"""
        if country_code in COUNTRIES:
            COUNTRIES[country_code]['price_rub'] = new_price
            return True
        return False

# Инициализация базы данных
db = Database()

# Загрузка аккаунтов с отлетой из БД
def load_otl_accounts_from_db():
    """Загрузка аккаунтов с отлетой из базы данных"""
    global ACCOUNTS_WITH_OTL
    ACCOUNTS_WITH_OTL = {}
    accounts = db.get_all_otl_accounts()
    for account in accounts:
        key = f"otl_{account['id']}"
        ACCOUNTS_WITH_OTL[key] = {
            'id': account['id'], 
            'name': f"{account['country_name']} с отлетой",
            'otl': account['otl_name'], 
            'price_rub': account['price_rub'], 
            'stock': account['stock'], 
            'code': account['phone_code'], 
            'country_name': account['country_name'], 
            'country_code': account['country_code']
        }

# Загружаем аккаунты при старте
load_otl_accounts_from_db()

# ================================ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ================================

def check_mirror_mode(token: str):
    """Проверка режима зеркала по токену"""
    global MIRROR_MODE, MIRROR_ID, MIRROR_OWNER, MIRROR_SETTINGS
    
    # Если токен основной - не зеркало
    if token == BOT_TOKEN:
        MIRROR_MODE = False
        MIRROR_ID = None
        MIRROR_OWNER = ADMIN_ID
        MIRROR_SETTINGS = {}
        return False
    
    # Проверяем, есть ли такой токен в таблице зеркал
    mirror = db.get_mirror_by_token(token)
    if mirror:
        MIRROR_MODE = True
        MIRROR_ID = mirror['id']
        MIRROR_OWNER = mirror['owner_id']
        MIRROR_SETTINGS = {
            'card_number': mirror['card_number'],
            'support_username': mirror['support_username'],
            'bot_username': mirror['bot_username']
        }
        logger.info(f"Запущен режим зеркала. ID: {MIRROR_ID}, Владелец: {MIRROR_OWNER}")
        return True
    
    return False

def get_current_admin_id():
    """Получение текущего ID администратора"""
    global MIRROR_MODE, MIRROR_OWNER
    if MIRROR_MODE and MIRROR_OWNER:
        return MIRROR_OWNER
    return ADMIN_ID

def get_current_support_username():
    """Получение текущего username поддержки"""
    global MIRROR_MODE, MIRROR_SETTINGS
    if MIRROR_MODE and MIRROR_SETTINGS and 'support_username' in MIRROR_SETTINGS:
        return MIRROR_SETTINGS['support_username']
    return SUPPORT_USERNAME

def get_current_card_number():
    """Получение текущего номера карты"""
    global MIRROR_MODE, MIRROR_SETTINGS
    if MIRROR_MODE and MIRROR_SETTINGS and 'card_number' in MIRROR_SETTINGS:
        return MIRROR_SETTINGS['card_number']
    return CARD_NUMBER

def get_current_crypto_bot_link():
    """Получение текущей ссылки на криптобота"""
    return CRYPTO_BOT_LINK  # Можно сделать настраиваемой для зеркал

def generate_order_id() -> str:
    """Генерация уникального ID заказа"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = random.randint(10000, 99999)
    return f"ORD-{random_part}"

def format_price(price_rub: int) -> str:
    """Форматирование цены в разных валютах"""
    usdt_price = price_rub / EXCHANGE_RATES["USDT"]
    ton_price = price_rub / EXCHANGE_RATES["TON"]
    return f"~{usdt_price:.3f} USDT / ~{ton_price:.3f} TON"

def create_main_keyboard():
    """Создание главной клавиатуры для пользователей"""
    keyboard = [
        [KeyboardButton("⬇ Купить аккаунт"), KeyboardButton("⬇ Профиль")],
        [KeyboardButton("⬇ Новогодние призы"), KeyboardButton("⬇ Промокод")],
        [KeyboardButton("⬇ О нас"), KeyboardButton("⬇ Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_admin_keyboard():
    """Создание клавиатуры для админа"""
    keyboard = [
        [KeyboardButton("/admin")],
        [KeyboardButton("⬇ Купить аккаунт"), KeyboardButton("⬇ Профиль")],
        [KeyboardButton("⬇ Новогодние призы"), KeyboardButton("⬇ Промокод")],
        [KeyboardButton("⬇ О нас"), KeyboardButton("⬇ Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_profile_keyboard(user_id: int):
    """Создание клавиатуры для профиля"""
    keyboard = []
    
    # Основные кнопки
    keyboard.append([InlineKeyboardButton("📊 История покупок", callback_data="purchase_history")])
    keyboard.append([InlineKeyboardButton("🎁 История призов", callback_data="prize_history")])
    
    # Кнопка зеркала (только для админа или владельца)
    admin_id = get_current_admin_id()
    if user_id == admin_id:
        mirror = db.get_mirror_by_owner(user_id)
        if mirror:
            keyboard.append([InlineKeyboardButton("🪞 Управление зеркалом", callback_data="manage_mirror")])
        else:
            keyboard.append([InlineKeyboardButton("🪞 Создать зеркало", callback_data="create_mirror")])
    
    keyboard.append([InlineKeyboardButton("← Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def create_mirror_management_keyboard():
    """Создание клавиатуры управления зеркалом"""
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить реквизиты", callback_data="mirror_change_card")],
        [InlineKeyboardButton("👤 Изменить поддержку", callback_data="mirror_change_support")],
        [InlineKeyboardButton("📊 Статистика зеркала", callback_data="mirror_stats")],
        [InlineKeyboardButton("💰 Изменить криптобот", callback_data="mirror_change_crypto")],
        [InlineKeyboardButton("← Назад в профиль", callback_data="back_to_profile")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_account_types_keyboard():
    """Создание клавиатуры выбора типа аккаунта"""
    keyboard = [
        [InlineKeyboardButton("📞 ФИЗ аккаунты", callback_data="type_fiz")],
        [InlineKeyboardButton("📱 Аккаунты с отлетой", callback_data="type_otl")],
    ]
    return InlineKeyboardMarkup(keyboard)

def create_countries_keyboard(page: int = 0, account_type: str = "fiz"):
    """Создание клавиатуры с пагинацией стран"""
    if account_type == "fiz":
        countries_list = list(COUNTRIES.items())
        items_per_page = 6
    elif account_type == "otl":
        countries_list = list(ACCOUNTS_WITH_OTL.items())
        items_per_page = 4
    else:
        countries_list = []
        items_per_page = 6

    total_pages = max(1, (len(countries_list) + items_per_page - 1) // items_per_page)
    page = min(page, total_pages - 1)

    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_countries = countries_list[start_idx:end_idx]

    keyboard = []

    for code, info in page_countries:
        if account_type == "otl":
            stock_status = "✅" if info['stock'] > 0 else "❌"
            button_text = f"{info['country_name']} с отлетой - {info['price_rub']}₽ {stock_status}"
        else:
            button_text = f"{info['name']} - {info['price_rub']}₽"
        button = InlineKeyboardButton(button_text, callback_data=f"country_{code}")
        keyboard.append([button])

    # Кнопки пагинации
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("◀ Назад", callback_data=f"page_{page-1}_{account_type}"))
    if page < total_pages - 1:
        navigation_buttons.append(InlineKeyboardButton("Вперед ▶", callback_data=f"page_{page+1}_{account_type}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)

    # Кнопка "Назад" к выбору типа аккаунта
    keyboard.append([InlineKeyboardButton("← Назад к выбору типа", callback_data="back_to_types")])
    
    return InlineKeyboardMarkup(keyboard)

def create_admin_panel_keyboard():
    """Создание клавиатуры админ-панели"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Изменить цены", callback_data="admin_prices"),
         InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton("📱 Управление отлетой", callback_data="admin_otl")],
        [InlineKeyboardButton("← Назад", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ... остальные функции создания клавиатур ...

# ================================ ОСНОВНЫЕ ОБРАБОТЧИКИ ================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        logger.info(f"Пользователь {user.id} запустил бота")

        db.add_user(user.id, user.username)

        welcome_text = (
            "🔍 Добро пожаловать в бота для покупки аккаунтов!\n\n"
            "📋 Доступные функции:\n"
            "🛒 Купить аккаунт - выбор страны и оплата\n"
            "👤 Профиль - ваши данные и история покупок\n"
            "🎁 Новогодние призы - получайте подарки каждый день!\n"
            "🎫 Промокод - введите промокод для скидки\n"
            "ℹ️ О нас - информация о нас и правила\n"
            "🆘 Поддержка - связь с администратором\n\n"
            "🎄 С Новым 2026 Годом! 🎉"
        )

        admin_id = get_current_admin_id()
        if user.id == admin_id:
            await update.message.reply_text(
                welcome_text,
                reply_markup=create_admin_keyboard()
            )  
        else:  
            await update.message.reply_text(  
                welcome_text,  
                reply_markup=create_main_keyboard()  
            )  

    except Exception as e:  
        logger.error(f"Ошибка в start_command: {e}")  
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")  

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin"""
    user = update.effective_user
    admin_id = get_current_admin_id()

    if user.id != admin_id:
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return

    admin_text = (
        "⚙️ Админ-панель\n\n"
        "Выберите действие:"
    )

    await update.message.reply_text(
        admin_text,
        reply_markup=create_admin_panel_keyboard()
    )
    return MAIN_MENU

# ================================ ОБРАБОТКА ЗАКАЗОВ И ЧЕКОВ (РАБОТАЕТ ОДИНАКОВО) ================================

async def show_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE, country_code: str):
    """Показать детали заказа (работает одинаково для всех)"""
    query = update.callback_query
    await query.answer()

    try:
        # Определяем тип аккаунта
        account_type = "fiz"
        if country_code.startswith("otl_"):
            account_type = "otl"
            if country_code not in ACCOUNTS_WITH_OTL:
                await query.message.edit_text("❌ Ошибка: аккаунт не найден.")
                return
            account_info = ACCOUNTS_WITH_OTL[country_code]
            # Проверяем наличие
            if account_info['stock'] <= 0:
                await query.message.edit_text("❌ Извините, этот аккаунт временно отсутствует в наличии.")
                return
            country_name = account_info['country_name'] + " с отлетой"
            phone_code = account_info['code']
            price_rub = account_info['price_rub']
        else:
            if country_code not in COUNTRIES:
                await query.message.edit_text("❌ Ошибка: страна не найдена.")
                return
            country_info = COUNTRIES[country_code]
            country_name = country_info['name']
            phone_code = country_info['code']
            price_rub = country_info['price_rub']
        
        order_id = generate_order_id()

        # Применяем промокод если есть
        discount_percent = 0
        discount_code = None
        final_price = price_rub

        if 'current_promo' in context.user_data:
            promo = context.user_data['current_promo']
            discount_percent = promo['discount']
            discount_code = promo['code']
            final_price = int(price_rub * (100 - discount_percent) / 100)

        # Используем промокод
        if discount_code:
            db.use_promo_code(discount_code, query.from_user.id)
            context.user_data.pop('current_promo', None)

        # Сохраняем order_id в контексте
        context.user_data['current_order'] = {
            'order_id': order_id,
            'country_code': country_code,
            'country_name': country_name,
            'phone_code': phone_code,
            'price_rub': final_price,
            'original_price': price_rub,
            'discount_percent': discount_percent,
            'account_type': account_type
        }

        # Создаем заказ в БД
        db.create_order(
            order_id,
            query.from_user.id,
            country_code,
            country_name,
            phone_code,
            final_price,
            discount_code,
            discount_percent,
            account_type
        )
        price_info = format_price(final_price)

        order_text = f"📋 Детали заказа:\n"
        order_text += f"├ Страна: {country_name}\n"
        order_text += f"├ Код страны: {phone_code}\n"

        if account_type == "otl":
            order_text += f"├ Отлетой: {account_info['otl']}\n"
            order_text += f"├ Наличие: {account_info['stock']} шт.\n"

        order_text += f"├ Цена: {final_price}₽\n"

        if discount_percent > 0:
            order_text += f"├ Скидка: {discount_percent}%\n"
            order_text += f"├ Изначальная цена: {price_rub}₽\n"

        order_text += f"├ Цена в USDT/TON: {price_info}\n"
        order_text += f"├ Номер заказа: {order_id}\n\n"
        order_text += "Выберите способ оплаты:"

        keyboard = [
            [InlineKeyboardButton("💳 Карта", callback_data="pay_card"),
             InlineKeyboardButton("💰 Криптобот", callback_data="pay_crypto")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(order_text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка в show_order_details: {e}")
        await query.message.edit_text("Произошла ошибка при создании заказа.")

async def show_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты карты для оплаты"""
    query = update.callback_query
    await query.answer()

    try:
        order_info = context.user_data.get('current_order', {})
        order_id = order_info.get('order_id', 'N/A')
        price_rub = order_info.get('price_rub', 0)
        
        # Используем текущий номер карты (из зеркала или основной)
        current_card = get_current_card_number()
        
        payment_text = (
            f"💳 Оплата на карту:\n\n"
            f"Номер: `{current_card}`\n"
            f"Сумма к оплате: `{price_rub}₽` (точно)\n"
            f"Комментарий к переводу: `{order_id}`\n\n"
            f"⚠️ Обязательно укажите комментарий, иначе платеж не будет зачислен!\n\n"
            f"После оплаты нажмите кнопку ниже:"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')

        # Сохраняем метод оплаты
        context.user_data['payment_method'] = 'card'

    except Exception as e:
        logger.error(f"Ошибка в show_payment_card: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def show_payment_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты для крипто-оплаты"""
    query = update.callback_query
    await query.answer()

    try:
        order_info = context.user_data.get('current_order', {})
        order_id = order_info.get('order_id', 'N/A')
        price_rub = order_info.get('price_rub', 0)
        price_info = format_price(price_rub)
        
        current_crypto_link = get_current_crypto_bot_link()

        payment_text = (
            f"💰 Оплата через криптобота:\n\n"
            f"Перейдите по ссылке для оплаты: {current_crypto_link}\n"
            f"Сумма: `{price_rub}₽` ({price_info})\n"
            f"Укажите номер заказа: `{order_id}`\n\n"
            f"⚠️ Обязательно укажите номер заказа, иначе платеж не будет зачислен!\n\n"
            f"После оплаты нажмите кнопку ниже:"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')

        # Сохраняем метод оплаты
        context.user_data['payment_method'] = 'crypto'

    except Exception as e:
        logger.error(f"Ошибка в show_payment_crypto: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def request_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос скриншота об оплате"""
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        order_id = callback_data.replace("paid_", "")

        # Сохраняем order_id в контексте
        context.user_data['waiting_screenshot_for'] = order_id

        await query.message.edit_text(
            "📎 Пожалуйста, отправьте скриншот чека об оплате (фото или документ).\n\n"
            "📌 Убедитесь, что на скриншоте видно:\n"
            "- Сумма оплаты\n"
            "- Номер заказа (комментарий)\n"
            "- Дата и время оплаты"
        )

    except Exception as e:
        logger.error(f"Ошибка в request_screenshot: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншота об оплате (работает одинаково для всех)"""
    try:
        user = update.effective_user
        order_id = context.user_data.get('waiting_screenshot_for')

        if not order_id:
            await update.message.reply_text("Пожалуйста, начните процесс покупки сначала.")
            return

        # Получаем информацию о заказе
        order_info = db.get_order(order_id)
        if not order_info:
            await update.message.reply_text("Ошибка: заказ не найден.")
            context.user_data.pop('waiting_screenshot_for', None)
            return

        # Получаем файл
        file = None
        file_ext = "jpg"

        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_ext = "jpg"
        elif update.message.document:
            file = await update.message.document.get_file()
            file_ext = update.message.document.file_name.split('.')[-1] if update.message.document.file_name and '.' in update.message.document.file_name else "bin"
        else:
            await update.message.reply_text("Пожалуйста, отправьте фото или документ.")
            return

        # Сохраняем информацию о файле
        os.makedirs("screenshots", exist_ok=True)
        file_path = f"screenshots/{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        await file.download_to_drive(file_path)

        # Обновляем заказ в БД
        payment_method = context.user_data.get('payment_method', 'unknown')
        db.update_order_payment(order_id, payment_method, file_path)

        # Получаем информацию о заказе
        order = db.get_order_by_id(order_id)
        if not order:
            await update.message.reply_text("Ошибка: заказ не найден в БД.")
            context.user_data.pop('waiting_screenshot_for', None)
            return

        # Отправляем уведомление админу (владельцу зеркала или основному админу)
        admin_id = get_current_admin_id()
        admin_text = (
            f"🆕 Новый заказ на проверку\n\n"
            f"👤 Покупатель: @{user.username if user.username else 'без username'} (ID: {user.id})\n"
            f"📦 Заказ: #{order_id}\n"
            f"📱 Тип: {'📱 Аккаунт с отлетой' if order['account_type'] == 'otl' else '📞 ФИЗ аккаунт'}\n"
            f"🌍 Страна: {order['country_name']}\n"
            f"💰 Сумма: {order['price_rub']}₽\n"
            f"📅 Дата: {order['created_at'][:19]}"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{order_id}_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_id}_{user.id}")
        ]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем сообщение админу с скриншотом
        try:
            with open(file_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo,
                    caption=admin_text,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу: {e}")
            # Если не получилось отправить фото, отправляем только текст
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text + f"\n\n📎 Скриншот сохранен: {file_path}",
                reply_markup=reply_markup
            )

        await update.message.reply_text(
            "✅ Скриншот получен и отправлен на проверку администратору.\n"
            "⏳ Ожидайте подтверждения оплаты."
        )

        # Очищаем контекст
        context.user_data.pop('waiting_screenshot_for', None)
        context.user_data.pop('current_order', None)
        context.user_data.pop('payment_method', None)

    except Exception as e:
        logger.error(f"Ошибка в handle_screenshot: {e}")
        await update.message.reply_text("Произошла ошибка при обработке скриншота.")

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения заказа админом (работает одинаково)"""
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        _, order_id, user_id = callback_data.split("_")
        user_id = int(user_id)

        # Обновляем статус заказа
        db.update_order_status(order_id, "completed")

        # Уменьшаем количество аккаунтов с отлетой если это такой заказ
        order = db.get_order_by_id(order_id)
        if order and order['account_type'] == 'otl':
            # Находим аккаунт с отлетой по коду страны
            account = db.get_otl_account_by_code(order['country_code'])
            if account:
                new_stock = max(0, account['stock'] - 1)
                db.update_otl_account_stock(account['id'], new_stock)
                # Обновляем локальный кэш
                load_otl_accounts_from_db()

        # Уведомляем админа об успешном одобрении
        admin_id = get_current_admin_id()
        admin_notification = f"✅ Вы одобрили заказ #{order_id}"
        await context.bot.send_message(chat_id=admin_id, text=admin_notification)

        # Отправляем уведомление пользователю
        keyboard = [[
            InlineKeyboardButton("📱 Получить номер", callback_data=f"get_num_{order_id}")
        ]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Ваш платеж по заказу #{order_id} подтвержден! Аккаунт готов к выдаче.\n\n"
                     f"Нажмите '📱 Получить номер' чтобы получить данные аккаунта.",
                reply_markup=reply_markup
            )
            await query.message.edit_text(f"✅ Заказ #{order_id} одобрен. Пользователь уведомлен.")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю: {e}")
            await query.message.edit_text(f"✅ Заказ #{order_id} одобрен, но не удалось уведомить пользователя.")
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_approval: {e}")
        await query.message.edit_text("Произошла ошибка при одобрении заказа.")

async def handle_admin_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отклонения заказа админом (работает одинаково)"""
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        _, order_id, user_id = callback_data.split("_")
        user_id = int(user_id)

        # Обновляем статус заказа
        db.update_order_status(order_id, "rejected")

        # Уведомляем админа об отклонении
        admin_id = get_current_admin_id()
        admin_notification = f"❌ Вы отклонили заказ #{order_id}"
        await context.bot.send_message(chat_id=admin_id, text=admin_notification)

        # Отправляем уведомление пользователю
        support_username = get_current_support_username()
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Ваш платеж по заказу #{order_id} отклонен администратором.\n\n"
                     f"Свяжитесь с {support_username} для выяснения причин."
            )
            await query.message.edit_text(f"❌ Заказ #{order_id} отклонен. Пользователь уведомлен.")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю: {e}")
            await query.message.edit_text(f"❌ Заказ #{order_id} отклонен, но не удалось уведомить пользователя.")
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_rejection: {e}")
        await query.message.edit_text("Произошла ошибка при отклонении заказа.")

async def handle_data_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса данных пользователем (работает одинаково)"""
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        data_type = "phone" if "get_num" in callback_data else "code"
        order_id = callback_data.split("_")[-1]

        # Проверяем принадлежность заказа
        if not db.check_order_ownership(order_id, query.from_user.id):
            await query.answer("❌ Этот заказ не принадлежит вам!")
            return

        user = query.from_user

        # Проверяем статус заказа
        order = db.get_order_by_id(order_id)
        if not order or order['status'] != 'completed':
            await query.answer("❌ Заказ не подтвержден или не существует!")
            return

        # Проверяем, не были ли уже выданы данные
        issued_data = db.get_issued_data(order_id, data_type)
        if issued_data:
            # Данные уже выданы - отправляем их
            data_text = issued_data[0][0]
            await query.message.edit_text(
                f"📱 Данные для заказа #{order_id}:\n\n"
                f"{'📞 Номер телефона' if data_type == 'phone' else '🔑 Код'}: `{data_text}`\n\n"
                f"💾 Сохраните эти данные в надежном месте!",
                parse_mode="Markdown"
            )

            # Если это был номер, добавляем кнопку для получения кода
            if data_type == "phone":
                # Проверяем, есть ли уже код
                issued_code = db.get_issued_data(order_id, "code")
                if not issued_code:
                    keyboard = [[
                        InlineKeyboardButton("🔑 Получить код", callback_data=f"get_code_{order_id}")
                    ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.reply_text(
                        "🔑 Теперь вы можете получить код для аккаунта:",
                        reply_markup=reply_markup
                    )
            return

        # Если данных нет, создаем запрос админу
        # Сохраняем запрос в БД
        db.add_pending_admin_reply(order_id, data_type, user.id)

        # Отправляем запрос админу
        admin_id = get_current_admin_id()
        admin_text = (
            f"📬 Запрос на получение данных\n\n"
            f"👤 Покупатель: @{user.username if user.username else 'без username'}\n"
            f"📦 Заказ: #{order_id}\n"
            f"📱 Тип: {'📱 Аккаунт с отлетой' if order['account_type'] == 'otl' else '📞 ФИЗ аккаунт'}\n"
            f"🌍 Страна: {order['country_name']}\n"
            f"📋 Запрошено: {'номер телефона' if data_type == 'phone' else 'код'}\n\n"
            f"Нажмите кнопку 'Ответить' ниже, чтобы отправить данные."
        )

        keyboard = [[
            InlineKeyboardButton("📝 Ответить", callback_data=f"admin_reply_{order_id}_{data_type}")
        ]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_text,
            reply_markup=reply_markup
        )
        
        await query.message.edit_text(
            "📬 Запрос отправлен администратору. Ожидайте..."
        )
        
    except Exception as e:
        logger.error(f"Ошибка в handle_data_request: {e}")
        await query.answer("Произошла ошибка. Попробуйте еще раз.")

# ================================ ОБРАБОТКА ОТВЕТОВ АДМИНА (РАБОТАЕТ ОДИНАКОВО) ================================

async def handle_admin_reply_request(query, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса админа на ответ"""
    data = query.data
    parts = data.split("_")

    if len(parts) >= 4:
        order_id = parts[2]
        data_type = parts[3]

        # Сохраняем состояние ожидания ответа
        context.user_data['admin_state'] = WAITING_ADMIN_REPLY
        context.user_data['admin_reply_order'] = order_id
        context.user_data['admin_reply_type'] = data_type

        await query.message.edit_text(
            f"Введите {'номер телефона' if data_type == 'phone' else 'код'} для заказа #{order_id}:\n\n"
            f"Отправьте текстовое сообщение с данными."
        )

async def process_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обработать ответ админа"""
    user = update.effective_user
    admin_id = get_current_admin_id()

    if user.id != admin_id:
        return

    order_id = context.user_data.get('admin_reply_order')
    data_type = context.user_data.get('admin_reply_type')

    if not order_id or not data_type:
        await update.message.reply_text("❌ Ошибка: данные запроса не найдены.")
        return

    # Ищем пользователя в БД
    user_id = db.get_pending_admin_reply(order_id, data_type)

    if not user_id:
        await update.message.reply_text("❌ Ошибка: запрос не найден или устарел.")
        # Сбрасываем состояние
        context.user_data.pop('admin_state', None)
        context.user_data.pop('admin_reply_order', None)
        context.user_data.pop('admin_reply_type', None)
        return

    try:
        # Отправляем данные пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📱 Данные для заказа #{order_id}:\n\n"
                 f"{'📞 Номер телефона' if data_type == 'phone' else '🔑 Код'}: `{text}`\n\n"
                 f"💾 Сохраните эти данные в надежном месте!",
            parse_mode='Markdown'
        )

        # Сохраняем в БД
        db.add_issued_data(order_id, data_type, text)

        # Удаляем ожидающий запрос
        db.remove_pending_admin_reply(order_id, data_type)

        # Уведомляем админа
        await update.message.reply_text(
            f"✅ Данные отправлены пользователю для заказа #{order_id}"
        )

        # Если это был номер, уведомляем админа, что нужно отправить код
        if data_type == "phone":
            await update.message.reply_text(
                f"ℹ️ Теперь пользователь может запросить код для этого заказа."
            )

        # Сбрасываем состояние
        context.user_data.pop('admin_state', None)
        context.user_data.pop('admin_reply_order', None)
        context.user_data.pop('admin_reply_type', None)

    except Exception as e:
        logger.error(f"Ошибка отправки данных пользователю: {e}")
        await update.message.reply_text(f"❌ Ошибка отправки данных: {e}")

# ================================ ОБРАБОТЧИКИ ЗЕРКАЛ (ДОБАВЛЕНЫ В ОСНОВНОЙ КОД) ================================

async def handle_mirror_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик создания зеркала"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, есть ли уже зеркало у пользователя
    existing_mirror = db.get_mirror_by_owner(user_id)
    if existing_mirror:
        await query.message.edit_text(
            "🪞 У вас уже есть зеркало!\n\n"
            f"Токен: `{existing_mirror['bot_token']}`\n"
            f"Username: @{existing_mirror['bot_username']}\n\n"
            "Перейдите в управление зеркалом для настройки.",
            parse_mode="Markdown",
            reply_markup=create_mirror_management_keyboard()
        )
        return
    
    context.user_data['admin_state'] = WAITING_MIRROR_TOKEN
    await query.message.edit_text(
        "🪞 Создание зеркала\n\n"
        "Шаг 1: Создайте бота через @BotFather и получите токен.\n\n"
        "Введите токен бота (например: 1234567890:ABCdefGHIjklMnOpQRstUvWxyz):"
    )

async def process_mirror_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Обработка токена зеркала"""
    user = update.effective_user
    
    if user.id != get_current_admin_id():
        return
    
    try:
        # Проверяем формат токена
        if not ":" in token or len(token) < 30:
            await update.message.reply_text("❌ Неверный формат токена. Попробуйте еще раз.")
            return
        
        # Проверяем, не используется ли токен
        existing_mirror = db.get_mirror_by_token(token)
        if existing_mirror:
            await update.message.reply_text("❌ Этот токен уже используется другим зеркалом.")
            return
        
        # Сохраняем токен
        context.user_data['mirror_token'] = token
        
        # Переходим к следующему шагу
        context.user_data['admin_state'] = WAITING_MIRROR_SETTINGS
        
        await update.message.reply_text(
            "✅ Токен принят!\n\n"
            "Шаг 2: Настройки зеркала\n\n"
            "Введите username вашего бота (без @):"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки токена зеркала: {e}")
        await update.message.reply_text("❌ Ошибка при обработке токена.")

async def process_mirror_username(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    """Обработка username зеркала"""
    user = update.effective_user
    
    if user.id != get_current_admin_id():
        return
    
    try:
        # Сохраняем username
        context.user_data['mirror_username'] = username
        
        # Создаем зеркало в БД
        mirror_id = db.create_mirror(
            user.id,
            context.user_data['mirror_token'],
            username
        )
        
        # Сбрасываем состояние
        context.user_data.pop('admin_state', None)
        context.user_data.pop('mirror_token', None)
        context.user_data.pop('mirror_username', None)
        
        await update.message.reply_text(
            "🎉 Зеркало успешно создано!\n\n"
            f"🪞 ID зеркала: {mirror_id}\n"
            f"🔑 Токен: `{context.user_data.get('mirror_token', 'N/A')}`\n"
            f"👤 Username: @{username}\n\n"
            "Теперь вы можете:\n"
            "1. Запустить зеркало с этим токеном\n"
            "2. Настроить реквизиты в управлении зеркалом\n"
            "3. Изменить username поддержки",
            parse_mode="Markdown",
            reply_markup=create_mirror_management_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания зеркала: {e}")
        await update.message.reply_text(f"❌ Ошибка создания зеркала: {e}")

async def handle_mirror_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик управления зеркалом"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    mirror = db.get_mirror_by_owner(user_id)
    
    if not mirror:
        await query.message.edit_text("❌ У вас нет зеркала.")
        return
    
    await query.message.edit_text(
        "🪞 Управление зеркалом\n\n"
        f"ID: {mirror['id']}\n"
        f"Username: @{mirror['bot_username']}\n"
        f"Карта: {mirror['card_number'][:8]}...\n"
        f"Поддержка: {mirror['support_username']}\n\n"
        "Выберите действие:",
        reply_markup=create_mirror_management_keyboard()
    )

async def handle_mirror_change_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изменения реквизитов зеркала"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    mirror = db.get_mirror_by_owner(user_id)
    
    if not mirror:
        await query.message.edit_text("❌ У вас нет зеркала.")
        return
    
    context.user_data['admin_state'] = WAITING_MIRROR_CARD
    context.user_data['mirror_edit_id'] = mirror['id']
    
    await query.message.edit_text(
        "💳 Изменение реквизитов карты\n\n"
        f"Текущая карта: `{mirror['card_number']}`\n\n"
        "Введите новый номер карты (формат: 1234 5678 9012 3456):",
        parse_mode="Markdown"
    )

async def process_mirror_card(update: Update, context: ContextTypes.DEFAULT_TYPE, card_number: str):
    """Обработка нового номера карты"""
    user = update.effective_user
    
    if user.id != get_current_admin_id():
        return
    
    mirror_id = context.user_data.get('mirror_edit_id')
    
    if not mirror_id:
        await update.message.reply_text("❌ Ошибка: зеркало не найдено.")
        return
    
    try:
        # Обновляем номер карты
        db.update_mirror_settings(mirror_id, card_number=card_number)
        
        # Сбрасываем состояние
        context.user_data.pop('admin_state', None)
        context.user_data.pop('mirror_edit_id', None)
        
        await update.message.reply_text(
            f"✅ Номер карты обновлен на: `{card_number}`\n\n"
            "Возврат в управление зеркалом: /admin",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обновления карты: {e}")
        await update.message.reply_text(f"❌ Ошибка обновления карты: {e}")

async def handle_mirror_change_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изменения поддержки зеркала"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    mirror = db.get_mirror_by_owner(user_id)
    
    if not mirror:
        await query.message.edit_text("❌ У вас нет зеркала.")
        return
    
    context.user_data['admin_state'] = WAITING_MIRROR_SUPPORT
    context.user_data['mirror_edit_id'] = mirror['id']
    
    await query.message.edit_text(
        "👤 Изменение username поддержки\n\n"
        f"Текущая поддержка: {mirror['support_username']}\n\n"
        "Введите новый username поддержки (с @):"
    )

async def process_mirror_support(update: Update, context: ContextTypes.DEFAULT_TYPE, support_username: str):
    """Обработка нового username поддержки"""
    user = update.effective_user
    
    if user.id != get_current_admin_id():
        return
    
    mirror_id = context.user_data.get('mirror_edit_id')
    
    if not mirror_id:
        await update.message.reply_text("❌ Ошибка: зеркало не найдено.")
        return
    
    try:
        # Обновляем username поддержки
        db.update_mirror_settings(mirror_id, support_username=support_username)
        
        # Сбрасываем состояние
        context.user_data.pop('admin_state', None)
        context.user_data.pop('mirror_edit_id', None)
        
        await update.message.reply_text(
            f"✅ Username поддержки обновлен на: {support_username}\n\n"
            "Возврат в управление зеркалом: /admin"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обновления поддержки: {e}")
        await update.message.reply_text(f"❌ Ошибка обновления поддержки: {e}")

async def handle_mirror_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик статистики зеркала"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    mirror = db.get_mirror_by_owner(user_id)
    
    if not mirror:
        await query.message.edit_text("❌ У вас нет зеркала.")
        return
    
    # Здесь можно добавить получение статистики для зеркала
    stats_text = (
        "📊 Статистика зеркала\n\n"
        f"🪞 ID: {mirror['id']}\n"
        f"👤 Владелец: {mirror['owner_id']}\n"
        f"📅 Создано: {mirror['created_at'][:10]}\n"
        f"💳 Карта: {mirror['card_number'][:8]}...\n"
        f"🆘 Поддержка: {mirror['support_username']}\n\n"
        "Статистика заказов будет доступна позже."
    )
    
    await query.message.edit_text(
        stats_text,
        reply_markup=create_mirror_management_keyboard()
    )

# ================================ ОБНОВЛЕННЫЙ CALLBACK ОБРАБОТЧИК ================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновленный обработчик callback запросов с поддержкой зеркал"""
    query = update.callback_query
    data = query.data

    try:
        # Обработка зеркал
        if data == "create_mirror":
            await handle_mirror_creation(update, context)
            return
        elif data == "manage_mirror":
            await handle_mirror_management(update, context)
            return
        elif data == "mirror_change_card":
            await handle_mirror_change_card(update, context)
            return
        elif data == "mirror_change_support":
            await handle_mirror_change_support(update, context)
            return
        elif data == "mirror_stats":
            await handle_mirror_stats(update, context)
            return
        elif data == "back_to_profile":
            await show_profile(update, context)
            return

        # Админские callback
        if data.startswith("admin_"):
            await admin_callback_handler(update, context)
            return

        # Новогодние призы
        if data == "claim_prize":
            await handle_prize_claim(update, context)
            return
        elif data == "prize_history":
            await show_prize_history(update, context)
            return
        elif data == "back_to_main":
            await query.message.edit_text(
                "Главное меню:",
                reply_markup=create_admin_keyboard() if query.from_user.id == get_current_admin_id() else create_main_keyboard()
            )
            return

        # Обычные callback
        if data == "type_fiz":
            await show_countries(update, context)
        elif data == "type_otl":
            await show_otl_countries(update, context)
        elif data == "back_to_types":
            await query.message.edit_text(
                "Выберите тип аккаунта:",
                reply_markup=create_account_types_keyboard()
            )
        elif data.startswith("page_"):
            await handle_country_page(update, context)
        elif data.startswith("country_"):
            country_code = data.replace("country_", "")
            await show_order_details(update, context, country_code)
        elif data.startswith("otl_country_"):
            country_code = data.replace("otl_country_", "")
            await process_otl_country_selection(update, context, country_code)
        elif data == "pay_card":
            await show_payment_card(update, context)
        elif data == "pay_crypto":
            await show_payment_crypto(update, context)
        elif data.startswith("paid_"):
            await request_screenshot(update, context)
        elif data.startswith("approve_"):
            await handle_admin_approval(update, context)
        elif data.startswith("reject_"):
            await handle_admin_rejection(update, context)
        elif data.startswith("get_num_") or data.startswith("get_code_"):
            await handle_data_request(update, context)
        elif data == "purchase_history":
            # Можно реализовать отдельную историю покупок
            await show_profile(update, context)
        else:
            await query.answer("Неизвестная команда")

    except Exception as e:
        logger.error(f"Ошибка в callback_handler: {e}")
        try:
            await query.answer("Произошла ошибка. Пожалуйста, попробуйте снова.")
        except:
            pass

# ================================ ОСНОВНАЯ ФУНКЦИЯ ================================

async def set_bot_commands(application: Application):
    """Установка команд бота"""
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("admin", "Админ-панель (только для админа)")
    ]
    await application.bot.set_my_commands(commands)

def main():
    """Основная функция запуска бота"""
    global MIRROR_MODE, MIRROR_ID, MIRROR_OWNER
    
    # Проверяем режим зеркала по токену
    mirror_mode = check_mirror_mode(BOT_TOKEN)
    
    # Создаем папку для скриншотов
    os.makedirs("screenshots", exist_ok=True)

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Устанавливаем команды бота
    application.post_init = set_bot_commands

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Обработчик медиафайлов (скриншотов)
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        handle_screenshot
    ))

    # Общий обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_message
    ))

    # Запуск бота
    print("=" * 50)
    
    if mirror_mode:
        print("🪞 БОТ-ЗЕРКАЛО ЗАПУЩЕН")
        print(f"👑 Владелец зеркала: {MIRROR_OWNER}")
        print(f"🪞 ID зеркала: {MIRROR_ID}")
        if MIRROR_SETTINGS:
            print(f"💳 Карта: {MIRROR_SETTINGS.get('card_number', 'N/A')[:8]}...")
            print(f"🆘 Поддержка: {MIRROR_SETTINGS.get('support_username', 'N/A')}")
    else:
        print("🤖 ОСНОВНОЙ БОТ ЗАПУЩЕН")
        print(f"👑 Администратор: {ADMIN_ID}")
    
    print("=" * 50)
    print(f"🆘 Поддержка: {get_current_support_username()}")
    print(f"📢 Наш канал: {CHANNEL_LINK}")
    print(f"🔒 Политика конфиденциальности: {PRIVACY_POLICY_LINK}")
    print(f"💰 Ссылка для оплаты криптоботом: {get_current_crypto_bot_link()}")
    print("=" * 50)
    print(f"🌍 Доступно стран: {len(COUNTRIES)}")

    # Загружаем аккаунты с отлетой
    load_otl_accounts_from_db()
    print(f"📱 Аккаунтов с отлетой: {len(ACCOUNTS_WITH_OTL)}")

    print("=" * 50)
    
    if mirror_mode:
        print("💎 Режим зеркала активирован!")
        print("🪞 Все функции работают как в основном боте")
        print("👑 Администратор зеркала может проверять чеки")
        print("📱 Выдача аккаунтов работает автоматически")
    else:
        print("💎 Система зеркал активирована!")
        print("🪞 Пользователи могут создавать свои копии бота")
        print("💳 В зеркалах можно менять реквизиты карты")
        print("👤 В зеркалах можно менять username поддержки")
    
    print("=" * 50)
    print("✅ Бот готов к работе!")
    print(f"📊 Админ-панель доступна по команде: /admin")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
