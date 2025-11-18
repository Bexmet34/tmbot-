from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, JobQueue
import logging
import datetime
import re
from collections import Counter, defaultdict

# Kendi komut modüllerinizi içe aktarın
from config import BOT_TOKEN, GAME_SERVER_UTC_OFFSET_HOURS, ADMIN_IDS, MEHTER_MP3_PATH, GREETING_IMAGES_DIR
from commands.swear_filter import check_for_swears, load_forbidden_words_from_file
from commands.notes import handle_note_command as notes_handler
from commands.reminders import handle_reminder_command as reminders_handler
from commands.game_time import get_game_server_time
from commands.greetings import send_greeting_image
from commands.utils import get_user_display_name_and_storage_name, is_admin, delete_message_job
from commands import database # Eklendi: Veritabanı modülü
from commands import stats # Eklendi: İstatistik modülü

# Loglama ayarlarını yapılandırın
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Süresi dolan hatırlatıcıları kontrol eder ve kullanıcılara özel mesaj gönderir."""
    logger.debug("Running check_reminders job...")
    now = datetime.datetime.now()
    
    all_reminders_by_user = database.get_all_reminders() # Veritabanından tüm hatırlatıcıları al
    user_id_to_display_name = database.get_user_display_names() # Veritabanından kullanıcı adlarını al
    
    for user_id, reminders in all_reminders_by_user.items():
        for reminder in reminders:
            if reminder['remind_at'] <= now:
                display_name = user_id_to_display_name.get(user_id, f"Kullanıcı {user_id}")
                reminder_text = reminder['reminder_text']
                try:
                    await context.bot.send_message(chat_id=user_id, text=f"ZeaLouS: Hatırlatma: '{reminder_text}'")
                    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye hatırlatma gönderildi: '{reminder_text}'")
                    database.remove_reminder(reminder['id']) # Hatırlatma gönderildiyse veritabanından sil
                except Exception as e:
                    logger.error(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id})'ye hatırlatma gönderilirken hata oluştu: {e}. Hatırlatma ID: {reminder['id']}")
                    database.remove_reminder(reminder['id'])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot başlatıldığında gönderilecek mesaj."""
    user_id, display_name, user_name_for_storage = get_user_display_name_and_storage_name(update)
    database.update_user_info(user_id, user_name_for_storage)
    help_hint = "Komutları görmek için `/help` yazabilirsiniz."
    await update.message.reply_text(f'Merhaba {display_name}! Ben ZeaLouS, mesajlarınızı kontrol etmek ve komutlarınızı işlemek için buradayım. {help_hint}')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        user_id, display_name, user_name_for_storage = get_user_display_name_and_storage_name(update)
        message_content = update.message.text
        now = datetime.datetime.now()

        database.update_user_info(user_id, user_name_for_storage)
        
        logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) mesaj gönderdi: '{message_content}'")

        user_data = database.get_punishment_data(user_id)

        if user_data['is_muted'] and user_data['mute_until'] and now > user_data['mute_until']:
            # Mute süresi dolduğunda gönderilen mesaj kalıcı kalabilir
            await update.message.reply_text(f"ZeaLouS: {display_name}, cezanız sona erdi. Tekrar mesaj atabilirsiniz.")
            
            if user_data['next_mute_type'] == '1_hr_served':
                database.clear_user_punishments(user_id)
                user_data = database.get_punishment_data(user_id)
                logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) için tüm cezalar sıfırlandı.")
            else:
                user_data['is_muted'] = False
                user_data['mute_until'] = None
                user_data['strike_count'] = 0
                database.save_punishment_data(user_id, user_data)
            
        if user_data['is_muted']:
            await update.message.delete() # Susturulmuş kullanıcının mesajını sil
            remaining_time = user_data['mute_until'] - now
            minutes, seconds = divmod(remaining_time.seconds, 60)
            hours, minutes = divmod(minutes, 60)
            
            mute_status_message = f"ZeaLouS: {display_name}, şu anda susturulmuş durumdasınız."
            if remaining_time.days > 0:
                mute_status_message += f" Cezanız {remaining_time.days} gün, {hours} saat, {minutes} dakika daha devam ediyor."
            elif hours > 0:
                mute_status_message += f" Cezanız {hours} saat, {minutes} dakika daha devam ediyor."
            else:
                mute_status_message += f" Cezanız {minutes} dakika, {seconds} saniye daha devam ediyor."
            mute_status_message += " Bu mesaj 5 saniye sonra silinecektir." # Geçici mesaj olduğunu belirt

            try:
                # Durum mesajını gruba gönder
                sent_message = await context.bot.send_message(chat_id=update.message.chat_id, text=mute_status_message)
                # Mesajı 5 saniye sonra silmek için zamanla
                context.job_queue.run_once(
                    delete_message_job, # commands.utils.delete_message_job kullanıldı
                    5, # 5 saniye gecikme
                    data={'chat_id': sent_message.chat_id, 'message_id': sent_message.message_id}
                )
                logger.info(f"[{now}] Kullanıcı {display_name} ({user_id}) susturulmuşken mesaj attı. Geçici bildirim gönderildi ve silinmesi zamanlandı.")
            except Exception as e:
                logger.error(f"[{now}] Kullanıcı {display_name} ({user_id}) susturulmuşken bildirim gönderilirken/silinirken hata oluştu: {e}")
            return

        if check_for_swears(user_id, message_content):
            user_data['strike_count'] += 1
            current_strike_count = user_data['strike_count']
            
            # Yasaklı kelime tespit edildiğinde gönderilen mesajı yakala ve silinmesini zamanla
            warning_message_text = (
                f'ZeaLouS: Mesajınızda yasaklı kelime tespit edildi {display_name}.'
                f'\nYasaklı kelime sayınız: {current_strike_count}'
            )
            sent_warning_message = await update.message.reply_text(warning_message_text)
            context.job_queue.run_once(
                delete_message_job, # commands.utils.delete_message_job kullanıldı
                7, # 7 saniye sonra silinecek
                data={'chat_id': sent_warning_message.chat_id, 'message_id': sent_warning_message.message_id}
            )
            await update.message.delete()
            logger.info(f"[{now}] Kullanıcı {display_name} ({user_id}) {current_strike_count} ihlale ulaştı. Bir sonraki susturma tipi: {user_data['next_mute_type']}. Uyarı mesajı silinmek üzere zamanlandı.")


            if current_strike_count >= 3:
                mute_duration = None

                if user_data['next_mute_type'] == '5_min':
                    mute_duration = datetime.timedelta(minutes=5)
                    user_data['next_mute_type'] = '1_hr'
                elif user_data['next_mute_type'] == '1_hr':
                    mute_duration = datetime.timedelta(hours=1)
                    user_data['next_mute_type'] = '1_hr_served'

                if mute_duration:
                    user_data['is_muted'] = True
                    user_data['mute_until'] = now + mute_duration
                    user_data['total_mutes_served'] += 1
                    user_data['strike_count'] = 0

                    logger.info(f"[{now}] Kullanıcı {display_name} ({user_id}) için {mute_duration} süreli susturma uygulandı. Yeni susturma tipi: {user_data['next_mute_type']}. İhlaller sıfırlandı.")

                    # Ceza uygulandı mesajını yakala ve silinmesini zamanla
                    punishment_message_text = f"ZeaLouS: {display_name}, ceza uygulandı!"
                    sent_punishment_message = await update.message.reply_text(punishment_message_text)
                    context.job_queue.run_once(
                        delete_message_job, # commands.utils.delete_message_job kullanıldı
                        7, # 7 saniye sonra silinecek
                        data={'chat_id': sent_punishment_message.chat_id, 'message_id': sent_punishment_message.message_id}
                    )

                    try:
                        # Kullanıcıya özel detaylı ceza bildirimi gönder (bu mesaj kalıcı kalabilir)
                        await context.bot.send_message(chat_id=user_id, text=f"ZeaLouS: Ceza aldınız. Süre: {mute_duration}. Kuralları gözden geçirin: /rules")
                    except Exception as e:
                        logger.warning(f"[{now}] Kullanıcı {display_name} ({user_id})'ye özel ceza mesajı gönderilirken hata oluştu: {e}")

                    database.save_punishment_data(user_id, user_data)
                    return
            
            database.save_punishment_data(user_id, user_data)
            return

        database.add_message_record(user_id)


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await notes_handler(update, context)


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reminders_handler(update, context)


