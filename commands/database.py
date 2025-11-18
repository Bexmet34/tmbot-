import sqlite3
import datetime
import logging
import json

from config import DB_PATH

logger = logging.getLogger(__name__)

def get_db_connection():
    """Veritabanı bağlantısı sağlar."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Sütun isimleriyle erişim için
    return conn

def create_tables():
    """Gerekli veritabanı tablolarını oluşturur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            display_name TEXT,
            first_name TEXT,
            last_name TEXT,
            is_bot INTEGER DEFAULT 0,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            reminder_text TEXT,
            remind_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS punishments (
            user_id TEXT PRIMARY KEY,
            strike_count INTEGER DEFAULT 0,
            is_muted INTEGER DEFAULT 0,
            mute_until TIMESTAMP,
            next_mute_type TEXT DEFAULT '5_min', -- '5_min', '1_hr', '1_hr_served'
            total_mutes_served INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Veritabanı tabloları kontrol edildi/oluşturuldu.")

def update_user_info(user_id: str, username: str, first_name: str = None, last_name: str = None, is_bot: bool = False):
    """Kullanıcı bilgilerini günceller veya ekler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    display_name = first_name if first_name else username
    if last_name:
        display_name += f" {last_name}"

    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, display_name, first_name, last_name, is_bot, last_activity)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, display_name, first_name, last_name, int(is_bot)))
    conn.commit()
    conn.close()

def get_user_display_names():
    """Tüm kullanıcıların user_id'sine göre display_name'ini içeren bir sözlük döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, display_name FROM users')
    users = cursor.fetchall()
    conn.close()
    return {user['user_id']: user['display_name'] for user in users}

def get_punishment_data(user_id: str):
    """Kullanıcının ceza verilerini alır. Yoksa varsayılan değerlerle oluşturur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM punishments WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    conn.close()

    if data:
        return dict(data)
    else:
        # Varsayılan değerlerle yeni bir giriş oluştur
        default_data = {
            'user_id': user_id,
            'strike_count': 0,
            'is_muted': False,
            'mute_until': None,
            'next_mute_type': '5_min',
            'total_mutes_served': 0
        }
        save_punishment_data(user_id, default_data) # Veritabanına kaydet
        return default_data

def save_punishment_data(user_id: str, data: dict):
    """Kullanıcının ceza verilerini kaydeder."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO punishments 
        (user_id, strike_count, is_muted, mute_until, next_mute_type, total_mutes_served)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data.get('strike_count', 0),
        int(data.get('is_muted', False)),
        data.get('mute_until'), # datetime nesnesi direk kaydedilebilir
        data.get('next_mute_type', '5_min'),
        data.get('total_mutes_served', 0)
    ))
    conn.commit()
    conn.close()

