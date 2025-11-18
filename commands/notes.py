import datetime
from telegram import Update
from telegram.ext import ContextTypes
import logging
from commands.utils import get_user_display_name_and_storage_name
from commands import database # Eklendi: database modülünü içe aktar

logger = logging.getLogger(__name__)

async def handle_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # save_data_callback kaldırıldı
    """
    Kullanıcının not almasını sağlar.
    Örn: /not al Buluşma saat 18:00
    """
    user_id, display_name, user_name_for_storage = get_user_display_name_and_storage_name(update)
    
    command_args = " ".join(context.args).strip()

    if not command_args:
        await update.message.reply_text(f"ZeaLouS: {display_name}, Hata: Kaydedilecek bir not belirtmediniz. Örn: /not Toplantı saat 10:00")
        return

    database.add_note(user_id, command_args) # Veritabanına not ekle
    await update.message.reply_text(f"ZeaLouS: {display_name}, Notunuz kaydedildi: '{command_args}'")
    logger.info(f"[{datetime.datetime.now()}] {user_id} için not kaydedildi: '{command_args}'")