async def statistics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detaylı istatistikleri butonlarla birlikte gönderir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    chat_id = update.message.chat_id
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) /istatistik komutunu kullandı. Detaylı istatistikler gönderiliyor.")
    await stats.send_statistics_message(update, context, chat_id) # Yeni stats modülünü kullan


async def game_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oyun sunucusunun saatini gösterir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    game_time = get_game_server_time()
    sent_message = await update.message.reply_text(f"ZeaLouS: {game_time}")
    context.job_queue.run_once(
        delete_message_job,
        7, # 7 saniye sonra silinecek
        data={'chat_id': sent_message.chat_id, 'message_id': sent_message.message_id}
    )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {get_user_display_name_and_storage_name(update)[1]} /oyunsaati komutunu kullandı. Yanıt mesajı silinmek üzere zamanlandı.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)

    help_text = (
        f"Merhaba {display_name}! İşte kullanabileceğiniz komutlar:\n\n"
        
        "**📚 Genel Komutlar:**\n"
        "🌐 /start - Botu başlatır ve bir karşılama mesajı gönderir.\n"
        "❓ /help - Bu yardım listesini gösterir.\n"
        "📜 /rules - Botun ceza sistemi kurallarını açıklar.\n\n"
        
        "**📝 Kişisel Araçlar:**\n"
        "📝 /not <metin> - Kendinize özel bir not kaydeder.\n"
        "⏰ /hatirlat <metin> [tarih] saat - Belirttiğiniz zamanda size bir hatırlatma gönderir.\n"
        "📊 /istatistik - Sohbet odasının detaylı istatistiklerini gösterir.\n\n"
        
        "**🎮 Eğlence ve Selamlamalar:**\n"
        "🕒 /oyunsaati - Oyun sunucusunun saatini gösterir.\n"
        "👋 /hello - 'Merhaba' görseli gönderir.\n"
        "☀️ /goodmorning - 'Günaydın' görseli gönderir.\n"
        "😴 /goodnight - 'İyi Geceler' görseli gönderir.\n"
        "🎉 /welcome - 'Hoş Geldin' görseli gönderir.\n"
        "🥁 /mehter - Bir Mehter Marşı MP3'ü çalar (çalmak için dokunmanız gerekir).\n\n"
    )
    
    # Yönetici komutlarını sadece adminlere göster
    if is_admin(user_id):
        help_text += (
            "**🛡️ Yönetici Komutları:**\n"
            "⚠️ /cezatemizle `[kullanıcı_id_veya_adı]` - Belirtilen kullanıcının tüm cezalarını sıfırlar.\n" # Burası düzeltildi
        )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rules_text = (
        "ZeaLouS Ceza Sistemi Kuralları:\n"
        "1. Yasaklı kelimede uyarı.\n"
        "2. 3 ihlalde 5 dakika mute.\n"
        "3. Yine 3 ihlalde 1 saat mute.\n"
        "4. 1 saatlik ceza sonunda tüm sayaçlar sıfırlanır."
    )
    await update.message.reply_text(f"ZeaLouS:\n{rules_text}")


