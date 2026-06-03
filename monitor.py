import os
import requests
from datetime import datetime, timedelta
import pytz
import time
import threading

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") # Ini otomatis jadi ID Grup jika di-set di Railway
MAGNUS_TOKEN = os.environ.get("MAGNUS_TOKEN")
WIB = pytz.timezone("Asia/Jakarta")

# ID TOPIK SPESIFIK
CARL_TOPIC_ID = 2

CLUSTER_FINANSIAL = ["gaji", "nego", "slip gaji", "bonus", "thr", "counter-offer", "counter offer", "kenaikan gaji"]
CLUSTER_KARIER = ["promosi", "jabatan", "anak emas", "performance review", "kpi", "rekomendasi", "naik jabatan"]
CLUSTER_RESIGN = ["budak korporat", "toxic workplace", "politik kantor", "resign", "quiet quitting", "tenggo", "overtime", "burnout", "kerja keras", "toxic"]
ALL_CLUSTERS = CLUSTER_FINANSIAL + CLUSTER_KARIER + CLUSTER_RESIGN

CAREER_KEYWORDS = [
    "tips naik gaji", "cara cepat promosi kerja", "tips kerja di korporat",
    "pengalaman kerja 5 tahun", "salary negotiation indonesia", "career advice indonesia",
    "naik jabatan cepat", "tips sukses karir", "resign dari kerja",
    "toxic workplace indonesia", "fresh graduate kerja", "kerja di startup vs korporat",
    "passive income karyawan", "networking karir indonesia", "interview kerja tips",
    "negosiasi gaji pertama", "burnout kerja", "work life balance indonesia",
    "promosi kerja muda", "skill yang dicari perusahaan",
]

EXCLUDE_KEYWORDS = [
    "hakim", "jaksa", "polisi", "tni", "pns", "asn", "pegawai negeri",
    "pemerintah", "dpr", "dprd", "menteri", "presiden", "gubernur",
    "walikota", "bupati", "mahkamah", "pengadilan", "korupsi", "kpk",
    "drama china", "drama cina", "drama korea", "drakor", "cdrama",
    "drama thailand", "anime", "film", "sinetron", "ftv", "serial",
    "episode", "ending", "spoiler", "review drama", "nonton",
    "pemain bola", "transfer pemain", "liga", "klub", "gaji pemain", "artis", "seleb",
]

VIDEO_CACHE = {}

