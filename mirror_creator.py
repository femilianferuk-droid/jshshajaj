import os
import shutil
import json

class MirrorCreator:
    @staticmethod
    def create_mirror(token, original_bot_path="bot.py", mirror_name="mirror_bot"):
        """Создание зеркала бота"""
        
        # Создаем директорию для зеркала
        mirror_dir = f"{mirror_name}"
        if not os.path.exists(mirror_dir):
            os.makedirs(mirror_dir)
        
        # Копируем основной файл бота
        shutil.copy(original_bot_path, os.path.join(mirror_dir, "bot.py"))
        
        # Создаем requirements.txt
        requirements = [
            "python-telegram-bot[job-queue]==20.3",
            "python-dotenv"
        ]
        
        with open(os.path.join(mirror_dir, "requirements.txt"), "w") as f:
            f.write("\n".join(requirements))
        
        # Создаем config.py с токеном
        config_content = f"""
# Конфигурация зеркала-бота
TOKEN = "{token}"
ADMIN_IDS = []  # Добавьте ID администраторов
DATABASE_URL = "users_data.json"
"""
        
        with open(os.path.join(mirror_dir, "config.py"), "w", encoding="utf-8") as f:
            f.write(config_content)
        
        # Создаем README с инструкциями
        readme_content = f"""
# Зеркало Telegram бота

## Настройка

1. Установите зависимости:
