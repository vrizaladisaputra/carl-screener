import os
import requests
from datetime import datetime, timedelta
import pytz
import time

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ============================================================
# KONFIGURASI THRESHOLD - lebih sensitif
# ============================================================
MIN_SHARE_PROXY = 3000   # turun dari 10k ke 3k
MAX_HOURS = 12            # diperluas dari 4 jam ke 12 jam

# ============================================================
# KEYWORDS - diperluas
# ============================================================
CAREER_KEYWORDS = [
    "tips naik gaji",
    "cara cepat promosi kerja",
    "tips kerja di korporat",
    "pengalaman kerja 5 tahun",
    "salary negotiation indonesia",
    "career advice indonesia",
    "naik jabatan cepat",
    "tips sukses karir",
    "resign dari kerja",
    "toxic workplace indonesia",
    "fresh graduate kerja",
    "kerja di startup vs korporat",
    "passive income karyawan",
    "networking karir indonesia",
    "interview kerja tips",
    "negosiasi gaji pertama",
    "burnout kerja",
    "work life balance indonesia",
    "promosi kerja muda",
    "skill yang dicari perusahaan",
]

# ============================================================
# FILTER JUDUL - pastikan relevan karir
# ============================================================
RELEVANT_TITLE_KEYWORDS = [
    "gaji", "promosi", "karir", "kerja", "korporat",
    "resign", "interview", "salary", "jabatan", "kantor",
    "atasan", "bos", "perusahaan", "karyawan", "fresh graduate",
    "burnout", "toxic", "networking", "skill", "passive income",
    "work life", "negosiasi", "startup", "magang", "internship",
]

# ============================================================
# FILTER EXCLUDE - konten yang TIDAK relevan
# ============================================================
EXCLUDE_KEYWORDS = [
    # Politik & pemerintahan
    "hakim", "jaksa", "polisi", "tni", "pns", "asn", "pegawai negeri",
    "pemerintah", "dpr", "dprd", "menteri", "presiden", "gubernur",
    "walikota", "bupati", "mahkamah", "pengadilan", "korupsi", "kpk",
    "anggaran", "apbn", "subsidi", "pajak pemerintah", "birokrasi",

    # Drama & hiburan
    "drama china", "drama cina", "drama korea", "drakor", "cdrama",
    "drama thailand", "anime", "film", "sinetron", "ftv", "serial",
    "episode", "ending", "spoiler", "review drama", "nonton",

    # Olahraga
    "pemain bola", "transfer pemain", "liga", "klub", "gaji pemain",

    # Selebriti
    "artis", "seleb", "influencer gaji", "youtuber gaji",
]

WIB = pytz.timezone("Asia/Jakarta")

def is_career_relevant(title):
    title_lower = title.lower()
    
    # Cek apakah masuk exclude list dulu
    if any(kw in title_lower for kw in EXCLUDE_KEYWORDS):
        print(f"   ⛔ Excluded: {title[:50]}")
        return False
    
    # Baru cek apakah relevan karir
    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)
    
def search_youtube_videos(keyword):
    published_after = (datetime.now(pytz.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    # Kondisi 1: 3k views dalam 12 jam
    if age_hours <= MAX_HOURS and view_count >= MIN_SHARE_PROXY:
        return True, f"🔥 {view_count:,} views dalam {age_hours:.1f} jam!"

    # Kondisi 2: Engagement tinggi
    if view_count > 0:
        engagement = (like_count + comment_count) / view_count
        if engagement > 0.05 and view_count > 2000:
            return True, f"⚡ Engagement tinggi: {engagement:.1%} ({view_count:,} views)"

    # Kondisi 3: View tinggi secara absolut (video lama tapi tetap viral)
    if view_count >= 50000:
        return True, f"📈 {view_count:,} views total — trending!"

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
    comment_count = int(stats.get("commentCount", 0))

    try:
        pub_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
        pub_dt = pub_dt.replace(tzinfo=pytz.utc).astimezone(WIB)
        pub_str = pub_dt.strftime("%d %b %Y, %H:%M WIB")
    except Exception:
        pub_str = published

    url = f"https://www.youtube.com/watch?v={video_id}"

    message = (
        f"🚨 <b>VIRAL CAREER VIDEO ALERT!</b>\n\n"
        f"📌 <b>Keyword:</b> {keyword}\n"
        f"{viral_reason}\n\n"
        f"🎬 <b>Judul:</b> {title}\n"
        f"👤 <b>Channel:</b> {channel}\n"
        f"📅 <b>Upload:</b> {pub_str}\n"
        f"👁 <b>Views:</b> {view_count:,}\n"
        f"❤️ <b>Likes:</b> {like_count:,}\n"
        f"💬 <b>Comments:</b> {comment_count:,}\n\n"
        f"🔗 <b>Link:</b> {url}\n\n"
        f"💡 <i>Video ini berpotensi mempengaruhi mindset karir banyak orang!</i>"
    )
    return message

def run_monitor():
    now_str = datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')
    print(f"Mulai monitoring: {now_str}")
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
            title = video["snippet"].get("title", "")
            viral, reason = is_viral(video, published_at)
            if viral and is_career_relevant(title):
                found_videos.append((video, reason, keyword))
                print(f"VIRAL: {title[:60]}")

        time.sleep(1)

    print(f"Total viral videos: {len(found_videos)}")

    if found_videos:
        send_telegram(
            f"🌅 <b>Laporan - {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}</b>\n"
            f"Ditemukan <b>{len(found_videos)} video viral</b> soal karir!\n"
            f"Berikut detailnya 👇"
        )
        time.sleep(1)
        for video, reason, keyword in found_videos:
            send_telegram(format_alert(video, reason, keyword))
            time.sleep(2)
    else:
        send_telegram(
            f"🌅 <b>Laporan - {datetime.now(WIB).strftime('%d %b %Y, %H:%M WIB')}</b>\n\n"
            f"✅ Tidak ada video karir viral saat ini.\n"
            f"Pantau terus di laporan berikutnya!"
        )

    print("Monitoring selesai!")

def main():
    print("Career Viral Monitor aktif!")
    print("Laporan dikirim setiap hari jam 08:00 dan 20:00 WIB")

    while True:
        now = datetime.now(WIB)

        # 2x sehari: jam 8 pagi dan jam 8 malam
        schedules = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0),
        ]

        future = [t for t in schedules if t > now]
        if future:
            target = min(future)
        else:
            target = schedules[0] + timedelta(days=1)

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
        main()