def search_youtube_videos(keyword):
    published_after = (datetime.now(pytz.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet", "q": keyword, "type": "video",
        "videoDuration": "short", "publishedAfter": published_after,
        "maxResults": 10, "order": "viewCount",
        "relevanceLanguage": "id", "key": YOUTUBE_API_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json().get("items", [])
    except:
        return []

def get_video_stats(video_ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "statistics,contentDetails,snippet", "id": ",".join(video_ids), "key": YOUTUBE_API_KEY}
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json().get("items", [])
    except:
        return []

def check_velocity_threshold(stats):
    view_count = int(stats.get("viewCount", 0))
    like_count = int(stats.get("likeCount", 0))
    comment_count = int(stats.get("commentCount", 0))
    if like_count == 0 or view_count == 0: return False, {}
    comment_to_like = comment_count / like_count
    metrics = {
        "view_count": view_count, "like_count": like_count, "comment_count": comment_count,
        "comment_to_like_ratio": comment_to_like, "like_to_view_ratio": like_count / view_count,
        "c1_passed": comment_to_like >= 0.08, "c2_passed": comment_to_like >= 0.05,
    }
    return metrics["c1_passed"] or metrics["c2_passed"], metrics

def check_topic_cluster(video):
    snippet = video.get("snippet", {})
    full_text = f"{snippet.get('title', '')} {snippet.get('description', '')} {' '.join(snippet.get('tags', [])) if snippet.get('tags') else ''}".lower()
    if any(kw in full_text for kw in EXCLUDE_KEYWORDS): return False, []
    matched = [kw for kw in ALL_CLUSTERS if kw in full_text]
    return len(matched) >= 2, matched

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": False,
        "message_thread_id": CARL_TOPIC_ID  # FIX: Kirim khusus ke topik Carl
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def send_alert_with_button(message, callback_data):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": False,
        "message_thread_id": CARL_TOPIC_ID,  # FIX: Kirim khusus ke topik Carl
        "reply_markup": {"inline_keyboard": [[{"text": "🎬 Generate Script", "callback_data": callback_data}]]}
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def forward_to_magnus(title, channel, video_url):
    payload_text = f"GENERATE_SCRIPT\nTITLE:{title}\nCHANNEL:{channel}\nURL:{video_url}"
    # FIX: Gunakan TELEGRAM_TOKEN (Token Carl sendiri), bukan MAGNUS_TOKEN
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": payload_text,
        "parse_mode": "HTML",
        "message_thread_id": 4  # FIX: Langsung tembak masuk ke topik Magnus (ID: 4)
    }
    try:
        requests.post(url, json=payload, timeout=10)
        return True
    except:
        return False

def format_alert(video, metrics, matched_keywords):
    snippet = video.get("snippet", {})
    video_id = video["id"]
    title = snippet.get("title", "N/A")
    channel = snippet.get("channelTitle", "N/A")
    
    fin_match = [k for k in matched_keywords if k in CLUSTER_FINANSIAL]
    kar_match = [k for k in matched_keywords if k in CLUSTER_KARIER]
    res_match = [k for k in matched_keywords if k in CLUSTER_RESIGN]
    cluster_str = ""
    if fin_match: cluster_str += f"\n   💰 Finansial: {', '.join(fin_match)}"
    if kar_match: cluster_str += f"\n   📈 Karier: {', '.join(kar_match)}"
    if res_match: cluster_str += f"\n   🚪 Resign/Politik: {', '.join(res_match)}"
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    message = (
        f"🚨 <b>CARL — Viral Career Alert!</b>\n\n"
        f"🎬 <b>{title}</b>\n"
        f"👤 {channel}\n\n"
        f"📊 <b>Metrics:</b>\n"
        f"   👁 Views: {metrics.get('view_count', 0):,}\n"
        f"   ❤️ Likes: {metrics.get('like_count', 0):,}\n"
        f"   💬 Comments: {metrics.get('comment_count', 0):,}\n\n"
        f"🔑 <b>Cluster Match:</b>{cluster_str}\n\n"
        f"🔗 {video_url}"
    )
    return message, video_url, title, channel

def run_monitor():
    send_telegram(f"⚡ <b>Carl:</b> Memulai pencarian video viral harian di forum...")
    qualified_videos = []
    seen_video_ids = set()
    
    for keyword in CAREER_KEYWORDS:
        videos = search_youtube_videos(keyword)
        if not videos: continue
        video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
        new_ids = [vid for vid in video_ids if vid not in seen_video_ids]
        if not new_ids: continue
        seen_video_ids.update(new_ids)
        stats_list = get_video_stats(new_ids)
        
        for video in stats_list:
            c3_passed, matched_kw = check_topic_cluster(video)
            if not c3_passed: continue
            c12_passed, metrics = check_velocity_threshold(video.get("statistics", {}))
            if not c12_passed: continue
            qualified_videos.append((video, metrics, matched_kw))
        time.sleep(0.3)
        
    if qualified_videos:
        for i, (video, metrics, matched_kw) in enumerate(qualified_videos):
            message, video_url, title, channel = format_alert(video, metrics, matched_kw)
            callback_data = f"gen_{video['id']}_{i}"
            VIDEO_CACHE[callback_data] = {"title": title, "channel": channel, "video_url": video_url, "matched_keywords": matched_kw}
            send_alert_with_button(message, callback_data)
            time.sleep(1)
    else:
        send_telegram("🌅 <b>Carl Laporan:</b> Hari ini aman! Tidak ada konten baru yang over-viral.")

def poll_carl():
    offset = None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    while True:
        try:
            params = {"timeout": 30}
            if offset: params["offset"] = offset
            response = requests.get(url, params=params, timeout=35).json()
            updates = response.get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    cq = update["callback_query"]
                    callback_data = cq.get("data", "")
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "Mengirim ke Magnus..."})
                    if callback_data in VIDEO_CACHE:
                        v_info = VIDEO_CACHE[callback_data]
                        success = forward_to_magnus(v_info["title"], v_info["channel"], v_info["video_url"], v_info["matched_keywords"])
                        if success:
                            send_telegram(f"✅ Data <b>{v_info['title'][:40]}...</b> dilempar ke Magnus!")
                        del VIDEO_CACHE[callback_data]
                elif "message" in update and "text" in update["message"]:
                    chat_text = update["message"]["text"].strip()
                    if chat_text == "/run" or chat_text == "/run@namabot_lo": # Kompatibel di dalam grup
                        threading.Thread(target=run_monitor).start()
        except: time.sleep(5)

def main():
    threading.Thread(target=poll_carl, daemon=True).start()
    while True:
        now = datetime.now(WIB)
        schedules = [now.replace(hour=8, minute=0, second=0, microsecond=0), now.replace(hour=20, minute=0, second=0, microsecond=0)]
        future = [t for t in schedules if t > now]
        target = min(future) if future else schedules[0] + timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        time.sleep(wait_seconds)
        run_monitor()

if __name__ == "__main__":
    main()
