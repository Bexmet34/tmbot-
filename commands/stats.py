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
    stats_text = f"**📊 ZeaLouS Bot İstatistikleri ({now.strftime('%H:%M:%S')})**\n\n"

    if stat_type == "general":
        total_messages = database.get_total_messages_count()
        total_users = database.get_total_unique_users_count()
        active_users_24h = database.get_active_users_last_24_hours()

        stats_text += (
            f"**📚 Genel Durum:**\n"
            f"Toplam Mesaj Sayısı: {total_messages}\n"
            f"Toplam Benzersiz Kullanıcı: {total_users}\n"
            f"Son 24 Saatte Aktif Kullanıcı: {active_users_24h}\n"
        )
    elif stat_type == "top_senders":
        top_senders = database.get_top_message_senders(limit=10) # İlk 10 mesajcı
        stats_text += "**🏆 En Çok Mesaj Gönderenler:**\n"
        if top_senders:
            for i, (display_name, count) in enumerate(top_senders):
                stats_text += f"{i+1}. {display_name}: {count} mesaj\n"
        else:
            stats_text += "Henüz mesaj gönderen yok.\n"
    elif stat_type == "my_stats" and user_id:
        user_stats = database.get_user_stats(user_id)
        stats_text += (
            f"**👤 {user_stats['display_name']} Kullanıcı İstatistikleri:**\n"
            f"Gönderilen Mesaj: {user_stats['message_count']}\n"
            f"Mevcut İhlal Sayısı: {user_stats['strike_count']}\n"
            f"Susturulmuş mu?: {'Evet' if user_stats['is_muted'] else 'Hayır'}\n"
        )
        if user_stats['is_muted'] and user_stats['mute_until']:
            mute_until_str = user_stats['mute_until']
            mute_until_dt = None
            try:
                mute_until_dt = datetime.datetime.strptime(mute_until_str, '%Y-%m-%d %H:%M:%S.%f')
            except (ValueError, TypeError):
                try:
                    mute_until_dt = datetime.datetime.strptime(mute_until_str, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pass # Eğer farklı bir format gelirse burada hata yakalanır

            if mute_until_dt:
                stats_text += f"Susturma Bitiş Tarihi: {mute_until_dt.strftime('%d.%m.%Y %H:%M:%S')}\n"
            else:
                stats_text += f"Susturma Bitiş Tarihi: Bilinmiyor ({mute_until_str})\n" # Hata olursa stringi göster
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
    
    stats_text = await generate_statistics_text("general")
    reply_markup = get_stats_keyboard(user_id)

    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text=stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    # Mesajı bir süre sonra silinmek üzere zamanlamaya gerek yok, butonlarla etkileşim bekleniyor.
    # Ancak orijinal komut mesajı (yani `/istatistik` yazılan mesaj) main.py'de silinmelidir.
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
        target_user_id = callback_data.split('_')[-1] # Kullanıcının kendi ID'si
    elif callback_data == "stats_refresh":
        # Yenileme için, şu anki gösterilen istatistik tipini koru (eğer mümkünse)
        # Basitçe genel istatistikleri yenileyelim veya daha karmaşık bir state yönetimi eklenebilir.
        stat_type = "general" # Şimdilik yenileme, genel istatistikleri gösterir
        
        # Eğer önceki mesajda hangi stat türünün gösterildiği bilgisi olsaydı, onu kullanabilirdik.
        # Örneğin, callback data'ya 'stats_refresh_current_type' gibi bir şey ekleyerek.
        # Şimdilik, refresh her zaman genel istatistikleri gösterir.
        logger.debug(f"[{datetime.datetime.now()}] İstatistik yenileme: Genel istatistikler tekrar gösteriliyor.")


    new_stats_text = await generate_statistics_text(stat_type, target_user_id)
    new_reply_markup = get_stats_keyboard(user_id)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_stats_text,
            reply_markup=new_reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"[{datetime.datetime.now()}] İstatistik mesajı güncellendi: {stat_type}.")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] İstatistik mesajı güncellenirken hata oluştu: {e}")
        # Hata mesajı gönderilebilir, ama buton etkileşiminde genellikle edit_message_text hatası beklenmez.

