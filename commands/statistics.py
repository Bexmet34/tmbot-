import datetime
from collections import Counter
from commands import database # Eklendi: database modülünü içe aktar

def _format_top_users(counts: Counter, display_names: dict, period_name: str, limit: int = 3) -> str:
    """Belirli bir dönem için en çok mesaj atan kullanıcıları biçimlendirir."""
    if not counts:
        return f"    {period_name}: Henüz mesaj yok.\n"
    
    top_users_str = f"    {period_name}:\n"
    for i, (user_id, count) in enumerate(counts.most_common(limit)):
        display_name = display_names.get(user_id, f"Bilinmeyen Kullanıcı ({user_id})")
        top_users_str += f"        {i+1}. @{display_name} ({count} mesaj)\n"
    return top_users_str

def get_statistics(current_user_id: str) -> str: # Parametreler güncellendi
    """
    Günlük, haftalık ve aylık "en çok mesaj atan kişi" istatistiklerini döndürür.
    """
    # Verileri veritabanından al
    message_records = database.get_message_records_for_stats()
    user_id_to_display_name = database.get_user_display_names()

    if not message_records:
        return "Henüz istatistik mevcut değil."

    now = datetime.datetime.now()
    stats_message = "--- Mesaj İstatistikleri ---\n"

    # Günlük (son 24 saat)
    daily_records = [
        record for record in message_records 
        if now - record['timestamp'] < datetime.timedelta(days=1)
    ]
    daily_counts = Counter(record['user_id'] for record in daily_records)
    stats_message += _format_top_users(daily_counts, user_id_to_display_name, "Günlük En Çok Mesaj Atanlar")

    # Haftalık (son 7 gün)
    weekly_records = [
        record for record in message_records 
        if now - record['timestamp'] < datetime.timedelta(days=7)
    ]
    weekly_counts = Counter(record['user_id'] for record in weekly_records)
    stats_message += _format_top_users(weekly_counts, user_id_to_display_name, "\nHaftalık En Çok Mesaj Atanlar")

    # Aylık (son 30 gün)
    monthly_records = [
        record for record in message_records 
        if now - record['timestamp'] < datetime.timedelta(days=30)
    ]
    monthly_counts = Counter(record['user_id'] for record in monthly_records)
    stats_message += _format_top_users(monthly_counts, user_id_to_display_name, "\nAylık En Çok Mesaj Atanlar")

    # Kullanıcının Genel Sıralaması
    overall_counts = Counter(record['user_id'] for record in message_records)
    user_rank_str = "Bulunamadı"
    user_message_count = overall_counts.get(current_user_id, 0)
    
    if user_message_count > 0:
        sorted_users = sorted(overall_counts.items(), key=lambda item: item[1], reverse=True)
        # Sadece mevcut kullanıcının sıralamasını bulmak için döngü
        for i, (user_id, count) in enumerate(sorted_users):
            if user_id == current_user_id:
                display_name = user_id_to_display_name.get(current_user_id, "Sen")
                user_rank_str = f"{i+1}. sırada (@{display_name}, {count} mesaj)"
                break
    
    stats_message += f"\n-- Senin Sıralaman --\n- {user_rank_str}\n"
    
    return stats_message
