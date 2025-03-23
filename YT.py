import torch
import sys
import moviepy
import os
import requests
import json
import pytz
import collections
import re
import numpy as np
from datetime import datetime, time
from together import Together
from pytrends.request import TrendReq
from pydub.effects import normalize
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx import fadein, fadeout
from PIL import Image, ImageDraw, ImageFont
from bark import generate_audio
from scipy.io.wavfile import write
from pydub import AudioSegment, effects
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

SHORTS_DURATION=59
LONG_VIDEO_DURATION=600
VIDEO_QUALITY="4K"
SHORTS_UPLOAD_TIME_UTC = time(15, 0)  # ساعت ۳ بعدازظهر UTC
LONG_VIDEO_UPLOAD_TIME_UTC= time(12, 0)  # ساعت ۱۲ ظهر UTC


# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # می‌تونی آی‌دی صدای مورد علاقه‌ات رو جایگزین کنی
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    print("❌ Error: YOUTUBE_API_KEY is missing! Check your environment variables.")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # گرفتن API Key از متغیر محیطی
PEXELS_URL = "https://api.pexels.com/v1/search"
CHANNEL_ID = "UCa4J9qWMutBboFsyqd-pS2A"



# YouTube API URLs
TOKEN_URL = "https://oauth2.googleapis.com/token"
METADATA_URL = "https://www.googleapis.com/youtube/v3/videos"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

# تنظیم منطقه زمانی به Eastern Time (ET)
EST = pytz.timezone('America/New_York')

# فایل لاگ برای ذخیره تاریخ آخرین آپلود
UPLOAD_LOG_FILE = "upload_log.json"

# مسیر ویدیوها (نام فایل‌ها را با ویدیوهای واقعی جایگزین کن)
LONG_VIDEO_FILE = "long_video.mp4"  # ویدیوی 5 تا 10 دقیقه‌ای
SHORT_VIDEO_FILE = "short_video.mp4"  # ویدیوی Shorts

# تعداد آپلودها در روز
MAX_LONG_UPLOADS = 1  # فقط 1 ویدیوی بلند در روز
MAX_SHORTS_UPLOADS = 1  # فقط 1 Shorts در روز

