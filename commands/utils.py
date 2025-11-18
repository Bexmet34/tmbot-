from telegram import Update
from telegram.ext import ContextTypes
import logging
import datetime
from config import ADMIN_IDS # ADMIN_IDS config.py dosyasından alınır

logger = logging.getLogger(__name__) # utils modülü için de loglama yapılandırın

def get_user_display_name_and_storage_name(update: Update):
    """Kullanıcının görünen adını ve depolama için kullanılacak adını döndürür."""
    user = update.effective_user
    display_name = user.first_name
    if user.last_name:
        display_name += f" {user.last_name}"
    user_name_for_storage = user.username if user.username else str(user.id)
    return str(user.id), display_name, user_name_for_storage

def is_admin(user_id: int | str) -> bool:
    """Belirtilen kullanıcının yönetici olup olmadığını kontrol eder."""
    return str(user_id) in ADMIN_IDS

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Belirli bir mesajı gecikmeli olarak silmek için zamanlanmış iş."""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    message_id = job_data['message_id']
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.debug(f"[{datetime.datetime.now()}] Mesaj {message_id} (sohbet {chat_id}) başarıyla silindi.")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] Mesaj {message_id} (sohbet {chat_id}) silinirken hata oluştu: {e}")
