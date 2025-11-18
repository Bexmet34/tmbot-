import datetime
from telegram import Update
from telegram.ext import ContextTypes
import os
import logging
from config import GREETING_IMAGES_DIR # Yeni eklenen görsel dizinini içe aktarın
from commands.utils import delete_message_job # delete_message_job'u utils'ten içe aktarın

logger = logging.getLogger(__name__)

async def send_greeting_image(update: Update, context: ContextTypes.DEFAULT_TYPE, image_filename: str, display_name: str, user_id: int, caption: str = None) -> None:
    """Belirtilen selamlama görselini gönderir veya bulunamazsa geçici bir hata mesajı verir."""
    image_path = os.path.join(GREETING_IMAGES_DIR, image_filename)
    chat_id = update.message.chat_id

    if caption is None:
        if image_filename == 'hello.png':
            caption = f"ZeaLouS: Merhaba, {display_name}!"
        elif image_filename == 'goodmorning.png':
            caption = f"ZeaLouS: Günaydın, {display_name}!"
        elif image_filename == 'goodnight.png':
            caption = f"ZeaLouS: İyi Geceler, {display_name}!"
        elif image_filename == 'welcome.png':
            caption = f"ZeaLouS: {display_name}, topluluğa hoş geldin!"
        else:
            caption = f"ZeaLouS: Bir görsel gönderiliyor, {display_name}!"


    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Görsel dosyası bulunamadı: {image_path}")

        with open(image_path, 'rb') as image_file:
            await context.bot.send_photo(chat_id=chat_id, photo=image_file, caption=caption)
        logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye '{image_filename}' gönderildi.")
    except FileNotFoundError:
        error_message_text = f"ZeaLouS: {display_name}, üzgünüm, selamlama görselini bulamadım: '{image_filename}'"
        sent_error_message = await update.message.reply_text(error_message_text)
        context.job_queue.run_once(
            delete_message_job,
            5, # 5 saniye sonra silinecek
            data={'chat_id': sent_error_message.chat_id, 'message_id': sent_error_message.message_id}
        )
        logger.error(f"[{datetime.datetime.now()}] Görsel '{image_filename}' bulunamadı. Kullanıcıya hata mesajı gönderildi ve silinmesi zamanlandı.")
    except Exception as e:
        error_message_text = f"ZeaLouS: {display_name}, görsel gönderilirken bir hata oluştu: {e}"
        sent_error_message = await update.message.reply_text(error_message_text)
        context.job_queue.run_once(
            delete_message_job,
            5, # 5 saniye sonra silinecek
            data={'chat_id': sent_error_message.chat_id, 'message_id': sent_error_message.message_id}
        )
        logger.error(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye görsel '{image_filename}' gönderilirken hata oluştu: {e}. Hata mesajı silinmek üzere zamanlandı.")

