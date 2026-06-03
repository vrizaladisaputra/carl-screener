import os
import requests
from datetime import datetime, timedelta
import pytz
import time
import threading

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WIB = pytz.timezone("Asia/Jakarta")

CARL_TOPIC_ID = 2  # ID Topik Carl di Grup

CAREER_KEYWORDS = [
    "tips naik gaji", "cara cepat promosi kerja", "tips kerja di korporat",
    "salary negotiation indonesia", "career advice indonesia", "naik jabatan cepat",
    "toxic workplace indonesia", "fresh graduate kerja", "burnout kerja"
]

VIDEO_CACHE = {}

def search_youtube_videos(keyword):
    published_after = (datetime.now(pytz.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet", "q": keyword, "type": "video", "videoDuration": "short",
        "publishedAfter": published_after, "maxResults": 5, "order": "viewCount",
        "relevanceLanguage": "id", "key": YOUTUBE_API_KEY,
    }
    try: return requests.get(url, params=params, timeout=10).json().get("items", [])
    except: return []

def get_video_stats(video_id):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "statistics,snippet", "id": video_id, "key": YOUTUBE_API_KEY}
    try: return requests.get(url, params=params, timeout=10).json().get("items", [{}])[0]
    except: return {}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "message_thread_id": CARL_TOPIC_ID}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def send_alert_with_button(message, callback_data):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "message_thread_id": CARL_TOPIC_ID,
        "reply_markup": {"inline_keyboard": [[{"text": "🎬 Generate Script", "callback_data": callback_data}]]}
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# ============================================================
# JALUR TRANSMISI DIREK KE MAGNUS (BYPASS TELEGRAM BOT PRIVACY)
# ============================================================
def forward_to_magnus(title, channel, video_url):
    # Railway memetakan nama service menjadi alamat internal (magnus-scriptwriter) di port 8080
    magnus_internal_url = "http://magnus-scriptwriter:8080/generate"
    
    payload = {
        "title": title,
        "channel": channel,
        "video_url": video_url
    }
    
    try:
        response = requests.post(magnus_internal_url, json=payload, timeout=15)
        if response.status_code == 200:
            return True
    except Exception as e:
        print(f"Jalur tol Railway error: {e}")
    return False

def run_monitor():
    send_telegram("⚡ <b>Carl:</b> Memulai pencarian video viral harian...")
    for kw in CAREER_KEYWORDS:
        videos = search_youtube_videos(kw)
        for v in videos:
            vid_id = v.get("id", {}).get("videoId")
            if not vid_id: continue
            detail = get_video_stats(vid_id)
            stats = detail.get("statistics", {})
            
            if int(stats.get("commentCount", 0)) >= 1:
                title = detail.get("snippet", {}).get("title", "N/A")
                channel = detail.get("snippet", {}).get("channelTitle", "N/A")
                v_url = f"https://www.youtube.com/watch?v={vid_id}"
                
                msg = f"🚨 <b>CARL — Viral Career Alert!</b>\n\n🎬 <b>{title}</b>\n👤 {channel}\n🔗 {v_url}"
                callback_data = f"gen_{vid_id}"
                VIDEO_CACHE[callback_data] = {"title": title, "channel": channel, "video_url": v_url}
                
                send_alert_with_button(msg, callback_data)
                return
    send_telegram("🌅 <b>Carl Laporan:</b> Hari ini aman! Belum ada konten over-viral baru.")

def poll_carl():
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            res = requests.get(url, params=params, timeout=35).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    cq = update["callback_query"]
                    cb_data = cq.get("data", "")
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "Menghubungi Magnus..."})
                    if cb_data in VIDEO_CACHE:
                        v_info = VIDEO_CACHE[cb_data]
                        if forward_to_magnus(v_info["title"], v_info["channel"], v_info["video_url"]):
                            send_telegram(f"✅ Sukses menghubungi Magnus lewat jalur internal Railway!")
                        else:
                            send_telegram(f"⚠️ Gagal mengirim data lewat jalur tol internal.")
                elif "message" in update and "text" in update["message"]:
                    if update["message"]["text"] == "/run":
                        threading.Thread(target=run_monitor).start()
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=poll_carl, daemon=True).start()
    run_monitor()
    while True: time.sleep(3600)
