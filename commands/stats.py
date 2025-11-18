from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, JobQueue
import datetime
import logging

from commands import database
from commands.utils import get_user_display_name_and_storage_name, delete_message_job

logger = logging.getLogger(__name__)

async def generate_statistics_text(stat_type: str = "general", user_id: str = None) -> str:
    """
    Belirtilen istatistik tipine göre metin oluşturur.
    """
    now = datetime.datetime.now()
    stats_text = f"**📊 ZeaLouS Bot İstatistikleri ({now.strftime('%d.%m.%Y %H:%M:%S')})**\n\n" # Tarih formatı güncellendi

    if stat_type == "general":
        total_messages = database.get_total_messages_count()
        total_users = database.get_total_unique_users_count()
        active_users_24h = database.get_active_users_last_24_hours()

        stats_text += (
            f"**📚 Genel Durum:**\n"
            f"Toplam Mesaj Sayısı: `{total_messages}`\n" # Inline kod olarak biçimlendirildi
            f"Toplam Benzersiz Kullanıcı: `{total_users}`\n" # Inline kod olarak biçimlendirildi
            f"Son 24 Saatte Aktif Kullanıcı: `{active_users_24h}`\n" # Inline kod olarak biçimlendirildi
        )
    elif stat_type == "top_senders":
        top_senders = database.get_top_message_senders(limit=10) # İlk 10 mesajcı
        stats_text += "**🏆 En Çok Mesaj Gönderenler:**\n"
        if top_senders:
            for i, (display_name, count) in enumerate(top_senders):
                stats_text += f"`{i+1}.` {display_name}: `{count}` mesaj\n" # Inline kod olarak biçimlendirildi
        else:
            stats_text += "Henüz mesaj gönderen yok.\n"
    elif stat_type == "my_stats" and user_id:
        user_stats = database.get_user_stats(user_id)
        stats_text += (
            f"**👤 {user_stats['display_name']} Kullanıcı İstatistikleri:**\n"
            f"Gönderilen Mesaj: `{user_stats['message_count']}`\n" # Inline kod olarak biçimlendirildi
            f"Mevcut İhlal Sayısı: `{user_stats['strike_count']}`\n" # Inline kod olarak biçimlendirildi
            f"Susturulmuş mu?: `{'Evet' if user_stats['is_muted'] else 'Hayır'}`\n" # Inline kod olarak biçimlendirildi
        )
        if user_stats['is_muted'] and user_stats['mute_until']:
            mute_until_str = user_stats['mute_until']
            mute_until_dt = None
            
            if isinstance(mute_until_str, datetime.datetime): # Zaten datetime objesi ise
                mute_until_dt = mute_until_str
            elif isinstance(mute_until_str, str): # String ise ayrıştırmayı dene
                try:
                    mute_until_dt = datetime.datetime.strptime(mute_until_str, '%Y-%m-%d %H:%M:%S.%f')
                except (ValueError, TypeError):
                    try:
                        mute_until_dt = datetime.datetime.strptime(mute_until_str, '%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass # Eğer farklı bir format gelirse burada hata yakalanır

            if mute_until_dt:
                stats_text += f"Susturma Bitiş Tarihi: `{mute_until_dt.strftime('%d.%m.%Y %H:%M:%S')}`\n" # Inline kod olarak biçimlendirildi
            else:
                stats_text += f"Susturma Bitiş Tarihi: `Bilinmiyor ({mute_until_str})`\n" # Hata olursa stringi göster
    else:
        stats_text += "Geçersiz istatistik tipi veya kullanıcı ID eksik.\n"
    
    return stats_text

def get_stats_keyboard(user_id: str) -> InlineKeyboardMarkup:
    """İstatistikler için inline klavye oluşturur."""
    keyboard = [
        [
            InlineKeyboardButton("Genel İstatistikler", callback_data="stats_general"),
            InlineKeyboardButton("En Çok Mesajcılar", callback_data="stats_top_senders")
        ],
        [
            InlineKeyboardButton("Benim İstatistiklerim", callback_data=f"stats_my_stats_{user_id}"),
            InlineKeyboardButton("Yenile", callback_data="stats_refresh")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_statistics_message(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """İlk istatistik mesajını gönderir."""
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    
    stats_text = await generate_statistics_text("general", user_id) # user_id de eklendi
    reply_markup = get_stats_keyboard(user_id)

    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text=stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown' # Markdown desteği eklendi
    )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) için istatistik mesajı gönderildi.")


async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """İstatistik butonlarına yapılan çağrıları işler."""
    query = update.callback_query
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)

    await query.answer() # Butona basıldığını Telegram'a bildir

    callback_data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) istatistik butonu {callback_data} ile etkileşimde bulundu.")

    stat_type = "general"
    target_user_id = None

    if callback_data == "stats_general":
        stat_type = "general"
    elif callback_data == "stats_top_senders":
        stat_type = "top_senders"
    elif callback_data.startswith("stats_my_stats_"):
        stat_type = "my_stats"
        target_user_id = user_id # callback_data'dan değil, mevcut user_id'den alıyoruz. Güvenlik için daha iyi.
    elif callback_data == "stats_refresh":
        # Yenileme butonuna basıldığında, o anki istatistik tipini koruyarak yenile.
        # Örneğin, mevcut mesajın ilk satırından hangi tip olduğunu anlamaya çalışabiliriz
        # veya callback_data'ya daha fazla bilgi ekleyebiliriz.
        # Şimdilik, sadece mevcut mesajın içeriğini kullanarak istatistik tipini yeniden belirleyelim.
        current_text = query.message.text
        if "Genel Durum" in current_text:
            stat_type = "general"
        elif "En Çok Mesaj Gönderenler" in current_text:
            stat_type = "top_senders"
        elif "Kullanıcı İstatistikleri" in current_text:
            stat_type = "my_stats"
            target_user_id = user_id # Kendi istatistiklerini yenile
        logger.debug(f"[{datetime.datetime.now()}] İstatistik yenileme: '{stat_type}' tipiyle tekrar gösteriliyor.")


    new_stats_text = await generate_statistics_text(stat_type, target_user_id)
    new_reply_markup = get_stats_keyboard(user_id)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_stats_text,
            reply_markup=new_reply_markup,
            parse_mode='Markdown' # Markdown desteği eklendi
        )
        logger.info(f"[{datetime.datetime.now()}] İstatistik mesajı güncellendi: {stat_type}.")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] İstatistik mesajı güncellenirken hata oluştu: {e}. Hata: {query.message.text}")
        # Hata mesajı gönderilebilir, ama buton etkileşiminde genellikle edit_message_text hatası beklenmez.
        # Geçici bir hata mesajı gönderip silebiliriz.
        error_msg = f"ZeaLouS: İstatistikler güncellenirken bir hata oluştu: {e}"
        sent_error = await context.bot.send_message(chat_id=chat_id, text=error_msg)
        context.job_queue.run_once(
            delete_message_job,
            7,
            data={'chat_id': sent_error.chat_id, 'message_id': sent_error.message_id}
        )

