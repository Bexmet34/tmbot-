import datetime
from telegram import Update
from telegram.ext import ContextTypes
import os
import logging
import io
from typing import Optional
from commands.utils import get_user_display_name_and_storage_name # Güncellendi: Ortak yardımcı fonksiyonu içe aktar

logger = logging.getLogger(__name__)

# Görsel dosyalarının bulunduğu dizin
IMAGE_DIR = r'c:\Users\Casper\Desktop\Yeni klasör\images'

async def send_greeting_image(update: Update, context: ContextTypes.DEFAULT_TYPE, image_filename: str, display_name: str, user_id: str, caption: Optional[str] = None):
    """
    Belirtilen görsel dosyasını (PNG veya JPG olması beklenir) bir Telegram fotoğrafı olarak gönderir.
    Eğer 'caption' belirtilirse, bu başlık fotoğrafın altına eklenir.
    """
    image_path = os.path.join(IMAGE_DIR, image_filename)

    if not os.path.exists(image_path):
        logger.error(f"[{datetime.datetime.now()}] Görsel dosyası bulunamadı: {image_path}")
        await update.message.reply_text(f"ZeaLouS: {display_name}, üzgünüm, selamlama görselini bulamadım.")
        return

    try:
        with open(image_path, 'rb') as f:
            # Sadece caption None değilse gönder
            if caption:
                await update.message.reply_photo(
                    photo=f,
                    caption=caption
                )
            else:
                await update.message.reply_photo(photo=f)
        logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye '{image_filename}' gönderildi.")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye '{image_filename}' gönderilirken hata oluştu: {e}")
        await update.message.reply_text(f"ZeaLouS: {display_name}, üzgünüm, selamlama görselini gönderirken bir hata oluştu: {e}")

