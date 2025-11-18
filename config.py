import datetime
import os # Added for path manipulation

# Küfür / Argo Filtresi
# Bu, yasakli.txt dosyasını config.py ile aynı dizinde (yani ana bot dizininde) arar.
FORBIDDEN_WORDS_FILE = os.path.join(os.path.dirname(__file__), 'yasakli.txt')

# Sunucu Saati / Oyun Saati
# Oyun sunucusunun UTC'ye göre saat farkı (örn: UTC+0 için 0, UTC-4 için -4)
GAME_SERVER_UTC_OFFSET_HOURS = 0 # Kullanıcının belirleyeceği sunucu saati farkı (örnek olarak UTC+0)
BOT_TOKEN = "8154263807:AAHK2apy8aI-wYygzGTxKcyjXegL1II15N4"

# Yönetici ID'leri (Bot'un adminleri)
ADMIN_IDS = ["5104018162", "1087968824"] # Yönetici yetkisi vereceğiniz kullanıcıların ID'lerini buraya ekleyin

# Veritabanı dosyasının yolu
# Bu, bot_data.db dosyasını config.py ile aynı dizinde (yani ana bot dizininde) oluşturur.
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_data.db') # Eklendi: Veritabanı yolu

# Mehter Marşı MP3 dosyasının yolu
MEHTER_MP3_PATH = os.path.join(os.path.dirname(__file__), 'music', 'mehter.mp3') # Eklendi: Mehter Marşı yolu