def fetch_youtube_trending(region_code="US", max_results=10):
    if not YOUTUBE_API_KEY:
        print("❌ Error: YouTube API Key is missing!")
        return []

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        trending_videos = response.json().get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []

    trending_topics = []
    for rank, video in enumerate(trending_videos, start=1):
        try:
            title = video["snippet"]["title"]
            description = video["snippet"]["description"]
            channel = video["snippet"]["channelTitle"]
            video_id = video["id"]
            view_count = int(video["statistics"].get("viewCount", 0))
            like_count = int(video["statistics"].get("likeCount", 0))
            thumbnail = video["snippet"]["thumbnails"]["high"]["url"]

            # مقیاس محبوبیت بر اساس بازدید و لایک (بین ۰ تا ۱۰۰)
            popularity = min(100, (view_count // 10000) + (like_count // 500))

            # فقط ویدیوهای با محبوبیت بالا در نظر گرفته شوند
            if popularity >= 10:
                trending_topics.append({
                    "rank": rank,
                    "title": title,
                    "description": description,
                    "channel": channel,
                    "video_id": video_id,
                    "view_count": view_count,
                    "like_count": like_count,
                    "popularity": popularity,
                    "thumbnail": thumbnail,
                    "region": region_code
                })
        except KeyError as e:
            print(f"⚠️ Missing key {e} for video: {video.get('id', 'Unknown')}")

    if not trending_topics:
        print("⚠ No trending videos found with enough popularity.")

    return trending_topics

def fetch_reddit_trends(subreddits=["gaming"], limit=10, time_period="day"):
    """ دریافت پست‌های پرطرفدار از چندین Reddit subreddit بدون ذخیره‌سازی """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    reddit_trends = []

    for subreddit in subreddits:
        url = f"https://www.reddit.com/r/{subreddit}/top.json?t={time_period}&limit={limit}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:  # جلوگیری از بلاک شدن
                print(f"⚠ Rate limit hit! Sleeping for 10 seconds...")
                time.sleep(10)
                continue

            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching Reddit trends for {subreddit}: {e}")
            continue
        except ValueError:
            print(f"❌ Error decoding JSON response from Reddit ({subreddit})!")
            continue

        posts = data.get("data", {}).get("children", [])
        if not posts:
            print(f"⚠ No trending posts found on r/{subreddit}!")
            continue

        max_score = max((post["data"].get("score", 1) for post in posts), default=1)

        for post in posts:
            post_data = post["data"]
            title = post_data.get("title", "Unknown Title")
            post_id = post_data.get("id", "")
            url = f"https://www.reddit.com{post_data.get('permalink', '')}"
            score = post_data.get("score", 0)

            # محاسبه محبوبیت (با حداقل 1000 امتیاز برای محبوبیت 100%)
            popularity = min(100, (score / max(1000, max_score)) * 100)

            reddit_trends.append({
                "title": title,
                "post_id": post_id,
                "url": url,
                "subreddit": subreddit,
                "source": "Reddit",
                "popularity": round(popularity, 2)
            })

    if not reddit_trends:
        print("⚠ No Reddit trends found with enough popularity.")
    
    return reddit_trends

def fetch_all_trends(region_code="US", reddit_subreddits=["gaming"], reddit_limit=10, time_period="day"):
    """ دریافت و ترکیب داده‌های ترند از یوتیوب و ردیت بدون ذخیره‌سازی """

    print("🔍 Fetching YouTube Trends...")
    youtube_trends = fetch_youtube_trending(region_code)

    print("🔍 Fetching Reddit Trends...")
    reddit_trends = fetch_reddit_trends(reddit_subreddits, reddit_limit, time_period)

    # ترکیب همه ترندها در یک لیست
    all_trends = youtube_trends + reddit_trends

    if not all_trends:
        print("⚠ No trending data found.")
    
    return all_trends

def select_best_trending_topic(trends):
    """ انتخاب بهترین موضوع ترند شده از لیست یوتیوب و ردیت، بر اساس تعداد تکرار و محبوبیت """

    if not trends or not isinstance(trends, list):
        print("❌ No trending topics found or invalid format.")
        return None

    # ✅ فیلتر داده‌های نامعتبر (باید حداقل 'title' و 'source' داشته باشند)
    valid_trends = [t for t in trends if isinstance(t, dict) and "title" in t and "source" in t]

    if not valid_trends:
        print("❌ No valid trending topics found.")
        return None

    # ✅ وزن‌دهی به منابع مختلف
    source_weights = {
        "YouTube": 2,  # یوتیوب ارزش بیشتری دارد
        "Reddit": 1    # ردیت وزن پایین‌تری دارد
    }

    # شمارش و امتیازدهی به هر عنوان
    topic_scores = collections.defaultdict(int)

    for trend in valid_trends:
        title = trend["title"]
        source = trend["source"]
        popularity = trend.get("popularity", 0)  # امتیاز محبوبیت اگر وجود داشته باشد
        weight = source_weights.get(source, 1)  # وزن پیش‌فرض ۱ اگر منبع ناشناخته باشد

        topic_scores[title] += weight * (1 + (popularity / 100))  # امتیاز نهایی

    # مرتب‌سازی بر اساس امتیاز نهایی
    sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)

    # ✅ اولویت‌بندی موضوعات مرتبط
    keywords = ["minecraft", "gaming", "ai", "technology", "computers", "knowledge"]

    for topic, score in sorted_topics:
        if any(re.search(rf"\b{re.escape(keyword)}\b", topic, re.IGNORECASE) for keyword in keywords):
            print(f"✅ Best topic selected: {topic} (Score: {score:.2f})")
            return topic

    # در صورت نبودن موضوع مرتبط، انتخاب موضوع پرامتیازتر
    best_fallback_topic = sorted_topics[0][0] if sorted_topics else None
    if best_fallback_topic:
        print(f"⚠ No suitable trending topic found. Using top topic: {best_fallback_topic}")

    return best_fallback_topic

# 🚀 اجرای تابع
trending_data = fetch_all_trends()
best_topic = select_best_trending_topic(trending_data)
trends = fetch_all_trending_topics()  # Fetch trending topics
topic = select_best_trending_topic(trends)  # ✅ Pass `trends` as argument

def download_best_minecraft_background(output_video="background.mp4"):
   #دانلود بهترین ویدیو گیم‌پلی ماینکرفت از Pixabay و ذخیره آن
    
    # دریافت کلید API از متغیر محیطی
    PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", None)
    PIXABAY_URL = "https://pixabay.com/api/videos/"

    if not PIXABAY_API_KEY:
        print("❌ ERROR: Pixabay API Key is missing! Set 'PIXABAY_API_KEY' in Railway environment variables.")
        return None
    
    params = {
        "key": PIXABAY_API_KEY,
        "q": "Minecraft gameplay",
        "video_type": "film",
        "per_page": 10  # دریافت 10 ویدیو برتر
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(PIXABAY_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # بررسی خطاهای HTTP
        data = response.json()
        
        if not data.get("hits"):
            print("❌ No Minecraft videos found on Pixabay.")
            return None

        # مرتب‌سازی ویدیوها بر اساس کیفیت (عرض) و طول ویدیو (حداقل 10 ثانیه)
        sorted_videos = sorted(
            [vid for vid in data["hits"] if vid["duration"] >= 10], 
            key=lambda vid: (vid["videos"]["medium"]["width"], vid["duration"]), 
            reverse=True
        )

        if not sorted_videos:
            print("❌ No suitable videos found (videos too short).")
            return None

        best_video_url = sorted_videos[0]["videos"]["medium"]["url"]  # لینک بهترین ویدیو
        print(f"✅ Selected best video: {best_video_url}")

        # دانلود ویدیو با استریم
        video_response = requests.get(best_video_url, stream=True, timeout=20)
        video_response.raise_for_status()

        with open(output_video, "wb") as f:
            total_size = int(video_response.headers.get("content-length", 0))
            downloaded_size = 0

            for chunk in video_response.iter_content(chunk_size=1024 * 1024):  # 1MB
                f.write(chunk)
                downloaded_size += len(chunk)

            # بررسی حجم دانلود شده
            if total_size > 0 and downloaded_size < total_size * 0.9:  # اگر کمتر از 90٪ حجم دانلود شد
                print("⚠ WARNING: Video download may be incomplete.")

        print(f"✅ Downloaded best background video: {output_video}")
        return output_video

    except requests.RequestException as e:
        print(f"❌ Error fetching or downloading video: {e}")
        return None

# تست دانلود بهترین ویدیو
download_best_minecraft_background()

def generate_video_script(topic):
    if not topic:
        print("❌ Error: No topic provided!")
        return None

    # Get API key from Railway environment variables
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
    if not TOGETHER_API_KEY:
        print("❌ Error: Missing TOGETHER_API_KEY key!")
        return None

    # Initialize the Together AI client
    client = Together(api_key=TOGETHER_API_KEY)

    prompt = f"""
    Generate a high-engagement YouTube video script about "{topic}" in an engaging, viral style.
    The script should follow this structure:

    1️⃣ **Hook (First 5-10 sec)**: Start with a shocking fact, bold statement, or an intriguing question.
    2️⃣ **Main Content (70%)**: Explain the topic in an exciting and easy-to-understand way, just like a famous YouTuber.
    3️⃣ **Call to Action (Last 10 sec)**: Encourage viewers to like, comment, and subscribe, but make it feel natural.

    - The language should be **fun, casual, and highly engaging**.
    - Keep sentences short and dynamic.
    - Avoid robotic or overly formal tones.
    - Use rhetorical questions and direct audience engagement.

    Now, generate a **high-quality, viral** YouTube script for: "{topic}".
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",  # Corrected model name
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=700
        )

        # Extract the generated script
        script = response.choices[0].message.content.strip()

        if not script:
            print("❌ Error: No script received from API")
            return None

        return script

    except Exception as e:
        print(f"❌ API Request Error: {e}")
        return None

# Get API key from Railway environment variables
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "MISSING_API_KEY")

if TOGETHER_API_KEY == "MISSING_API_KEY":
    print("❌ ERROR: Together AI API Key is missing! Set 'TOGETHER_API_KEY' in Railway environment variables.")
    exit(1)

# Initialize the Together client with the API key
client = Together(api_key=TOGETHER_API_KEY)

def generate_video_metadata(topic):
    print("📝 Generating video metadata...")

    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "MISSING_API_KEY")
    if TOGETHER_API_KEY == "MISSING_API_KEY":
        print("❌ ERROR: Together AI API Key is missing! Set 'TOGETHER_API_KEY' in Railway environment variables.")
        return None

    client = Together(api_key=TOGETHER_API_KEY)

    prompt = f"""
    Generate an engaging YouTube video title, description, and relevant hashtags for a video about "{topic}".
    
    - The title should be eye-catching and optimized for high CTR.
    - The description should include a short summary of the video, a call to action, and links.
    - The hashtags should be relevant and increase discoverability.
    
    Return the output in **valid JSON format** with keys: "title", "description", and "hashtags".
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )

        # Debugging: Print raw API response
        print("🔍 Raw API Response:", response)

        # Extract content
        content = response.choices[0].message.content.strip()

        # Debugging: Print extracted content
        print("📜 Extracted Content:", content)

        # Try parsing as JSON
        try:
            metadata = json.loads(content)
            if not all(key in metadata for key in ["title", "description", "hashtags"]):
                raise ValueError("Missing expected keys in JSON")
        except (json.JSONDecodeError, ValueError):
            print("⚠ Warning: Invalid JSON received. Using default metadata.")
            metadata = {
                "title": f"Awesome Video About {topic}!",
                "description": f"This video is all about {topic}. Stay tuned for more!",
                "hashtags": "#YouTube #Trending"
            }

        print("✅ Video metadata generated successfully!")
        return metadata

    except Exception as e:
        print("❌ Error generating metadata:", str(e))
        return None

def generate_voiceover(script, output_audio="voiceover.wav"):
    if not script or not isinstance(script, str):
        print("❌ Error: Invalid script provided!")
        return None

    try:
        audio_array = generate_audio(script)  # Bark-based voice generation
        
        if not isinstance(audio_array, np.ndarray) or audio_array.size == 0:
            print("❌ Error: No audio generated.")
            return None
        
        sample_rate = 24000
        write(output_audio, sample_rate, np.array(audio_array * 32767, dtype=np.int16))
        
        print(f"✅ Voiceover generated successfully: {output_audio}")
        return output_audio

    except Exception as e:
        print(f"❌ Error generating voiceover: {str(e)}")
        return None

def generate_video(voiceover, background_video, output_video="final_video.mp4"):
    if not os.path.isfile(voiceover):
        print(f"❌ Error: Voiceover file not found ({voiceover})")
        return None

    if not os.path.isfile(background_video):
        print(f"❌ Error: Background video file not found ({background_video})")
        return None

    try:
        command = [
            "ffmpeg", "-y",
            "-i", background_video,
            "-i", voiceover,
            "-c:v", "copy",
            "-c:a", "aac",
            output_video
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if not os.path.isfile(output_video):
            print("❌ Error: Video file not created.")
            return None

        print(f"✅ Video generated successfully: {output_video}")
        return output_video

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error: {e.stderr.decode('utf-8', errors='ignore')}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def enhance_audio(input_audio, output_audio="enhanced_voiceover.mp3"):
    if not os.path.isfile(input_audio):
        print(f"❌ Error: Input audio file not found ({input_audio})")
        return None

    try:
        audio = AudioSegment.from_file(input_audio)

        # نرمال‌سازی صدا برای بالانس کردن حجم صدا
        enhanced_audio = effects.normalize(audio)

        # حذف نویز‌های کم‌دامنه (فیلتر high-pass)
        enhanced_audio = enhanced_audio.high_pass_filter(100)

        # تنظیم مقدار بلندی صدا در حد متعادل
        target_dBFS = -14.0
        change_in_dBFS = target_dBFS - enhanced_audio.dBFS
        enhanced_audio = enhanced_audio.apply_gain(change_in_dBFS)

        # ذخیره خروجی با کیفیت بالا
        enhanced_audio.export(output_audio, format="mp3", bitrate="192k")

        if not os.path.isfile(output_audio):
            print("❌ Error: Enhanced audio file not created.")
            return None

        print(f"✅ Enhanced audio saved: {output_audio}")
        return output_audio

    except Exception as e:
        print(f"❌ Error enhancing audio: {e}")
        return None

def enhance_video(input_video, output_video="enhanced_video.mp4"):
    if not os.path.isfile(input_video):
        print(f"❌ Error: Input video file not found ({input_video})")
        return None

    try:
        clip = VideoFileClip(input_video)

        # ایجاد متن عنوان با پس‌زمینه‌ی نیمه‌شفاف
        title_text = (TextClip("🔥 Minecraft Fact!", fontsize=70, font="Arial-Bold", color="white", stroke_color="black", stroke_width=3)
                      .set_position(("center", "top"))
                      .set_duration(3))

        # ترکیب متن با ویدیو
        final_clip = CompositeVideoClip([clip, title_text])

        # ذخیره خروجی با کیفیت بالا
        final_clip.write_videofile(output_video, codec="libx264", fps=30, threads=4, preset="ultrafast")

        if not os.path.isfile(output_video):
            print("❌ Error: Enhanced video file not created.")
            return None

        print(f"✅ Enhanced video saved: {output_video}")
        return output_video

    except Exception as e:
        print(f"❌ Error enhancing video: {e}")
        return None

def add_video_effects(input_video, output_video="final_video_with_effects.mp4"):
    print("🎬 Adding effects to video...")

    if not os.path.isfile(input_video):
        print(f"❌ Error: Input video file not found ({input_video})")
        return None

    try:
        # بارگذاری ویدیو
        clip = VideoFileClip(input_video)

        # ایجاد متن گرافیکی متحرک با افکت استروک (حاشیه مشکی برای خوانایی بهتر)
        txt_clip = (TextClip("🔥 Amazing Minecraft Fact!", fontsize=80, color='yellow', font="Arial-Bold",
                             stroke_color="black", stroke_width=5)
                    .set_position(("center", "top"))
                    .set_duration(3)
                    .fadein(0.5).fadeout(0.5))  # افکت محو شدن در ابتدا و انتها

        # ترکیب ویدیو و متن
        final_clip = CompositeVideoClip([clip, txt_clip])

        # ذخیره ویدیو با تنظیمات بهینه
        final_clip.write_videofile(output_video, codec="libx264", fps=30, threads=4, preset="ultrafast")

        if not os.path.isfile(output_video):
            print("❌ Error: Video with effects was not created.")
            return None

        print(f"✅ Video with effects saved: {output_video}")
        return output_video

    except Exception as e:
        print(f"❌ Error adding effects to video: {e}")
        return None

def generate_thumbnail(topic, output_file="thumbnail.jpg"):
    print("🖼 Generating thumbnail using Pexels...")

    if not PEXELS_API_KEY:
        print("❌ ERROR: Pexels API Key is missing! Set 'PEXELS_API_KEY' in environment variables.")
        return None

    # 🔍 جستجوی تصویر مرتبط در Pexels
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": topic, "per_page": 1}
    response = requests.get(PEXELS_URL, headers=headers, params=params)

    if response.status_code != 200:
        print("❌ ERROR: Failed to fetch image from Pexels!")
        return None

    data = response.json()
    if "photos" not in data or len(data["photos"]) == 0:
        print("⚠ No images found for this topic. Using default image.")
        return None

    image_url = data["photos"][0]["src"]["large"]
    
    # 📥 دانلود تصویر
    img = Image.open(requests.get(image_url, stream=True).raw)

    # 🖌 اضافه کردن متن روی تصویر
    draw = ImageDraw.Draw(img)
    FONT_PATH = os.path.join(os.path.dirname(__file__), "impact.ttf")
    try:
        font = ImageFont.truetype(FONT_PATH, 90)  # فونت اینستاگرامی معروف
    except OSError:
        print("⚠️ Font not found, using default font.")
        font = ImageFont.load_default()
    
    text_position = (100, img.height - 150)
    
    # 🖌 افکت استروک برای خوانایی بهتر
    for offset in range(-3, 4, 2):
        draw.text((text_position[0] + offset, text_position[1]), topic, font=font, fill="black")
        draw.text((text_position[0], text_position[1] + offset), topic, font=font, fill="black")

    draw.text(text_position, topic, font=font, fill="yellow")

    # 💾 ذخیره‌ی تامبنیل نهایی
    img.save(output_file)
    print(f"✅ Thumbnail saved as {output_file}")
    return output_file

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # باید API Key ست بشه

def analyze_past_videos():
    print("📊 Analyzing past video performance...")

    if not YOUTUBE_API_KEY:
        print("❌ ERROR: YouTube API Key is missing! Set 'YOUTUBE_API_KEY' in environment variables.")
        return None

    # دریافت اطلاعات کانال (بدون نیاز به CHANNEL_ID)
    channel_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true&key={YOUTUBE_API_KEY}"
    channel_response = requests.get(channel_url)

    if channel_response.status_code != 200:
        print("❌ ERROR: Failed to fetch channel details!")
        return None

    uploads_playlist_id = channel_response.json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # دریافت لیست ویدیوها از آپلودهای کانال
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={uploads_playlist_id}&maxResults=20&key={YOUTUBE_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        print("❌ ERROR: Failed to fetch video list from YouTube!")
        return None

    video_ids = [item["contentDetails"]["videoId"] for item in response.json().get("items", [])]

    if not video_ids:
        print("⚠ No videos found.")
        return None

    # دریافت آمار ویدیوها
    stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={','.join(video_ids)}&key={YOUTUBE_API_KEY}"
    stats_response = requests.get(stats_url)

    if stats_response.status_code != 200:
        print("❌ ERROR: Failed to fetch video stats!")
        return None

    stats_data = stats_response.json().get("items", [])

    engagement_data = []
    for video in stats_data:
        vid_id = video["id"]
        stats = video["statistics"]

        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        views = int(stats.get("viewCount", 1))  # جلوگیری از تقسیم بر صفر

        engagement_rate = (likes + comments) / views
        engagement_data.append((vid_id, engagement_rate))

    best_videos = sorted(engagement_data, key=lambda x: x[1], reverse=True)

    print("\n🔥 **Top Performing Videos:**")
    for vid_id, rate in best_videos[:5]:
        print(f"- Video ID: {vid_id}, Engagement Rate: {rate:.2%}")

    return best_videos[:5]

def suggest_improvements():
    
    #پیشنهاد بهینه‌سازی استراتژی ویدیو بر اساس ویدیوهای موفق قبلی.
    
    best_videos = analyze_past_videos()
    
    if not best_videos:
        print("⚠ Not enough data to suggest improvements.")
        return

    engagement_rates = [vid[1]["engagement_rate"] for vid in best_videos]
    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

    print(f"\n📊 **Average Engagement Rate:** {avg_engagement:.2%}")

    if avg_engagement < 0.03:
        print("⚠ Engagement rate is low. Consider experimenting with different topics and styles.")
    else:
        print("\n🎯 **Suggested Video Strategies Based on Past Success:**")
        print("- Use more engaging hooks in the first 5 seconds.")
        print("- Focus on topics similar to high-performing videos.")
        print("- Encourage more comments by asking interactive questions.")
        print("- Test different thumbnail styles (e.g., bold text, bright colors).")
        
    script= generate_video_script(topic)

def check_copyright_violation(script):
    prompt = f"""
    Analyze the following script for potential copyright violations or plagiarism.
    - If the script is 100% original and safe, return: "SAFE".
    - If there are any potential copyright risks, return a short explanation.

    Script:
    {script}
    """
    
    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250
        )
        result = response["choices"][0]["message"]["content"]
        
        if "SAFE" in result:
            return True
        else:
            print(f"⚠ Potential copyright issue detected: {result}")
            return False
    except Exception as e:
        print("❌ Error checking copyright:", str(e))
        return True  # اگر نتوانست بررسی کند، اجازه می‌دهیم ادامه دهد


def check_and_fix_youtube_metadata(video_metadata):
    """
    بررسی و اصلاح خودکار متادیتای یوتیوب قبل از آپلود.
    """
    title = video_metadata["title"]
    description = video_metadata["description"]

    prompt = f"""
    Analyze the following YouTube video metadata to ensure it fully complies with YouTube’s policies.
    - If it's 100% safe, return: "SAFE".
    - If it contains potential violations, rewrite it to make it fully compliant.
    
    Title: {title}
    Description: {description}
    
    If you rewrite it, return ONLY the fixed metadata in this format:
    Title: [NEW TITLE]
    Description: [NEW DESCRIPTION]
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        result = response["choices"][0]["message"]["content"]

        if "SAFE" in result:
            print("✅ Metadata is safe.")
            return video_metadata  # بدون تغییر ادامه بده

        # استخراج عنوان و توضیحات جدید از پاسخ مدل
        fixed_title = result.split("Title: ")[1].split("\n")[0]
        fixed_description = result.split("Description: ")[1].strip()

        print(f"✅ Fixed Title: {fixed_title}")
        print(f"✅ Fixed Description: {fixed_description}")

        # جایگزینی متادیتای اصلاح‌شده
        video_metadata["title"] = fixed_title
        video_metadata["description"] = fixed_description

        return video_metadata  # با متادیتای اصلاح‌شده ادامه بده

    except Exception as e:
        print("❌ Error checking/fixing metadata:", str(e))
        return video_metadata  # اگر خطا پیش آمد، آپلود را متوقف نکن

# استفاده از بررسی و اصلاح خودکار قبل از آپلود
video_metadata = generate_video_metadata(topic)
video_metadata = check_and_fix_youtube_metadata(video_metadata)

upload_video(enhanced_video, video_metadata)

def check_upload_limit():
    today = datetime.now(timezone.utc).isoformat()[:10]  # تاریخ امروز به فرمت YYYY-MM-DD

    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={CHANNEL_ID}&maxResults=50&order=date&type=video&publishedAfter={today}T00:00:00Z&key={YOUTUBE_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        print("❌ ERROR: Failed to fetch upload history from YouTube!")
        return {"long_videos": 0, "shorts": 0}  # در صورت خطا، فرض می‌کنیم هیچ ویدیویی آپلود نشده

    videos = response.json().get("items", [])

    long_videos = sum(1 for v in videos if "shorts" not in v["snippet"]["title"].lower())  # تشخیص ویدیوهای عادی
    shorts = sum(1 for v in videos if "shorts" in v["snippet"]["title"].lower())  # تشخیص YouTube Shorts

    return {"long_videos": long_videos, "shorts": shorts}

# بررسی ساعت مجاز برای آپلود
def get_upload_type():
    now = datetime.now(EST)
    hour = now.hour

    if 7 <= hour <= 9:
        return "long_videos"  # زمان آپلود ویدیوی بلند
    elif 11 <= hour <= 15:
        return "shorts"  # زمان آپلود Shorts
    return None

# دریافت access token
def get_access_token():
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(TOKEN_URL, data=data)
    response_json = response.json()
    if response.status_code != 200 or "access_token" not in response_json:
        raise Exception("Failed to get access token: " + str(response_json))
    return response_json.get("access_token")

# آپلود متادیتا و دریافت video_id
def upload_metadata(title, description, category_id=24, privacy_status="public"):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {"part": "snippet,status"}
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id  # Ensure categoryId is int
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    metadata_response = requests.post(METADATA_URL, headers=headers, params=params, json=metadata)
    if metadata_response.status_code != 200:
        print("Error uploading metadata:", metadata_response.json())
        return None
    return metadata_response.json().get("id")

# آپلود ویدیو
def upload_video(video_file, video_id):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(os.path.getsize(video_file))
    }
    init_request = requests.post(
        f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        headers=headers
    )
    if init_request.status_code != 200:
        print("Error initializing upload:", init_request.json())
        return
    upload_url = init_request.headers.get("Location")
    if not upload_url:
        print("Failed to retrieve upload URL")
        return
    with open(video_file, "rb") as file:
        upload_response = requests.put(upload_url, headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4"
        }, data=file)
    print("Upload response:", upload_response.json())

upload_video = upload_video(video_file, video_id)

# اجرای آپلود در زمان مناسب
if __name__ == "__main__":
    print("🚀 Starting the YouTube Auto-Upload Bot...")

    # 1️⃣ تحلیل ویدیوهای قبلی و ارائه پیشنهادات برای بهینه‌سازی
    suggest_improvements()

    # 2️⃣ دریافت و ذخیره‌ی ترندهای مختلف در `trending_topics.json`
    fetch_all_trends()

    # 3️⃣ تحلیل داده‌های ترند و انتخاب بهترین موضوع
    selected_topic = select_best_trending_topic()
    if not selected_topic:
        print("⚠ No suitable topic found, skipping video creation.")
        exit()  # اگر موضوع مناسبی پیدا نشود، اجرا متوقف می‌شود.

    print(f"🔥 Creating a video on: {selected_topic}")

    # 4️⃣ تولید متن ویدیوی جذاب با GPT
    script = generate_video_script(selected_topic)
    if not script:
        print("❌ Script generation failed. Skipping video creation.")
        exit()

    with open("video_script.txt", "w") as file:
        file.write(script)
    print("📜 Video script saved successfully!")

    # 5️⃣ تولید صداگذاری از روی متن
    voiceover = generate_voiceover(script)
    if not voiceover:
        print("❌ Voiceover generation failed. Skipping video creation.")
        exit()

    # 6️⃣ تولید زیرنویس
    subtitles = generate_subtitles(voiceover)

    # 7️⃣ تولید ویدیو نهایی
    final_video = generate_video(voiceover, "minecraft_parkour.mp4")
    if not final_video:
        print("❌ Video generation failed.")
        exit()

    print(f"🎬 Video ready for editing: {final_video}")

    # 8️⃣ بهینه‌سازی صدا و تصویر
    enhanced_voiceover = enhance_audio(voiceover)  # حذف نویز و بهینه‌سازی
    enhanced_video = enhance_video(final_video)  # افزودن افکت‌های گرافیکی

    # 9️⃣ تولید تامبنیل برای ویدیو
    thumbnail = generate_thumbnail(selected_topic)

    # 🔟 اضافه کردن افکت‌های گرافیکی به ویدیو
    final_video_with_effects = add_video_effects(enhanced_video)

    # 📝 تولید متادیتای ویدیو
    video_metadata = generate_video_metadata(selected_topic)
    if not video_metadata:
        video_metadata = {
            "title": f"Awesome Video About {selected_topic}!",
            "description": f"This video is all about {selected_topic}. Stay tuned for more!",
            "hashtags": "#YouTube #Trending"
        }

    title = video_metadata["title"]
    description = video_metadata["description"]
    hashtags = video_metadata["hashtags"]

    # 1️⃣1️⃣ آپلود متادیتای ویدیو و دریافت video_id
    video_id = upload_metadata(title, description, category_id=20, privacy_status="public")
    if not video_id:
        print("❌ Failed to upload metadata, skipping video upload.")
        exit()

    # 1️⃣2️⃣ آپلود ویدیوی نهایی
    upload_video(final_video_with_effects, video_id)

    # 1️⃣3️⃣ بررسی محدودیت‌های آپلود و انجام آن در زمان مناسب
    upload_type = get_upload_type()
    upload_limits = check_upload_limit()
    
    if upload_type and upload_limits[upload_type] < (MAX_LONG_UPLOADS if upload_type == "long_videos" else MAX_SHORTS_UPLOADS):
        print(f"✅ It's time to upload a {upload_type.replace('_', ' ')}. Proceeding with upload.")

        try:
            video_file = LONG_VIDEO_FILE if upload_type == "long_videos" else SHORT_VIDEO_FILE
            category_id = 20  # دسته‌بندی Gaming
            video_id = upload_metadata(title, description, category_id, "public")
            
            if video_id:
                upload_video(video_file, video_id)
                log_upload(upload_type)  # ثبت آپلود در لاگ
        except Exception as e:
            print("❌ An error occurred:", str(e))
    else:
        print("⏳ Either it's not the right time for upload or today's upload limit has been reached.")
