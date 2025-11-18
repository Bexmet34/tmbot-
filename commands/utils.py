import datetime
import re
from telegram import Update
from config import ADMIN_IDS # ADMIN_IDS'i config'den içe aktar
from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__) # utils modülü için de loglama yapılandırın

def get_user_display_name_and_storage_name(update: Update) -> tuple[str, str, str]:
    """
    Kullanıcının Telegram'da görüntülenecek adını ve depolama için kullanılacak adını döndürür.
    Anonim yöneticiler ve kullanıcı adı/ilk adı olmayan durumlar için düzeltme yapar.
    Returns: (user_id, display_name_for_reply, user_name_for_storage)
    """
    effective_user = update.effective_user
    user_id = str(effective_user.id) # Her zaman effective_user'ın ID'sini kullan

    display_name_for_reply = ""
    user_name_for_storage = ""

    # 1. Öncelik: Mesajda özel yazar imzası (anonim yöneticiler için) varsa
    if update.message.author_signature:
        display_name_for_reply = update.message.author_signature
        user_name_for_storage = update.message.author_signature
    # 2. Öncelik: effective_user'ın kullanıcı adı varsa ve generic bot adı değilse
    elif effective_user.username and effective_user.username.lower() not in ["groupanonymousbot", "channel_bot"]: # channel_bot gibi isimleri de filtrele
        display_name_for_reply = f"@{effective_user.username}"
        user_name_for_storage = effective_user.username
    # 3. Öncelik: effective_user'ın ilk adı varsa
    elif effective_user.first_name:
        display_name_for_reply = effective_user.first_name
        user_name_for_storage = effective_user.first_name
    # 4. Öncelik: effective_user'ın soyadı varsa
    elif effective_user.last_name:
        display_name_for_reply = effective_user.last_name
        user_name_for_storage = effective_user.last_name
    # 5. Öncelik: Mesaj bir kanaldan/gruptan geliyorsa ve sender_chat.title varsa
    elif update.message.sender_chat and update.message.sender_chat.title:
        # Sadece "Group" gibi jenerik bir isim olmadığından emin ol
        if update.message.sender_chat.title.lower() != "group":
            display_name_for_reply = update.message.sender_chat.title
            user_name_for_storage = update.message.sender_chat.title
        else:
            # "Group" ise daha genel bir ifadeye düş
            display_name_for_reply = "Anonim Üye" # Veya "Sohbet Üyesi"
            user_name_for_storage = f"Anonim Üye ({user_id})"
    # 6. Son Çare: Hiçbir ad bulunamazsa
    else:
        display_name_for_reply = f"Kullanıcı {user_id}"
        user_name_for_storage = f"Kullanıcı {user_id}"

    # Eğer hala "GroupAnonymousBot" gibi bir isim geldiyse, bu büyük ihtimalle bir hatadır
    # ve daha genel bir isme düşmeliyiz.
    if "groupanonymousbot" in display_name_for_reply.lower():
        display_name_for_reply = "Anonim Yönetici"
        user_name_for_storage = f"Anonim Yönetici ({user_id})"

    return user_id, display_name_for_reply, user_name_for_storage

def is_admin(user_id: str) -> bool:
    """Verilen user_id'nin bir yönetici olup olmadığını kontrol eder."""
    return user_id in ADMIN_IDS

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
