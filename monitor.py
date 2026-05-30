import os
import requests
from datetime import datetime, timedelta
import pytz
import time
import random
import threading
import json

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Token Carl
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
MAGNUS_TOKEN = os.environ.get("MAGNUS_TOKEN")  # Token Magnus

WIB = pytz.timezone("Asia/Jakarta")

# ============================================================
# CLUSTER KEYWORDS
# ============================================================
CLUSTER_FINANSIAL = [
    "gaji", "nego", "slip gaji", "bonus", "thr", "counter-offer", "counter offer", "kenaikan gaji"
]
CLUSTER_KARIER = [
    "promosi", "jabatan", "anak emas", "performance review", "kpi", "rekomendasi", "naik jabatan"
]
CLUSTER_RESIGN = [
    "budak korporat", "toxic workplace", "politik kantor", "resign", "quiet quitting",
    "tenggo", "overtime", "burnout", "kerja keras", "toxic"
]
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
    "pemain bola", "transfer pemain", "liga", "klub", "gaji pemain",
    "artis", "seleb",
]

# ============================================================
# VIDEO CACHE — simpan data video sementara
# ============================================================
VIDEO_CACHE = {}

# ============================================================
# YOUTUBE FUNCTIONS
# ============================================================
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
        response.raise_for_status()
        return response.json().get("items", [])
    except Exception as e:
        print(f"Error searching '{keyword}': {e}")
        return []

def get_video_stats(video_ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "statistics,contentDetails,snippet",
        "id": ",".join(video_ids), "key": YOUTUBE_API_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("items", [])
    except Exception as e:
        print(f"Error getting stats: {e}")
        return []

# ============================================================
# CONDITION 1 & 2: VELOCITY THRESHOLD
# ============================================================
def check_velocity_threshold(stats):
    view_count = int(stats.get("viewCount", 0))
    like_count = int(stats.get("likeCount", 0))
    comment_count = int(stats.get("commentCount", 0))
    if like_count == 0 or view_count == 0:
        return False, {}
    comment_to_like = comment_count / like_count
    like_to_view = like_count / view_count
    c1_passed = comment_to_like >= 0.08
    c2_passed = comment_to_like >= 0.05
    metrics = {
        "view_count": view_count, "like_count": like_count,
        "comment_count": comment_count, "comment_to_like_ratio": comment_to_like,
        "like_to_view_ratio": like_to_view, "c1_passed": c1_passed, "c2_passed": c2_passed,
    }
    return c1_passed or c2_passed, metrics

# ============================================================
# CONDITION 3: TOPIC CLUSTER FILTER
# ============================================================
def check_topic_cluster(video):
    snippet = video.get("snippet", {})
    title = snippet.get("title", "").lower()
    description = snippet.get("description", "").lower()
    tags = " ".join(snippet.get("tags", [])).lower() if snippet.get("tags") else ""
    full_text = f"{title} {description} {tags}"
    if any(kw in full_text for kw in EXCLUDE_KEYWORDS):
        return False, []
    matched = [kw for kw in ALL_CLUSTERS if kw in full_text]
    return len(matched) >= 2, matched

# ============================================================
# TELEGRAM — CARL
# ============================================================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Carl: Telegram message sent!")
        return True
    except Exception as e:
        print(f"Carl Telegram error: {e}")
        return False

def send_alert_with_button(message, callback_data):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "🎬 Generate Script",
                    "callback_data": callback_data
                }
            ]]
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Carl: Alert with button sent!")
        return True
    except Exception as e:
        print(f"Carl button error: {e}")
        return False

def answer_callback(callback_query_id, text="⏳ Mengirim ke Magnus..."):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    requests.post(url, json={
        "callback_query_id": callback_query_id,
        "text": text
    }, timeout=10)

