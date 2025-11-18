import datetime
import re
from config import FORBIDDEN_WORDS_FILE # config.py'den dosya yolunu import et
# from commands.utils import get_user_display_name_and_storage_name # Şu an için buraya doğrudan gerek yok, main.py hallediyor.

# Yasaklı kelimeleri depolayacak modül seviyesinde bir set
_forbidden_words_set = set()

def load_forbidden_words_from_file():
    """
    Yasaklı kelimeleri belirtilen dosyadan yükler.
    """
    global _forbidden_words_set
    try:
        with open(FORBIDDEN_WORDS_FILE, 'r', encoding='utf-8') as f:
            # Her satırı oku, boşlukları temizle ve küçük harfe çevirerek sete ekle
            _forbidden_words_set = {line.strip().lower() for line in f if line.strip()}
        print(f"[{datetime.datetime.now()}] {len(_forbidden_words_set)} yasaklı kelime yüklendi.")
    except FileNotFoundError:
        print(f"[{datetime.datetime.now()}] UYARI: Yasaklı kelimeler dosyası bulunamadı: {FORBIDDEN_WORDS_FILE}")
        _forbidden_words_set = set() # Dosya bulunamazsa seti boş bırak
    except Exception as e:
        print(f"[{datetime.datetime.now()}] HATA: Yasaklı kelimeler yüklenirken bir hata oluştu: {e}")
        _forbidden_words_set = set()

def check_for_swears(user_id: str, message_content: str) -> bool:
    """
    Mesaj içeriğinde yasaklı kelime olup olmadığını kontrol eder.
    Varsayılan olarak mesajı siler veya uyarı gönderir (gerçek bir bot ortamında).
    """
    if not _forbidden_words_set:
        # Kelimeler yüklenmemişse veya dosya boşsa kontrol yapma
        return False

    # Mesajı küçük harfe çevir ve kelimelere ayır
    words = re.findall(r'\b\w+\b', message_content.lower())
    
    found_swears = [word for word in words if word in _forbidden_words_set] # Yüklenen seti kullan
    
    if found_swears:
        print(f"[{datetime.datetime.now()}] KÜFÜR TESPİT EDİLDİ! Kullanıcı: {user_id}, Mesaj: '{message_content}'")
        print(f"Tespit edilen kelimeler: {', '.join(found_swears)}")
        # Burada gerçek bir bot ortamında mesajı silme veya kullanıcıya uyarı gönderme işlemi yapılır.
        return True
    return False

# Eğer aşağıdaki satır mevcutsa, bu satırı silin veya yorum satırı yapın:
# load_forbidden_words_from_file()