def clear_user_punishments(user_id: str):
    """Bir kullanıcının tüm ceza verilerini sıfırlar."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM punishments WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Kullanıcı {user_id} için cezalar temizlendi.")

def add_message_record(user_id: str):
    """Bir kullanıcı mesaj attığında kayıt ekler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def add_reminder(user_id: str, reminder_text: str, remind_at: datetime.datetime):
    """Yeni bir hatırlatıcı ekler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reminders (user_id, reminder_text, remind_at)
        VALUES (?, ?, ?)
    ''', (user_id, reminder_text, remind_at))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_all_reminders():
    """Tüm hatırlatıcıları kullanıcı ID'sine göre gruplayarak döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, reminder_text, remind_at FROM reminders')
    reminders = cursor.fetchall()
    conn.close()

    grouped_reminders = defaultdict(list)
    for r in reminders:
        # 'remind_at' string olarak geliyor, datetime objesine dönüştür
        r_dict = dict(r)
        if isinstance(r_dict['remind_at'], str):
            try:
                r_dict['remind_at'] = datetime.datetime.strptime(r_dict['remind_at'], '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                r_dict['remind_at'] = datetime.datetime.strptime(r_dict['remind_at'], '%Y-%m-%d %H:%M:%S')
        grouped_reminders[r_dict['user_id']].append(r_dict)
    return grouped_reminders

def remove_reminder(reminder_id: int):
    """Belirtilen ID'ye sahip hatırlatıcıyı siler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    conn.commit()
    conn.close()

# Yeni istatistik fonksiyonları
def get_total_messages_count() -> int:
    """Tüm sohbetlerde gönderilen toplam mesaj sayısını döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM messages')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_unique_users_count() -> int:
    """Toplam benzersiz kullanıcı sayısını döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_active_users_last_24_hours() -> int:
    """Son 24 saat içinde mesaj gönderen benzersiz kullanıcı sayısını döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    twenty_four_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=24)
    cursor.execute(
        'SELECT COUNT(DISTINCT user_id) FROM messages WHERE timestamp >= ?',
        (twenty_four_hours_ago,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_top_message_senders(limit: int = 5) -> list[tuple[str, int]]:
    """En çok mesaj gönderen kullanıcıları (display_name, mesaj_sayısı) olarak döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.display_name, COUNT(m.id) as message_count
        FROM messages m
        JOIN users u ON m.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY message_count DESC
        LIMIT ?
    ''', (limit,))
    top_senders = cursor.fetchall()
    conn.close()
    return [(row['display_name'], row['message_count']) for row in top_senders]

def get_user_stats(user_id: str) -> dict:
    """Belirli bir kullanıcının mesaj ve ceza istatistiklerini döndürür."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_info = cursor.execute('SELECT display_name FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if not user_info:
        conn.close()
        return {'display_name': 'Bilinmeyen Kullanıcı', 'message_count': 0, 'strike_count': 0, 'is_muted': False, 'mute_until': None}

    display_name = user_info['display_name']

    message_count = cursor.execute(
        'SELECT COUNT(*) FROM messages WHERE user_id = ?', (user_id,)
    ).fetchone()[0]

    punishment_data = get_punishment_data(user_id) # Zaten bir dict döndürüyor
    
    conn.close()
    return {
        'display_name': display_name,
        'message_count': message_count,
        'strike_count': punishment_data.get('strike_count', 0),
        'is_muted': bool(punishment_data.get('is_muted', 0)),
        'mute_until': punishment_data.get('mute_until')
    }

def get_statistics(user_id: str = None) -> str:
    """
    Genel istatistikler sağlar veya belirli bir kullanıcının istatistiklerini.
    Bu fonksiyonu yeni detaylı istatistik fonksiyonları yerine kullanmayacağız.
    """
    total_messages = get_total_messages_count()
    total_users = get_total_unique_users_count()
    active_users_24h = get_active_users_last_24_hours()

    stats_text = (
        f"**Genel İstatistikler:**\n"
        f"Toplam Mesaj: {total_messages}\n"
        f"Toplam Kullanıcı: {total_users}\n"
        f"Son 24 Saatte Aktif Kullanıcı: {active_users_24h}\n"
    )
    
    if user_id:
        user_stats = get_user_stats(user_id)
        stats_text += (
            f"\n**{user_stats['display_name']} Kullanıcı İstatistikleri:**\n"
            f"Gönderilen Mesaj: {user_stats['message_count']}\n"
            f"Mevcut İhlal Sayısı: {user_stats['strike_count']}\n"
            f"Susturulmuş mu?: {'Evet' if user_stats['is_muted'] else 'Hayır'}\n"
        )
        if user_stats['is_muted'] and user_stats['mute_until']:
            mute_until_dt = datetime.datetime.strptime(user_stats['mute_until'], '%Y-%m-%d %H:%M:%S.%f') if isinstance(user_stats['mute_until'], str) else user_stats['mute_until']
            stats_text += f"Susturma Bitiş Tarihi: {mute_until_dt.strftime('%d.%m.%Y %H:%M:%S')}\n"

    return stats_text