# ============================================================
# FORWARD KE MAGNUS
# ============================================================
def forward_to_magnus(title, channel, video_url, matched_keywords):
    """Kirim data video ke Magnus untuk di-generate scriptnya"""
    if not MAGNUS_TOKEN:
        print("MAGNUS_TOKEN tidak ada, skip forward")
        return False

    # Encode data sebagai pesan ke Magnus
    payload_text = (
        f"GENERATE_SCRIPT\n"
        f"TITLE:{title}\n"
        f"CHANNEL:{channel}\n"
        f"URL:{video_url}\n"
        f"KEYWORDS:{','.join(matched_keywords)}"
    )

    url = f"https://api.telegram.org/bot{MAGNUS_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": payload_text,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"Carl: Data video forwarded ke Magnus!")
        return True
    except Exception as e:
        print(f"Forward to Magnus error: {e}")
        return False

# ============================================================
# FORMAT ALERT
# ============================================================
def format_alert(video, metrics, matched_keywords):
    snippet = video.get("snippet", {})
    video_id = video["id"]
    title = snippet.get("title", "N/A")
    channel = snippet.get("channelTitle", "N/A")
    published = snippet.get("publishedAt", "")
    try:
        pub_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
        pub_dt = pub_dt.replace(tzinfo=pytz.utc).astimezone(WIB)
        pub_str = pub_dt.strftime("%d %b %Y, %H:%M WIB")
    except Exception:
        pub_str = published

    c_to_l = metrics.get("comment_to_like_ratio", 0)
    l_to_v = metrics.get("like_to_view_ratio", 0)

    conditions = []
    if metrics.get("c1_passed"):
        conditions.append("✅ C1: Share Velocity tinggi")
    if metrics.get("c2_passed"):
        conditions.append("✅ C2: Engagement Density tinggi")
    conditions.append("✅ C3: Topic Cluster match")

    fin_match = [k for k in matched_keywords if k in CLUSTER_FINANSIAL]
    kar_match = [k for k in matched_keywords if k in CLUSTER_KARIER]
    res_match = [k for k in matched_keywords if k in CLUSTER_RESIGN]
    cluster_str = ""
    if fin_match:
        cluster_str += f"\n   💰 Finansial: {', '.join(fin_match)}"
    if kar_match:
        cluster_str += f"\n   📈 Karier: {', '.join(kar_match)}"
    if res_match:
        cluster_str += f"\n   🚪 Resign/Politik: {', '.join(res_match)}"

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    message = (
        f"🚨 <b>CARL — Viral Career Alert!</b>\n\n"
        f"🎬 <b>{title}</b>\n"
        f"👤 {channel} | 📅 {pub_str}\n\n"
        f"📊 <b>Metrics:</b>\n"
        f"   👁 Views: {metrics.get('view_count', 0):,}\n"
        f"   ❤️ Likes: {metrics.get('like_count', 0):,}\n"
        f"   💬 Comments: {metrics.get('comment_count', 0):,}\n"
        f"   📈 Comment/Like: {c_to_l:.1%}\n"
        f"   📈 Like/View: {l_to_v:.1%}\n\n"
        f"🔑 <b>Cluster Match:</b>{cluster_str}\n\n"
        f"<b>Filter Lolos:</b>\n" + "\n".join(conditions) + "\n\n"
        f"🔗 {video_url}"
    )
    return message, video_url, title, channel

# ============================================================
# POLLING — DENGERIN TOMBOL CARL
# ============================================================
def store_video(callback_data, title, channel, video_url, matched_keywords):
    VIDEO_CACHE[callback_data] = {
        "title": title, "channel": channel,
        "video_url": video_url, "matched_keywords": matched_keywords,
    }

def poll_carl(stop_event):
    offset = None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    print("🎧 Carl polling aktif — menunggu tombol Generate Script dipencet...")

    while not stop_event.is_set():
        try:
            params = {"timeout": 30, "allowed_updates": ["callback_query"]}
            if offset:
                params["offset"] = offset
            response = requests.get(url, params=params, timeout=35)
            updates = response.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    cq = update["callback_query"]
                    callback_id = cq["id"]
                    callback_data = cq.get("data", "")

                    answer_callback(callback_id)

                    if callback_data in VIDEO_CACHE:
                        video_info = VIDEO_CACHE[callback_data]
                        print(f"🎬 Tombol dipencet! Forward ke Magnus: {video_info['title'][:50]}")

                        # Forward ke Magnus
                        success = forward_to_magnus(
                            video_info["title"],
                            video_info["channel"],
                            video_info["video_url"],
                            video_info["matched_keywords"],
                        )

                        if success:
                            send_telegram(
                                f"✅ <b>Dikirim ke Magnus!</b>\n\n"
                                f"🎬 <i>{video_info['title'][:80]}</i>\n\n"
                                f"Magnus sedang generate script... tunggu sebentar! 🖊️"
                            )
                        else:
                            send_telegram("⚠️ Gagal kirim ke Magnus. Cek MAGNUS_TOKEN di Railway.")

                        del VIDEO_CACHE[callback_data]
                    else:
                        send_telegram("⚠️ Data video expired. Jalankan monitor lagi.")

        except Exception as e:
            print(f"Carl polling error: {e}")
            time.sleep(5)

