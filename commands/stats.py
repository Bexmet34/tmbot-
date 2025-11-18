from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, JobQueue
import datetime
import logging
import json # JSON modülü kullanılmamış, ancak import edilmişti. İhtiyaç yoksa kaldırılabilir.

from commands import database
from commands.utils import get_user_display_name_and_storage_name, delete_message_job

logger = logging.getLogger(__name__)

async def generate_statistics_text(stat_type: str = "general", user_id: str = None) -> str:
    """
    Belirtilen istatistik tipine göre metin oluşturur.
    """
    now = datetime.datetime.now()
    stats_text = f"**📊 ZeaLouS Bot İstatistikleri ({now.strftime('%d.%m.%Y %H:%M:%S')})**\n\n" # Tarih formatı güncellendi

    try:
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
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] İstatistik metni oluşturulurken hata oluştu (Tip: {stat_type}, Kullanıcı: {user_id}): {e}", exc_info=True)
        stats_text = "**📊 ZeaLouS Bot İstatistikleri**\n\nÜzgünüm, istatistikler şu anda yüklenemiyor. Lütfen daha sonra tekrar deneyin."
    
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
    
    try:
        stats_text = await generate_statistics_text("general", user_id) # user_id de eklendi
        reply_markup = get_stats_keyboard(user_id)

        await context.bot.send_message(
            chat_id=chat_id,
            text=stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown' # Markdown desteği eklendi
        )
        logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) için istatistik mesajı gönderildi.")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) için ilk istatistik mesajı gönderilirken hata oluştu: {e}", exc_info=True)
        error_msg = f"ZeaLouS: Üzgünüm, istatistikler şu anda gösterilemiyor. Bir hata oluştu."
        sent_error = await context.bot.send_message(chat_id=chat_id, text=error_msg)
        context.job_queue.run_once(
            delete_message_job,
            7,
            data={'chat_id': sent_error.chat_id, 'message_id': sent_error.message_id}
        )


async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """İstatistik butonlarına yapılan çağrıları işler."""
    query = update.callback_query
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)

    # query.answer() çağrısı hemen yapılmalı
    await query.answer()

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
        target_user_id = user_id
    elif callback_data == "stats_refresh":
        current_text = query.message.text # Mevcut mesajın metni
        if "**📚 Genel Durum:**" in current_text:
            stat_type = "general"
        elif "**🏆 En Çok Mesaj Gönderenler:**" in current_text:
            stat_type = "top_senders"
        elif "**👤" in current_text and "Kullanıcı İstatistikleri" in current_text:
            stat_type = "my_stats"
            target_user_id = user_id
        logger.debug(f"[{datetime.datetime.now()}] İstatistik yenileme: '{stat_type}' tipiyle tekrar gösteriliyor.")

    try:
        new_stats_text = await generate_statistics_text(stat_type, target_user_id)
        new_reply_markup = get_stats_keyboard(user_id)

        # Mevcut mesajın metni ve butonlarıyla yeni metin ve butonları karşılaştır
        current_reply_markup_json = json.dumps(query.message.reply_markup.to_dict(), sort_keys=True) if query.message.reply_markup else None
        new_reply_markup_json = json.dumps(new_reply_markup.to_dict(), sort_keys=True) if new_reply_markup else None

        if query.message.text == new_stats_text and current_reply_markup_json == new_reply_markup_json:
            logger.info(f"[{datetime.datetime.now()}] İstatistikler zaten güncel. Mesaj düzenlenmedi. Kullanıcı {display_name} ({user_id})")
            # Kullanıcıya geçici bir bildirim göndermek için query.answer() daha uygun
            await query.answer("İstatistikler zaten güncel!")
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_stats_text,
                reply_markup=new_reply_markup,
                parse_mode='Markdown' # Markdown desteği eklendi
            )
            logger.info(f"[{datetime.datetime.now()}] İstatistik mesajı güncellendi: {stat_type}. Kullanıcı {display_name} ({user_id})")
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] İstatistik mesajı güncellenirken hata oluştu: {e}. Mesaj ID: {message_id}, Callback Data: {callback_data}", exc_info=True)
        error_msg = f"ZeaLouS: İstatistikler güncellenirken bir hata oluştu: {e}"
        sent_error = await context.bot.send_message(chat_id=chat_id, text=error_msg)
        context.job_queue.run_once(
            delete_message_job,
            7,
            data={'chat_id': sent_error.chat_id, 'message_id': sent_error.message_id}
        )

