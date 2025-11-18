import datetime
from config import GAME_SERVER_UTC_OFFSET_HOURS

def get_game_server_time() -> str:
    """
    Oyun sunucusunun saat dilimine göre anlık saati gösterir.
    AOE formatına göre çıktı verir.
    """
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    game_server_time = utc_now + datetime.timedelta(hours=GAME_SERVER_UTC_OFFSET_HOURS)
    
    return f"AOE'de şuan Saat {game_server_time.strftime('%H:%M')}"