# ============================================================
# MAIN MONITOR
# ============================================================
def run_monitor():
    print(f"\n{'='*50}")
    print(f"Carl mulai monitoring: {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}")
    print(f"{'='*50}")

    qualified_videos = []
    seen_video_ids = set()

    for keyword in CAREER_KEYWORDS:
        print(f"\n🔎 Mencari: '{keyword}'")
        videos = search_youtube_videos(keyword)
        if not videos:
            continue

        video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
        new_ids = [vid for vid in video_ids if vid not in seen_video_ids]
        if not new_ids:
            continue

        seen_video_ids.update(new_ids)
        stats_list = get_video_stats(new_ids)

        for video in stats_list:
            title = video["snippet"].get("title", "")
            print(f"\n   Cek: {title[:55]}...")

            c3_passed, matched_kw = check_topic_cluster(video)
            if not c3_passed:
                print(f"   ❌ C3 gagal")
                continue
            print(f"   ✅ C3 lolos - {matched_kw}")

            c12_passed, metrics = check_velocity_threshold(video.get("statistics", {}))
            if not c12_passed:
                print(f"   ❌ C1/C2 gagal")
                continue
            print(f"   ✅ C1/C2 lolos")

            qualified_videos.append((video, metrics, matched_kw))
        time.sleep(1)

    print(f"\n📊 Total video lolos: {len(qualified_videos)}")

    if qualified_videos:
        send_telegram(
            f"🌅 <b>Carl — Laporan {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}</b>\n"
            f"Ditemukan <b>{len(qualified_videos)} video</b> yang lolos filter!\n"
            f"Tap 🎬 Generate Script di video yang mau lo jadiin konten 👇"
        )
        time.sleep(1)

        for i, (video, metrics, matched_kw) in enumerate(qualified_videos):
            message, video_url, title, channel = format_alert(video, metrics, matched_kw)
            callback_data = f"gen_{video['id']}_{i}"
            store_video(callback_data, title, channel, video_url, matched_kw)
            send_alert_with_button(message, callback_data)
            time.sleep(2)
    else:
        send_telegram(
            f"🌅 <b>Carl — Laporan {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}</b>\n\n"
            f"✅ Tidak ada video yang lolos semua filter saat ini.\n"
            f"Pantau terus di laporan berikutnya!"
        )

    print("Carl: Monitoring selesai!")

# ============================================================
# SCHEDULER
# ============================================================
def main():
    print("🤖 Carl aktif!")
    print("Laporan dikirim setiap hari jam 08:00 dan 20:00 WIB")

    stop_event = threading.Event()
    poll_thread = threading.Thread(target=poll_carl, args=(stop_event,), daemon=True)
    poll_thread.start()

    while True:
        now = datetime.now(WIB)
        schedules = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0),
        ]
        future = [t for t in schedules if t > now]
        target = min(future) if future else schedules[0] + timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"Jadwal berikutnya: {target.strftime('%d %b %Y, %H:%M WIB')}")
        print(f"Menunggu {wait_seconds/3600:.1f} jam...")
        time.sleep(wait_seconds)
        run_monitor()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        stop_event = threading.Event()
        poll_thread = threading.Thread(target=poll_carl, args=(stop_event,), daemon=True)
        poll_thread.start()
        run_monitor()
        print("\n⏳ Carl tetap aktif 5 menit — silakan tap tombol Generate Script!")
        time.sleep(300)
    else:
        main()
