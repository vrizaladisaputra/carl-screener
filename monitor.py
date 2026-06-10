import os
import requests
from datetime import datetime, timedelta, timezone  # Menggunakan timezone bawaan Python
time
import json
import threading
import re  # Ditambahkan untuk deteksi pola kata bahasa asing

# ============================================================
# KONFIGURASI BOT CARL + GEMINI FILTER
# ============================================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # Wajib ditambahkan di Railway Carl!

CARL_TOPIC_ID = 2  # ID Topik Carl di Grup Telegram

# Keyword dengan volume pencarian raksasa & emosi tinggi di Indonesia (Viral Bait)
# Namun akan disaring super ketat oleh Gemini agar hanya meloloskan 2 pilar Rizal.
CAREER_KEYWORDS = [
    "budak korporat", "politik kantor", "realita anak korporat",
    "banting setir karir", "gaji SCBD", "tips nego gaji",
    "pindah kerja naik gaji", "quarter life crisis karir", "curhat kerjaan",
    "layoff startup", "wfa jakarta cafe", "product manager indonesia"
]

VIDEO_CACHE = {}

def is_indonesian_or_english_only(title, description):
    """
    Python-Level Firewall untuk menyaring dan membuang konten asing (seperti Hindi, Hinglish, dll)
    secara instan sebelum memanggil Gemini API. Hemat token & 100% akurat.
    """
    text = f"{title} {description}".lower()
    
    # 1. Cek Karakter Devnagari (Aksara India): Range Unicode \u0900 - \u097F
    for char in text:
        if '\u0900' <= char <= '\u097f':
            return False
            
    # 2. Cek Kata-kata Khas Romanized Hindi (Hinglish) yang sering lolos deteksi biasa
    hinglish_stopwords = {
        "aur", "ka", "ki", "ke", "hai", "ko", "se", "bhi", "ho", "kar", 
        "aapne", "kabhi", "socha", "sach", "asli", "naam", "yaar", "hota", 
        "hoga", "kya", "meri", "mera", "tum", "aap", "gaya", "hi", "mein",
        "ek", "dusre", "khilaf", "aapko"
    }
    
    # Memisahkan kata dengan regex untuk menghindari kecocokan parsial
    words = set(re.findall(r'\b\w+\b', text))
    
    # Jika ada kata Hinglish yang terdeteksi, tolak video
    if words.intersection(hinglish_stopwords):
        return False
        
    return True