async def hello_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'Merhaba' görseli gönderir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    sent_photo_message = await send_greeting_image(update, context, 'hello.png', display_name, user_id, context.job_queue)
    if sent_photo_message: # Eğer görsel başarıyla gönderildiyse, onu silinmek üzere zamanla
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_photo_message.chat_id, 'message_id': sent_photo_message.message_id}
        )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} /hello komutunu kullandı. Görsel yanıtı silinmek üzere zamanlandı (eğer gönderildiyse).")


async def goodmorning_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'Günaydın' görseli gönderir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    sent_photo_message = await send_greeting_image(update, context, 'goodmorning.png', display_name, user_id, context.job_queue)
    if sent_photo_message:
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_photo_message.chat_id, 'message_id': sent_photo_message.message_id}
        )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} /goodmorning komutunu kullandı. Görsel yanıtı silinmek üzere zamanlandı (eğer gönderildiyse).")


async def goodnight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'İyi Geceler' görseli gönderir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    sent_photo_message = await send_greeting_image(update, context, 'goodnight.png', display_name, user_id, context.job_queue)
    if sent_photo_message:
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_photo_message.chat_id, 'message_id': sent_photo_message.message_id}
        )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} /goodnight komutunu kullandı. Görsel yanıtı silinmek üzere zamanlandı (eğer gönderildiyse).")


