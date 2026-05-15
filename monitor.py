import os
import requests
from datetime import datetime, timedelta
import pytz
import time

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

MIN_SHARE_PROXY = 10000
MAX_HOURS = 4

CAREER_KEYWORDS = [
    "tips naik gaji",
    "cara cepat promosi kerja",
    "tips kerja di korporat",
    "pengalaman kerja 5 tahun",
    "salary negotiation indonesia",
    "career advice indonesia",
    "naik jabatan cepat",
    "tips sukses karir",
]

WIB = pytz.timezone("Asia/Jakarta")

def search_youtube_videos(keyword):
    published_after = (datetime.now(pytz.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "videoDuration": "short",
        "publishedAfter": published_after,
        "maxResults": 10,
        "order": "viewCount",
        "relevanceLanguage": "id",
        "key": YOUTUBE_API_KEY,
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
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("items", [])
    except Exception as e:
        print(f"Error getting stats: {e}")
        return []

def is_viral(video, published_at_str):
    stats = video.get("statistics", {})
    view_count = int(stats.get("viewCount", 0))
    like_count = int(stats.get("likeCount", 0))
    comment_count = int(stats.get("commentCount", 0))
    published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ")
    published_at = published_at.replace(tzinfo=pytz.utc)
    age_hours = (datetime.now(pytz.utc) - published_at).total_seconds() / 3600
    if age_hours <= MAX_HOURS and view_count >= MIN_SHARE_PROXY:
        return True, f"🔥 {view_count:,} views dalam {age_hours:.1f} jam!"
    if view_count > 0:
        engagement = (like_count + comment_count) / view_count
        if engagement > 0.05 and view_count > 5000:
            return True, f"⚡ Engagement tinggi: {engagement:.1%} ({view_count:,} views)"
    return False, ""

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
        print("Telegram alert sent!")
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def format_alert(video_data, viral_reason, keyword):
    snippet = video_data["snippet"]
    stats = video_data.get("statistics", {})
    video_id = video_data["id"]
    title = snippet.get("title", "N/A")
    channel = snippet.get("channelTitle", "N/A")
    published = snippet.get("publishedAt", "")
    view_count = int(stats.get("viewCount", 0))
    like_count = int(stats.get("likeCount", 0))
    try:
        pub_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
        pub_dt = pub_dt.replace(tzinfo=pytz.utc).astimezone(WIB)
        pub_str = pub_dt.strftime("%d %b %Y, %H:%M WIB")
    except Exception:
        pub_str = published
    url = f"https://www.youtube.com/watch?v={video_id}"
    message = f"🚨 <b>VIRAL CAREER VIDEO ALERT!</b>\n\n📌 <b>Keyword:</b> {keyword}\n{viral_reason}\n\n🎬 <b>Judul:</b> {title}\n👤 <b>Channel:</b> {channel}\n📅 <b>Upload:</b> {pub_str}\n👁 <b>Views:</b> {view_count:,}\n❤️ <b>Likes:</b> {like_count:,}\n\n🔗 <b>Link:</b> {url}\n\n💡 <i>Video ini berpotensi mempengaruhi mindset karir banyak orang!</i>"
    return message

def run_monitor():
    print(f"Mulai monitoring: {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}")
    found_videos = []
    seen_video_ids = set()
    for keyword in CAREER_KEYWORDS:
        print(f"Mencari: '{keyword}'")
        videos = search_youtube_videos(keyword)
        if not videos:
            continue
        video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
        if not video_ids:
            continue
        new_ids = [vid for vid in video_ids if vid not in seen_video_ids]
        if not new_ids:
            continue
        seen_video_ids.update(new_ids)
        stats_list = get_video_stats(new_ids)
        for video in stats_list:
            published_at = video["snippet"].get("publishedAt", "")
            viral, reason = is_viral(video, published_at)
            if viral:
                found_videos.append((video, reason, keyword))
                print(f"VIRAL: {video['snippet']['title'][:50]}")
        time.sleep(1)
    print(f"Total viral videos: {len(found_videos)}")
    if found_videos:
        send_telegram(f"🌅 <b>Laporan Harian - {datetime.now(WIB).strftime('%d %b %Y')}</b>\nDitemukan <b>{len(found_videos)} video viral</b> soal karir!\nBerikut detailnya 👇")
        time.sleep(1)
        for video, reason, keyword in found_videos:
            send_telegram(format_alert(video, reason, keyword))
            time.sleep(2)
    else:
        send_telegram(f"🌅 <b>Laporan Harian - {datetime.now(WIB).strftime('%d %b %Y')}</b>\n\n✅ Tidak ada video karir yang viral hari ini.\nPantau terus besok jam 08.00 WIB!")
    print("Monitoring selesai!")

def main():
    print("Career Viral Monitor aktif!")
    print("Akan kirim laporan setiap hari jam 08:00 WIB")
    while True:
        now = datetime.now(WIB)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"Jadwal berikutnya: {target.strftime('%d %b %Y, %H:%M WIB')}")
        print(f"Menunggu {wait_seconds/3600:.1f} jam...")
        time.sleep(wait_seconds)
        run_monitor()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_monitor()
    else:
        run_monitor()
