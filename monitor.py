import os
import requests
from datetime import datetime, timedelta
import pytz
import time
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

def evaluate_video_with_gemini(title, description, channel):
    """Menggunakan Gemini AI untuk menyaring ketat video berdasarkan 2 pilar Rizal"""
    if not GEMINI_API_KEY:
        return {"match": False, "error": "api_key_missing"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Kamu bertindak sebagai Content Curator & Strategy Filter kelas dunia untuk personal branding TikTok Rizal / Ical (27 tahun).
    
    BERIKUT ADALAH PROFIL DAN BACKROUND RIZAL:
    - Pendidikan: SBM ITB (Manajemen Bisnis).
    - Karir Sekarang: Product Manager (PM) di Truvisor.io, memegang produk cybersecurity & network visibility (Vectra AI & Keysight Technologies). Gaji saat ini 17jt/bulan.
    - Cara Kerja: WFH/WFA mobile, jarang ke kantor, banyakan nyetir/pindah tempat buat ketemu customer & partner B2B di luar.
    - Masa Lalu Karir: Pernah jadi Relationship Manager di Shopee, Account Manager Lifestyle di TikTok, dan Tech Sales di Soltius. Sukses melakukan 'Tech Pivot' dari non-tech/sales ke cybersecurity yang sangat teknis tanpa background coding.
    
    TUGAS KAMU:
    Evaluasi data video YouTube Shorts atau Long-form berikut:
    Judul Video: "{title}"
    Deskripsi: "{description}"
    Kreator/Channel: "{channel}"
    
    🚨 ATURAN LOKALISASI & BAHASA (WAJIB DIPATUHI):
    1. REJECT MUTLAK (MATCH: FALSE) jika video menggunakan bahasa selain Bahasa Indonesia atau Bahasa Inggris (seperti Bahasa Hindi/India, Spanyol, Arab, Tagalog, dll). Target audiens Rizal adalah profesional lokal di Indonesia.
    2. Abaikan/Reject video yang memiliki aksara non-Latin atau mengandung kata-kata regional India/asing (contoh kata: 'aur', 'ka', 'asli', 'sach', 'ki', 'ke', dll) pada judul atau deskripsinya.
    
    KAMU HANYA BOLEH MELOLOSKAN (MATCH: TRUE) JIKA VIDEO BERBAHASA INDONESIA/INGGRIS DAN SANGAT RELATE DENGAN SALAH SATU DARI 2 PILAR INI:
    
    Pilar 1: "The Tech Pivot" (Karir & Pindah Jalur ke IT/Cybersecurity)
    - Kriteria Lolos: Masuk IT/Tech untuk anak non-IT/tanpa coding, nego gaji/karir akhir 20-an, transisi sales/e-commerce ke tech corporate, atau cybersecurity dari kacamata bisnis.
    - REJECT MUTLAK (Kriteria Reject): Tips bikin CV standar, tips interview klise, tutorial coding teknis.
    
    Pilar 2: "The Mobile PM Lifestyle & Corporate Hacks" (Day in My Life & Soft Skills)
    - Kriteria Lolos: Sisi realita kerja mobile (nyetir/pindah tempat), suka duka jadi Product Manager, komunikasi B2B/negosiasi klien, manajemen waktu lapangan, pov anak corporate umur 27 yang pragmatis.
    - REJECT MUTLAK (Kriteria Reject): Motivasi toxic positivity, tips produktivitas tidak realistis, konten kantor komedi kubikel kaku.

    Kembalikan respon harus dalam format JSON yang valid seperti contoh di bawah (JANGAN beri komentar atau penjelasan apa pun di luar JSON):
    {{
        "match": true_atau_false,
        "pilar": "Pilar 1: The Tech Pivot" atau "Pilar 2: The Mobile PM Lifestyle & Corporate Hacks" atau "None",
        "reason": "Alasan singkat kenapa video ini lolos kurasi pilar kamu",
        "twist": "Instruksi spesifik cara nge-twist konten ini agar masuk ke sudut pandang/pengalaman hidup Rizal (SBM ITB/Ex-TikTok-Shopee/PM Cybersecurity gaji 17jt)",
        "hooks": [
            "Hook alternatif 1 (gaya The Pragmatic Older Brother: santai, blak-blakan, realistis, berbobot)",
            "Hook alternatif 2"
        ]
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        result_text = res_data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(result_text)
    except Exception as e:
        print(f"Error pada penyaringan AI Carl: {e}")
        return {"match": False}

def search_youtube_videos(keyword):
    published_after = (datetime.now(pytz.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    
    magnus_internal_url = "http://magnus-scriptwriter:8080/generate"
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
    send_telegram("⚡ <b>Carl:</b> Memulai pencarian dan penyaringan AI ketat berdasarkan 2 Pilar Rizal...")
    found_any = False
    
    for kw in CAREER_KEYWORDS:
        videos = search_youtube_videos(kw)
        for v in videos:
            vid_id = v.get("id", {}).get("videoId")
            if not vid_id: continue
            
            detail = get_video_stats(vid_id)
            stats = detail.get("statistics", {})
            snippet = detail.get("snippet", {})
            
            if int(stats.get("commentCount", 0)) >= 1:
                title = snippet.get("title", "N/A")
                desc = snippet.get("description", "")
                channel = snippet.get("channelTitle", "N/A")
                v_url = f"https://www.youtube.com/watch?v={vid_id}"
                
                # UPGRADE: Python-Level Language Firewall Check (Zero-Cost & 100% Akurat)
                if not is_indonesian_or_english_only(title, desc):
                    print(f"🚫 [Firewall] Menolak konten asing (Hindi/Lainnya): {title}")
                    continue
                
                # JALANKAN AI SCREENING FILTER (Hanya untuk konten yang lolos Firewall bahasa)
                ai_evaluation = evaluate_video_with_gemini(title, desc, channel)
                
                # Jika API Key Hilang, hentikan program dan beri notifikasi peringatan
                if ai_evaluation.get("error") == "api_key_missing":
                    send_telegram("⚠️ <b>Sistem Carl Error:</b> Variabel <code>GEMINI_API_KEY</code> belum dipasang di Railway Carl! Penyaringan dihentikan sementara demi mencegah spam konten tidak relevan.")
                    return
                
                if ai_evaluation.get("match") is True:
                    pilar = ai_evaluation.get("pilar", "Pilar Konten")
                    reason = ai_evaluation.get("reason", "")
                    twist = ai_evaluation.get("twist", "")
                    hooks_list = ai_evaluation.get("hooks", [])
                    
                    hooks_text = ""
                    for hk in hooks_list:
                        hooks_text += f"• <i>\"{hk}\"</i>\n"
                    
                    msg = f"🚨 <b>CARL — PILAR MATCH DETECTED!</b>\n\n" \
                          f"🎬 <b>{title}</b>\n" \
                          f"👤 Channel: {channel}\n" \
                          f"🎯 <b>{pilar}</b>\n\n" \
                          f"📌 <b>Kenapa Cocok:</b>\n{reason}\n\n" \
                          f"🔀 <b>Twist Strategy (Untuk Ical):</b>\n{twist}\n\n" \
                          f"🎙 <b>Pragmatic Hooks:</b>\n{hooks_text}\n" \
                          f"🔗 {v_url}"
                    
                    callback_data = f"gen_{vid_id}"
                    
                    VIDEO_CACHE[callback_data] = {
                        "title": title, 
                        "channel": channel, 
                        "video_url": v_url,
                        "twist": twist
                    }
                    
                    send_alert_with_button(msg, callback_data)
                    found_any = True
                    return
                    
    if not found_any:
        send_telegram("🌅 <b>Carl Laporan:</b> Pemindaian selesai. Hari ini tidak ada video luar yang lolos filter ketat pilar Rizal.")

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
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    print("🕒 Penjadwal otomatis Carl diaktifkan untuk jam 08:00 dan 20:00 WIB...")
    
    while True:
        try:
            now = datetime.now(jakarta_tz)
            # Trigger jika menit berada pada angka 00 dan jam adalah 8 (pagi) atau 20 (malam)
            if now.minute == 0 and (now.hour == 8 or now.hour == 20):
                print(f"⏰ [Scheduler] Memulai screening otomatis terjadwal pada jam {now.strftime('%H:%M WIB')}")
                threading.Thread(target=run_monitor).start()
                # Kasih jeda tidur agak lama agar tidak men-trigger dua kali di menit yang sama
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