def evaluate_videos_batch_with_gemini(video_list):
    """
    Menggunakan Gemini AI untuk menyaring daftar video secara massal (batch).
    Mengurangi puluhan API call menjadi hanya 1-2 call saja! Bebas error 429.
    """
    if not GEMINI_API_KEY:
        return {"match_found": False, "error": "api_key_missing"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # Format list video agar rapi dibaca AI
    formatted_list = []
    for idx, vid in enumerate(video_list):
        formatted_list.append(f"""
--- VIDEO KANDIDAT #{idx+1} ---
ID: {vid['id']}
Title: {vid['title']}
Channel: {vid['channel']}
Description: {vid['description']}
""")
    
    videos_text = "\n".join(formatted_list)
    
    prompt = f"""
    Kamu bertindak sebagai Content Curator & Strategy Filter kelas dunia untuk personal branding TikTok Rizal / Ical (27 tahun).
    
    BERIKUT ADALAH PROFIL DAN BACKGROUND RIZAL:
    - Pendidikan: SBM ITB (Manajemen Bisnis).
    - Karir Sekarang: Product Manager (PM) di Truvisor.io, memegang produk cybersecurity & network visibility (Vectra AI & Keysight Technologies). Gaji saat ini 17jt/bulan.
    - Cara Kerja: WFH/WFA mobile, jarang ke kantor, banyakan nyetir/pindah tempat buat ketemu customer & partner B2B di luar.
    - Masa Lalu Karir: Pernah jadi Relationship Manager di Shopee, Account Manager Lifestyle di TikTok, dan Tech Sales di Soltius. Sukses melakukan 'Tech Pivot' dari non-tech/sales ke cybersecurity yang sangat teknis tanpa background coding.
    
    TUGAS KAMU:
    Evaluasi daftar video kandidat berikut dan tentukan apakah ada yang cocok untuk dijadikan bahan konten TikTok Rizal:
    {videos_text}
    
    🚨 ATURAN EVALUASI & KURASI PILAR:
    1. Pilih MAKSIMAL SATU (1) video TERBAIK yang paling cocok dengan salah satu dari 2 pilar Rizal:
       - Pilar 1: "The Tech Pivot" (Karir & Pindah Jalur ke IT/Cybersecurity)
       - Pilar 2: "The Mobile PM Lifestyle & Corporate Hacks" (Day in My Life & Soft Skills)
    2. Jika tidak ada satu pun video yang memenuhi kriteria pilar Rizal, set "match_found" menjadi false.

    Kembalikan respon harus dalam format JSON yang valid seperti contoh di bawah (JANGAN beri komentar atau penjelasan apa pun di luar JSON):
    {{
        "match_found": true,
        "selected_video_id": "Masukkan_ID_Video_Yang_Kamu_Pilih_Di_Sini",
        "pilar": "Pilar 1: The Tech Pivot" atau "Pilar 2: The Mobile PM Lifestyle & Corporate Hacks",
        "reason": "Alasan singkat kenapa video ini lolos kurasi pilar kamu",
        "twist": "Instruksi spesifik cara nge-twist konten ini agar masuk ke sudut pandang/pengalaman hidup Rizal (SBM ITB/Ex-TikTok-Shopee/PM Cybersecurity gaji 17jt)",
        "hooks": [
            "Hook alternatif 1 (gaya The Pragmatic Older Brother: santai, blak-blakan, realistis, berbobot)",
            "Hook alternatif 2"
        ]
    }}
    
    Jika tidak ada satupun yang cocok:
    {{
        "match_found": false
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
        response.raise_for_status()
        res_data = response.json()
        result_text = res_data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(result_text)
    except Exception as e:
        print(f"Error pada penyaringan Batch AI Carl: {e}")
        return {"match_found": False}

def search_youtube_videos(keyword):
    published_after = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://www.googleapis.com/youtube/v3/search"
    
    params = {
        "part": "snippet", 
        "q": keyword, 
        "type": "video",
        "publishedAfter": published_after, 
        "maxResults": 3, 
        "order": "viewCount",
        "relevanceLanguage": "id", 
        "regionCode": "ID",
        "key": YOUTUBE_API_KEY,
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

def forward_to_magnus(title, channel, video_url, twist_strategy):
    enriched_title = f"{title} (💡 STRATEGI TWIST ICAL: {twist_strategy})"
    
    # UPGRADE: Jalur internal dinamis menggunakan official Railway Private Domain & Port
    magnus_internal_url = os.environ.get("MAGNUS_URL", "http://magnus-scriptwriter.railway.internal:8080/generate")
    payload = {
        "title": enriched_title,
        "channel": channel,
        "video_url": video_url
    }
    try:
        response = requests.post(magnus_internal_url, json=payload, timeout=15)
        if response.status_code == 200:
            return True
    except Exception as e:
        print(f"Gagal kirim via jalur internal: {e}")
    return False

def run_monitor():
    send_telegram("⚡ <b>Carl:</b> Mengumpulkan video kandidat potensial dari 12 kata kunci harian...")
    candidates = []
    seen_ids = set()
    
    for kw in CAREER_KEYWORDS:
        videos = search_youtube_videos(kw)
        for v in videos:
            vid_id = v.get("id", {}).get("videoId")
            if not vid_id or vid_id in seen_ids: continue
            seen_ids.add(vid_id)
            
            detail = get_video_stats(vid_id)
            stats = detail.get("statistics", {})
            snippet = detail.get("snippet", {})
            
            if int(stats.get("commentCount", 0)) >= 1:
                title = snippet.get("title", "N/A")
                desc = snippet.get("description", "")
                channel = snippet.get("channelTitle", "N/A")
                v_url = f"https://www.youtube.com/watch?v={vid_id}"
                
                # PYTHON FIREWALL CHECK (Instan & Tanpa Makan Token!)
                if is_indonesian_or_english_only(title, desc):
                    candidates.append({
                        "id": vid_id,
                        "title": title,
                        "description": desc,
                        "channel": channel,
                        "url": v_url
                    })
        time.sleep(0.5) # Jeda aman rate limit YouTube Search API
                    
    if not candidates:
        send_telegram("🌅 <b>Carl Laporan:</b> Pemindaian selesai. Tidak ada video kandidat yang memenuhi kriteria awal bahasa & engagement.")
        return

    send_telegram(f"🧠 <b>Carl:</b> Menemukan {len(candidates)} kandidat awal. Memilah video terbaik menggunakan filter AI secara batch...")
    
    # Ambil maksimal 8 kandidat teratas untuk dikurasi sekaligus dalam 1 API call
    batch_candidates = candidates[:8]
    
    ai_evaluation = evaluate_videos_batch_with_gemini(batch_candidates)
    
    if ai_evaluation.get("error") == "api_key_missing":
        send_telegram("⚠️ <b>Sistem Carl Error:</b> Variabel <code>GEMINI_API_KEY</code> belum dipasang di Railway Carl!")
        return
        
    if ai_evaluation.get("match_found") is True:
        selected_id = ai_evaluation.get("selected_video_id")
        
        # Temukan data objek kandidat asli dari daftar
        selected_video = next((c for c in batch_candidates if c["id"] == selected_id), None)
        
        if selected_video:
            pilar = ai_evaluation.get("pilar", "Pilar Konten")
            reason = ai_evaluation.get("reason", "")
            twist = ai_evaluation.get("twist", "")
            hooks_list = ai_evaluation.get("hooks", [])
            
            hooks_text = ""
            for hk in hooks_list:
                hooks_text += f"• <i>\"{hk}\"</i>\n"
            
            msg = f"🚨 <b>CARL — PILAR MATCH DETECTED!</b>\n\n" \
                  f"🎬 <b>{selected_video['title']}</b>\n" \
                  f"👤 Channel: {selected_video['channel']}\n" \
                  f"🎯 <b>{pilar}</b>\n\n" \
                  f"📌 <b>Kenapa Cocok:</b>\n{reason}\n\n" \
                  f"🔀 <b>Twist Strategy (Untuk Ical):</b>\n{twist}\n\n" \
                  f"🎙 <b>Pragmatic Hooks:</b>\n{hooks_text}\n" \
                  f"🔗 {selected_video['url']}"
            
            callback_data = f"gen_{selected_id}"
            
            VIDEO_CACHE[callback_data] = {
                "title": selected_video['title'], 
                "channel": selected_video['channel'], 
                "video_url": selected_video['url'],
                "twist": twist
            }
            
            send_alert_with_button(msg, callback_data)
        else:
            send_telegram("🌅 <b>Carl Laporan:</b> AI memilih kecocokan tetapi ID video tidak terdaftar dalam kandidat.")
    else:
        send_telegram("🌅 <b>Carl Laporan:</b> Pemindaian selesai. Tidak ada video harian luar yang lolos filter ketat pilar Rizal.")

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
                        if forward_to_magnus(v_info["title"], v_info["channel"], v_info["video_url"], v_info["twist"]):
                            send_telegram(f"✅ Sukses! Strategi twist & data video dikirim ke Magnus.")
                        else:
                            send_telegram(f"⚠️ Gagal mengirim data lewat jalur internal.")
                elif "message" in update and "text" in update["message"]:
                    if update["message"]["text"] == "/run":
                        threading.Thread(target=run_monitor).start()
        except: time.sleep(5)

# ============================================================
# PENJADWAL OTOMATIS (RUNNING AT 08:00 & 20:00 WIB JAKARTA TIME)
# ============================================================
def scheduler_loop():
    """Mengecek waktu setiap menit dan mentrigger Carl otomatis pada jam target"""
    # Menggunakan built-in timezone WIB (UTC+7) tanpa butuh install pytz eksternal
    jakarta_tz = timezone(timedelta(hours=7))
    print("🕒 Penjadwal otomatis Carl diaktifkan untuk jam 08:00 dan 20:00 WIB...")
    
    while True:
        try:
            now = datetime.now(jakarta_tz)
            if now.minute == 0 and (now.hour == 8 or now.hour == 20):
                print(f"⏰ [Scheduler] Memulai screening otomatis terjadwal pada jam {now.strftime('%H:%M WIB')}")
                threading.Thread(target=run_monitor).start()
                time.sleep(65)
        except Exception as e:
            print(f"⚠️ Error di sistem penjadwal: {e}")
        time.sleep(30) # Cek kembali setiap 30 detik

if __name__ == "__main__":
    # 1. Jalankan polling Telegram Carl
    threading.Thread(target=poll_carl, daemon=True).start()
    
    # 2. Jalankan thread penjadwal otomatis jam 8 pagi dan malam
    threading.Thread(target=scheduler_loop, daemon=True).start()
    
    # 3. Jalankan sekali pas startup biar Rizal tahu Carl-nya aktif mendeteksi
    run_monitor()
    
    # Jaga agar program utama tetap hidup
    while True: 
        time.sleep(3600)
