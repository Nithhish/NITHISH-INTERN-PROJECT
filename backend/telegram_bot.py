import urllib.request
import urllib.parse
import threading

def send_telegram_alert(message: str, token: str, chat_id: str):
    """Sends a Telegram alert without blocking the main thread"""
    
    if not token or token == "<TOKEN>" or not chat_id:
        return
        
    def _send():
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
        except Exception as e:
            print(f"[WARN] Failed to send Telegram alert: {e}")
            
    # Send in a background thread so it doesn't slow down the response
    threading.Thread(target=_send, daemon=True).start()
