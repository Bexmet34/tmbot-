import datetime

def send_welcome_message(member_name: str):
    """
    Yeni üyeye karşılama mesajı gönderir.
    """
    welcome_message = f"Hoş geldin @{member_name}! Kuralları okumayı unutma 😊"
    print(f"[{datetime.datetime.now()}] BOT: {welcome_message}")
    # Gerçek bir botta: messaging_platform.send_message(channel_id, welcome_message)