async def welcome_command_svg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'Hoş Geldin' görseli gönderir ve komut mesajını siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    caption = f"ZeaLouS: {display_name}, topluluğa hoş geldin!"
    sent_photo_message = await send_greeting_image(update, context, 'welcome.png', display_name, user_id, context.job_queue, caption=caption)
    if sent_photo_message:
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_photo_message.chat_id, 'message_id': sent_photo_message.message_id}
        )
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} /welcome komutunu kullandı. Görsel yanıtı silinmek üzere zamanlandı (eğer gönderildiyse).")


# ✔ KOMUT ADI SADECE BURADA DEĞİŞTİRİLDİ
async def clear_punishments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)

    if not is_admin(user_id):
        await update.message.reply_text(f"ZeaLouS: {display_name}, bu komutu kullanamazsınız.")
        return

    if not context.args:
        await update.message.reply_text(f"ZeaLouS: {display_name}, kullanıcı ID veya username belirtmeniz gerekir. Örn: `/cezatemizle 12345/username`")
        return

    target_user_id = context.args[0]
    target_display_name = database.get_user_display_names().get(target_user_id, f"Kullanıcı {target_user_id}")

    database.clear_user_punishments(target_user_id)
    await update.message.reply_text(f"ZeaLouS: {display_name}, {target_display_name} kullanıcısının tüm cezaları temizlendi.")


async def mehter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mehter Marşı MP3'ünü gönderir, komut mesajını ve gönderilen sesi siler."""
    await update.message.delete() # Kullanıcının komut mesajını sil
    chat_id = update.message.chat_id
    user_id, display_name, _ = get_user_display_name_and_storage_name(update)
    logger.info(f"[{datetime.datetime.now()}] Kullanıcı {display_name} ({user_id}) /mehter komutunu kullandı.")
    
    try:
        with open(MEHTER_MP3_PATH, 'rb') as audio_file:
            sent_audio_message = await context.bot.send_audio(chat_id=chat_id, audio=audio_file, caption="ZeaLouS: Mehter Marşı çalıyor!")
            context.job_queue.run_once(
                delete_message_job,
                7, # 7 saniye sonra silinecek
                data={'chat_id': sent_audio_message.chat_id, 'message_id': sent_audio_message.message_id}
            )
        logger.info(f"[{datetime.datetime.now()}] Mehter Marşı '{MEHTER_MP3_PATH}' başarıyla gönderildi ve silinmek üzere zamanlandı.")
    except FileNotFoundError:
        logger.error(f"[{datetime.datetime.now()}] Mehter Marşı dosyası bulunamadı: {MEHTER_MP3_PATH}")
        sent_error_message = await update.message.reply_text("ZeaLouS: Mehter Marşı dosyası bulunamadı.")
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_error_message.chat_id, 'message_id': sent_error_message.message_id}
        )
    except Exception as e:
        logger.error(f"[{datetime.datetime.now()}] Mehter Marşı gönderilirken hata oluştu: {e}")
        sent_error_message = await update.message.reply_text("ZeaLouS: Mehter Marşı gönderilirken bir hata oluştu.")
        context.job_queue.run_once(
            delete_message_job,
            7, # 7 saniye sonra silinecek
            data={'chat_id': sent_error_message.chat_id, 'message_id': sent_error_message.message_id}
        )


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    database.create_tables()
    load_forbidden_words_from_file()

    application.job_queue.run_repeating(check_reminders, interval=60, first=0)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("not", notes_command))
    application.add_handler(CommandHandler("hatirlat", reminders_command))
    application.add_handler(CommandHandler("istatistik", statistics_command)) # Değiştirildi
    application.add_handler(CommandHandler("oyunsaati", game_time_command))
    application.add_handler(CommandHandler("hello", hello_command))
    application.add_handler(CommandHandler("goodmorning", goodmorning_command))
    application.add_handler(CommandHandler("goodnight", goodnight_command))
    application.add_handler(CommandHandler("welcome", welcome_command_svg))

    application.add_handler(CommandHandler("cezatemizle", clear_punishments_command))
    application.add_handler(CommandHandler("mehter", mehter_command))

    # Yeni: İstatistik butonları için CallbackQueryHandler eklendi
    application.add_handler(CallbackQueryHandler(stats.handle_stats_callback, pattern='^stats_'))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot başlatılıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
