import sqlite3
import datetime
from config import DB_PATH # DB_PATH'i config.py dosyasından içe aktarıyoruz

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def _connect_db():
    """Veritabanına bağlanır ve bağlantı nesnesini döndürür."""
    return sqlite3.connect(DB_PATH)

def create_tables():
    """Gerekli tüm veritabanı tablolarını oluşturur."""
    conn = _connect_db()
    cursor = conn.cursor()

    # Kullanıcı bilgileri tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
    ''')

    # Mevcut 'users' tablosu şemasını güncelle (sütunlar yoksa ekle)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN first_seen TEXT")
    except sqlite3.OperationalError:
        pass # Sütun zaten var
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    except sqlite3.OperationalError:
        pass # Sütun zaten var

    # Mesaj log tablosu (eski message_stats yerine)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Ceza bilgileri tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS punishments (
            user_id TEXT PRIMARY KEY,
            strike_count INTEGER DEFAULT 0,
            is_muted BOOLEAN DEFAULT 0,
            mute_until TEXT,
            next_mute_type TEXT DEFAULT '5_min',
            total_mutes_served INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Mevcut 'punishments' tablosu şemasını güncelle (sütunlar yoksa ekle)
    try:
        cursor.execute("ALTER TABLE punishments ADD COLUMN strike_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE punishments ADD COLUMN is_muted BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE punishments ADD COLUMN mute_until TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE punishments ADD COLUMN next_mute_type TEXT DEFAULT '5_min'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE punishments ADD COLUMN total_mutes_served INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Notlar tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            note_text TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Hatırlatıcılar tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            reminder_text TEXT,
            remind_at TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Mevcut 'reminders' tablosu şemasını güncelle (sütunlar yoksa ekle)
    try:
        cursor.execute("ALTER TABLE reminders ADD COLUMN reminder_text TEXT")
    except sqlite3.OperationalError:
        pass # Sütun zaten var
    try:
        cursor.execute("ALTER TABLE reminders ADD COLUMN remind_at TEXT")
    except sqlite3.OperationalError:
        pass # Sütun zaten var
    try:
        cursor.execute("ALTER TABLE reminders ADD COLUMN created_at TEXT")
    except sqlite3.OperationalError:
        pass # Sütun zaten var

    conn.commit()
    conn.close()
    logger.info("Veritabanı tabloları kontrol edildi/oluşturuldu.")

def update_user_info(user_id: str, display_name: str):
    """Kullanıcı bilgilerini (display_name) günceller veya yeni kullanıcı ekler."""
    conn = _connect_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET display_name = ?, last_seen = ? WHERE user_id = ?",
                       (display_name, now, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, display_name, first_seen, last_seen) VALUES (?, ?, ?, ?)",
                       (user_id, display_name, now, now))
        # Yeni kullanıcı eklendiğinde boş ceza kaydı da oluştur
        cursor.execute("INSERT INTO punishments (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_user_display_names() -> dict:
    """Tüm kullanıcıların ID'lerinden görünen isimlerine bir sözlük döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, display_name FROM users")
    users = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return users

def add_message_record(user_id: str):
    """Kullanıcının her mesajını zaman damgasıyla kaydeder."""
    conn = _connect_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("INSERT INTO message_log (user_id, timestamp) VALUES (?, ?)", (user_id, now))
    conn.commit()
    conn.close()

def get_leaderboard(period: str) -> list:
    """Belirtilen periyoda göre (daily, weekly, monthly) lider tablosunu döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    start_date = None

    if period == 'daily':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'weekly':
        start_date = now - datetime.timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'monthly':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if not start_date:
        conn.close()
        return []

    start_date_str = start_date.isoformat()
    cursor.execute("""
        SELECT user_id, COUNT(*) as msg_count
        FROM message_log
        WHERE timestamp >= ?
        GROUP BY user_id
        ORDER BY msg_count DESC
        LIMIT 3
    """, (start_date_str,))
    
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

def get_user_overall_rank(user_id: str) -> tuple:
    """Kullanıcının genel mesaj sıralamasını döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, COUNT(*) as msg_count
        FROM message_log
        GROUP BY user_id
        ORDER BY msg_count DESC
    """)
    all_users_by_rank = cursor.fetchall()
    conn.close()
    
    rank = 0
    for i, (uid, count) in enumerate(all_users_by_rank, 1):
        if str(uid) == str(user_id):
            rank = i
            break
            
    return rank, len(all_users_by_rank)

def get_total_user_message_count(user_id: str) -> int:
    """Kullanıcının toplam mesaj sayısını döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM message_log WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()
    conn.close()
    return count[0] if count else 0

def get_statistics(user_id):
    """Kullanıcının kişisel istatistiklerini ve lider tablolarını formatlanmış bir metin olarak döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()

    # Kişisel bilgileri al
    cursor.execute("SELECT display_name FROM users WHERE user_id = ?", (user_id,))
    display_name_row = cursor.fetchone()
    display_name = display_name_row[0] if display_name_row else f"Kullanıcı {user_id}"

    cursor.execute("SELECT strike_count, total_mutes_served FROM punishments WHERE user_id = ?", (user_id,))
    punishment_data = cursor.fetchone()
    strike_count = punishment_data[0] if punishment_data else 0
    total_mutes = punishment_data[1] if punishment_data else 0
    conn.close()

    message_count = get_total_user_message_count(user_id)

    # Kişisel istatistik metnini oluştur
    stats_text = (
        f"📊 Kişisel İstatistiklerin:\n"
        f"  Adın: {display_name}\n"
        f"  Toplam Mesaj: {message_count}\n"
        f"  Mevcut İhlal Sayısı: {strike_count}\n"
        f"  Toplam Susturulma: {total_mutes}\n\n"
    )

    # Lider tabloları için tüm kullanıcı adlarını al
    user_names = get_user_display_names()

    def format_leaderboard(title: str, period: str) -> str:
        leaderboard_data = get_leaderboard(period)
        text = f"🏆 {title} Lider Tablosu:\n"
        if not leaderboard_data:
            text += "  - Henüz veri yok.\n"
        else:
            for i, (uid, count) in enumerate(leaderboard_data, 1):
                name = user_names.get(str(uid), f"Kullanıcı {uid}")
                text += f"  {i}. {name}: {count} mesaj\n"
        return text

    stats_text += format_leaderboard("Günlük", "daily")
    stats_text += "\n"
    stats_text += format_leaderboard("Haftalık", "weekly")
    stats_text += "\n"
    stats_text += format_leaderboard("Aylık", "monthly")
    stats_text += "\n"

    # Kullanıcının genel sıralamasını ekle
    rank, total_users = get_user_overall_rank(user_id)
    if rank > 0:
        stats_text += f"Sıralaman: {total_users} kişi arasında {rank}. sıradasın."
    else:
        stats_text += "Genel sıralamada yer almak için henüz mesaj göndermediniz."

    return stats_text


def get_punishment_data(user_id: str) -> dict:
    """Belirli bir kullanıcının ceza bilgilerini döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT strike_count, is_muted, mute_until, next_mute_type, total_mutes_served FROM punishments WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()

    if data:
        mute_until = datetime.datetime.fromisoformat(data[2]) if data[2] else None
        return {
            'strike_count': data[0],
            'is_muted': bool(data[1]),
            'mute_until': mute_until,
            'next_mute_type': data[3],
            'total_mutes_served': data[4]
        }
    else:
        # Varsayılan değerlerle yeni bir giriş oluştur
        save_punishment_data(user_id, {'strike_count': 0, 'is_muted': False, 'mute_until': None, 'next_mute_type': '5_min', 'total_mutes_served': 0})
        return {'strike_count': 0, 'is_muted': False, 'mute_until': None, 'next_mute_type': '5_min', 'total_mutes_served': 0}


def save_punishment_data(user_id: str, data: dict):
    """Belirli bir kullanıcının ceza bilgilerini kaydeder/günceller."""
    conn = _connect_db()
    cursor = conn.cursor()
    mute_until_str = data['mute_until'].isoformat() if data['mute_until'] else None
    
    cursor.execute("INSERT OR IGNORE INTO punishments (user_id, strike_count, is_muted, mute_until, next_mute_type, total_mutes_served) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, data['strike_count'], data['is_muted'], mute_until_str, data['next_mute_type'], data['total_mutes_served']))
    cursor.execute("UPDATE punishments SET strike_count = ?, is_muted = ?, mute_until = ?, next_mute_type = ?, total_mutes_served = ? WHERE user_id = ?",
                   (data['strike_count'], data['is_muted'], mute_until_str, data['next_mute_type'], data['total_mutes_served'], user_id))
    conn.commit()
    conn.close()

def clear_user_punishments(user_id: str):
    """Belirli bir kullanıcının tüm ceza sayaçlarını ve susturma durumunu sıfırlar."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM punishments WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Kullanıcı {user_id} için tüm cezalar sıfırlandı.")


def add_note(user_id: str, note_text: str):
    """Kullanıcıya yeni bir not ekler."""
    conn = _connect_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("INSERT INTO notes (user_id, note_text, created_at) VALUES (?, ?, ?)",
                   (user_id, note_text, now))
    conn.commit()
    conn.close()

def get_notes(user_id: str):
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, note_text, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    notes = [{"id": row[0], "note_text": row[1], "created_at": row[2]} for row in cursor.fetchall()]
    conn.close()
    return notes

def delete_note(note_id, user_id):
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def add_reminder(user_id: str, reminder_text: str, remind_at: datetime.datetime):
    """Kullanıcıya yeni bir hatırlatıcı ekler."""
    conn = _connect_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    remind_at_str = remind_at.isoformat()
    cursor.execute("INSERT INTO reminders (user_id, reminder_text, remind_at, created_at) VALUES (?, ?, ?, ?)",
                   (user_id, reminder_text, remind_at_str, now))
    conn.commit()
    conn.close()

def get_all_reminders() -> defaultdict:
    """Tüm aktif hatırlatıcıları kullanıcı ID'sine göre gruplandırarak döndürür."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, reminder_text, remind_at FROM reminders")
    
    reminders_by_user = {}
    for row in cursor.fetchall():
        remind_at = datetime.datetime.fromisoformat(row[3])
        user_id = row[1]
        if user_id not in reminders_by_user:
            reminders_by_user[user_id] = []
        reminders_by_user[user_id].append({
            "id": row[0],
            "user_id": user_id,
            "reminder_text": row[2],
            "remind_at": remind_at
        })
    conn.close()
    return reminders_by_user

def remove_reminder(reminder_id: int):
    """Belirtilen ID'ye sahip hatırlatıcıyı siler."""
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def get_reminders_for_user(user_id: str):
    conn = _connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, reminder_text, remind_at FROM reminders WHERE user_id = ? ORDER BY remind_at ASC", (user_id,))
    reminders = []
    for row in cursor.fetchall():
        remind_at = datetime.datetime.fromisoformat(row[2])
        reminders.append({
            "id": row[0],
            "reminder_text": row[1],
            "remind_at": remind_at
        })
    conn.close()
    return reminders
