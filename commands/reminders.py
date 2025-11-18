import datetime
import re
from telegram import Update
from telegram.ext import ContextTypes
import logging
from commands.utils import get_user_display_name_and_storage_name
from commands import database # Eklendi: database modülünü içe aktar

logger = logging.getLogger(__name__)

async def handle_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # save_data_callback kaldırıldı
    """
    Kullanıcının hatırlatma ayarlamasını sağlar.
    Örn: /hatirlat Buluşma saat 18:00 2024-12-31 18:00
    """
    user_id, display_name, user_name_for_storage = get_user_display_name_and_storage_name(update)

    command_args = " ".join(context.args).strip()
    
    parts = command_args.split(" ")
    
    reminder_time_str = None
    reminder_text_parts = []
    remind_at = None

    # YYYY-MM-DD HH:MM formatı için
    if len(parts) >= 2 and re.match(r'\d{4}-\d{2}-\d{2}', parts[-2]) and re.match(r'\d{2}:\d{2}', parts[-1]):
        try:
            reminder_time_str = f"{parts[-2]} {parts[-1]}"
            remind_at = datetime.datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
            reminder_text_parts = parts[:-2]
        except ValueError:
            pass

    # HH:MM formatı için (bugünkü tarihle)
    if remind_at is None and len(parts) >= 1 and re.match(r'\d{2}:\d{2}', parts[-1]):
        try:
            today = datetime.date.today()
            reminder_time_str = f"{today.strftime('%Y-%m-%d')} {parts[-1]}"
            remind_at = datetime.datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
            # Eğer saat geçmişse, bir sonraki güne ayarla
            if remind_at < datetime.datetime.now():
                 remind_at += datetime.timedelta(days=1)
            reminder_text_parts = parts[:-1]
        except ValueError:
            pass
    
    if remind_at:
        reminder_text = " ".join(reminder_text_parts)
        if not reminder_text:
            reminder_text = "Hatırlatma"
            
        database.add_reminder(user_id, reminder_text, remind_at) # Veritabanına hatırlatma ekle
        await update.message.reply_text(f"ZeaLouS: {display_name} için hatırlatma kaydedildi: '{reminder_text}' {remind_at.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"[{datetime.datetime.now()}] {user_id} için hatırlatma kaydedildi: '{reminder_text}' {remind_at.strftime('%Y-%m-%d %H:%M')}")
    else:
        await update.message.reply_text(f"ZeaLouS: {display_name}, Hata: Hatırlatma formatı yanlış. Örn: /hatirlat Buluşma saat 18:00 2024-12-31 18:00 veya /hatirlat Buluşma saat 18:00")
