import sys
import moviepy
print("Python path:", sys.path)
print("MoviePy version:", moviepy.__version__)


import os
import requests
import json
import pytz
import collections
import openai
import subprocess
import cv2
import numpy as np
from datetime import datetime
from pytrends.request import TrendReq
from pydub import AudioSegment
from pydub.effects import normalize
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx import fadein, fadeout
from PIL import Image, ImageDraw, ImageFont
# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # می‌تونی آی‌دی صدای مورد علاقه‌ات رو جایگزین کنی

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

def load_trending_topics():
    file_path = "trending_topics.json"
    if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:
        # مقدار پیش‌فرض اگر فایل وجود ندارد یا خالی است
        default_data = [
            {"title": "Minecraft Secrets", "popularity": 95},
            {"title": "AI in 2025", "popularity": 90}
        ]
        with open(file_path, "w") as file:
            json.dump(default_data, file, indent=4)
        return default_data  # مقدار پیش‌فرض را برگردان

    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print("❌ Error: JSON file is corrupted. Resetting it.")
        return load_trending_topics()  # فایل را ریست کن


def fetch_youtube_trending(region_code="US", max_results=10):
    
    #دریافت لیست ویدیوهای پرطرفدار یوتیوب و ذخیره در trending_topics.json

    access_token = get_access_token()
    
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": max_results
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print("❌ Error fetching trending videos:", response.json())
        return []

    trending_videos = response.json().get("items", [])
    trending_topics = []

    for video in trending_videos:
        title = video["snippet"]["title"]
        description = video["snippet"]["description"]
        trending_topics.append({"title": title, "description": description})

    # ذخیره لیست در فایل JSON
    with open("trending_topics.json", "w") as file:
        json.dump(trending_topics, file, indent=2)

    print(f"✅ {len(trending_topics)} trending topics saved in trending_topics.json")

def fetch_google_trends():
    
    #دریافت لیست ترندهای روز از Google Trends
    
    pytrends = TrendReq(hl='en-US', tz=360)  
    pytrends.build_payload(kw_list=["Minecraft", "AI", "Technology"], timeframe="now 1-d", geo="US")  
    
    trending_searches = pytrends.trending_searches(pn="united_states")
    
    if trending_searches is not None and not trending_searches.empty:
        trends = trending_searches[0].tolist()
    else:
        trends = []

    return [{"title": trend, "source": "Google Trends"} for trend in trends]


def fetch_reddit_trends(subreddit="gaming", limit=10):
    
    #دریافت پست‌های ترند از Reddit
    
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Error fetching Reddit trends:", response.json())
        return []

    posts = response.json().get("data", {}).get("children", [])
    reddit_trends = [{"title": post["data"]["title"], "source": "Reddit"} for post in posts]
    return reddit_trends

def fetch_all_trends():
    
    #دریافت و ترکیب داده‌های ترند از یوتیوب، گوگل ترندز، و ردیت
    
    print("🔍 Fetching trending topics from multiple sources...")
    
    youtube_trends = fetch_youtube_trending()
    google_trends = fetch_google_trends()
    reddit_trends = fetch_reddit_trends()

    all_trends = youtube_trends + google_trends + reddit_trends  # ترکیب داده‌های ترند
    with open("trending_topics.json", "w") as file:
        json.dump(all_trends, file, indent=2)

    print(f"✅ {len(all_trends)} trending topics saved in trending_topics.json")

def select_best_trending_topic():
    
    #تحلیل داده‌های ترند و انتخاب بهترین موضوع برای تولید ویدیو.
    
    # بارگذاری داده‌ها از trending_topics.json
    try:
        with open("trending_topics.json", "r") as file:
            trends = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print("❌ Error: trending_topics.json not found or contains invalid JSON.")
        return None

    if not trends:
        print("❌ No trending topics found.")
        return None

    # فیلتر کردن داده‌های نامعتبر
    valid_trends = [t for t in trends if isinstance(t, dict) and "topic" in t]

    if not valid_trends:
        print("❌ No valid trending topics found.")
        return None

    # شمارش میزان تکرار موضوعات در منابع مختلف
    topic_count = collections.Counter([t["topic"] for t in valid_trends])

    # مرتب‌سازی بر اساس بیشترین تکرار
    sorted_topics = sorted(topic_count.items(), key=lambda x: x[1], reverse=True)

    # انتخاب اولین موضوع مرتبط با Minecraft, AI, یا Gaming
    keywords = ["minecraft", "knowledge", "gaming", "ai", "technology", "computers"]
    for topic, count in sorted_topics:
        if any(keyword in topic.lower() for keyword in keywords):
            print(f"✅ Best topic selected: {topic} (Found in {count} sources)")
            return topic

    # در صورت نبودن موضوع مرتبط، برترین موضوع را انتخاب کن
    best_fallback_topic = sorted_topics[0][0] if sorted_topics else None
    if best_fallback_topic:
        print(f"⚠ No suitable trending topic found. Using top topic: {best_fallback_topic}")
    
    return best_fallback_topic

# اجرای تابع
topic = select_best_trending_topic()

import openai

def generate_video_script(topic):
    
    #تولید یک متن ویدیوی جذاب با لحن عامیانه و پرانرژی.
    if not topic:
        print("❌ Error: No topic provided!")
        return None

    prompt = f"""
    Write a viral YouTube video script for the topic: {topic}. 
    The script should be informal, fun, and engaging like a famous YouTuber. 
    The tone should be energetic and natural, avoiding anything too formal or robotic.

    Structure:
    1️⃣ Hook (First 5-10 seconds) - Start with a shocking fact, an exciting question, or a crazy statement.
    2️⃣ Main Content (70% of the video) - Explain the topic in a super fun and easy way, like talking to a friend.
    3️⃣ Call to Action (Last 10 seconds) - Encourage viewers to like, comment, and subscribe in a way that feels natural.

    Example:
    - Hook: "Yo! Did you know there's a secret trick in Minecraft that lets you survive ANY fall?! Most players have NO idea about this!"
    - Main Content: "So check this out... Normally, if you fall from a high place, you're DONE. But there's actually a trick where you can land on a ladder at the very last second and take ZERO damage! It's all about Minecraft physics, and it works EVERY time."
    - Call to Action: "Try this in your next game and tell me in the comments if it worked! And hey, if you love Minecraft tricks like this, smash that like button so I know to drop more!"

    Now, generate a script with this same fun, engaging style for the topic: {topic}.
    """

    try:
        client = openai.OpenAI()  # کلاینت جدید OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        script = response.choices[0].message.content
        print("✅ Video script generated successfully!")
        return script
    except Exception as e:
        print("❌ Error generating script:", str(e))
        return None

topic = select_best_trending_topic()
if topic:
    script = generate_video_script(topic)
else:
    print("❌ No topic selected. Cannot generate script.")


def generate_video(voiceover, background_video, output_video="final_video.mp4"):
    
    #ترکیب پس‌زمینه‌ی ماینکرفت، صداگذاری، و اضافه کردن زیرنویس
    
    try:
        # ترکیب ویدیو و صدا
        command = f"ffmpeg -i {background_video} -i {voiceover} -c:v copy -c:a aac {output_video}"
        subprocess.run(command, shell=True, check=True)
        print("✅ Video generated successfully!")
        return output_video
    except Exception as e:
        print("❌ Error generating video:", str(e))
        return None

def generate_subtitles(audio_file, output_srt="subtitles.srt"):
    
    #تولید زیرنویس هماهنگ با صدا با استفاده از Whisper AI
    
    try:
        response = openai.Audio.transcribe("whisper-1", audio_file)
        subtitles = response["text"]

        with open(output_srt, "w") as srt_file:
            srt_file.write(subtitles)

        print("✅ Subtitles generated successfully!")
        return output_srt
    except Exception as e:
        print("❌ Error generating subtitles:", str(e))
        return None


def generate_voiceover(script, output_audio="voiceover.mp3"):
    
    #تولید صداگذاری از متن با استفاده از ElevenLabs API
    
    if not ELEVENLABS_API_KEY:
        print("❌ ERROR: ElevenLabs API key is missing!")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    payload = {
        "text": script,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        with open(output_audio, "wb") as f:
            f.write(response.content)
        print("✅ Voiceover generated successfully!")
        return output_audio
    else:
        print(f"❌ Error generating voiceover: {response.json()}")
        return None

def enhance_audio(input_audio, output_audio="enhanced_voiceover.mp3"):
    
    #پردازش و بهینه‌سازی صدای گوینده، حذف نویز و اضافه کردن افکت‌های صوتی
    
    print("🎧 Enhancing voiceover...")

    # بارگذاری فایل صوتی
    try:
        audio = AudioSegment.from_file(input_audio)
    except Exception as e:
        print(f"❌ Error loading audio file: {e}")
        return None

    # **حذف نویز و نرمال‌سازی صدا**
    enhanced_audio = normalize(audio)

    # **افزودن افکت صوتی کلیک در ابتدای ویدیو**
    try:
        click_sound = AudioSegment.from_file("sounds/click.mp3")
        enhanced_audio = click_sound + enhanced_audio
    except FileNotFoundError:
        print("⚠ Click sound file not found, continuing without it.")

    # ذخیره‌ی نسخه‌ی بهینه‌شده
    try:
        enhanced_audio.export(output_audio, format="mp3")
        print(f"✅ Voiceover enhanced and saved as {output_audio}")
        return output_audio
    except Exception as e:
        print(f"❌ Error saving enhanced audio: {e}")
        return None


def enhance_video(input_video, output_video="enhanced_video.mp4"):
    
    #بهبود ویدیو با افزودن ترنزیشن‌ها، افکت‌های گرافیکی و متن
    
    print("🎬 Enhancing video with effects...")

    # بارگذاری ویدیو
    clip = VideoFileClip(input_video)

    # **افزودن افکت فید-این و فید-اوت (ورود و خروج نرم)**
    clip = fadein.fadein(clip, 1).fx(fadeout.fadeout, 1)

    # **ایجاد متن عنوان برای ویدیو**
    title_text = TextClip("🔥 CreeperClues - Minecraft Facts!", fontsize=70, color="white", font="Arial-Bold")
    title_text = title_text.set_position(("center", "top")).set_duration(3)

    # **ترکیب متن با ویدیو**
    final_clip = CompositeVideoClip([clip, title_text])

    # ذخیره‌ی ویدیوی بهینه‌شده
    final_clip.write_videofile(output_video, codec="libx264", fps=30)

    print(f"✅ Video enhanced and saved as {output_video}")
    return output_video

def add_video_effects(input_video, output_video="final_video_with_effects.mp4"):
    
    #اضافه کردن افکت‌های تصویری، ترنزیشن‌ها و متن‌های گرافیکی به ویدیو
    
    print("🎬 Adding effects to video...")

    # بارگذاری ویدیو اصلی
    clip = VideoFileClip(input_video)

    # ایجاد متن گرافیکی متحرک
    txt_clip = TextClip("🔥 Amazing Minecraft Fact!", fontsize=80, color='yellow', font="Impact-Bold")
    txt_clip = txt_clip.set_position(("center", "top")).set_duration(3)  # نمایش برای ۳ ثانیه

    # ترکیب ویدیو و متن
    final = CompositeVideoClip([clip, txt_clip])

    # ذخیره ویدیو
    final.write_videofile(output_video, codec="libx264", fps=30)
    print(f"✅ Video with effects saved as {output_video}")
    return output_video

def generate_thumbnail(topic, output_file="thumbnail.png"):
    
    #تولید تامبنیل جذاب برای ویدیو، ابتدا با DALL·E، و در صورت خطا، با یک تصویر پیش‌فرض.
    
    print("🖼 Generating thumbnail...")

    # تلاش برای تولید تصویر با DALL·E
    try:
        response = openai.Image.create(
            model="dall-e-3",
            prompt=f"Create a high-quality YouTube thumbnail for a video about {topic}. It should be colorful, eye-catching, and engaging.",
            n=1,
            size="1024x1024"
        )

        if "data" in response and response["data"]:
            image_url = response["data"][0]["url"]
            if image_url:
                img = Image.open(requests.get(image_url, stream=True).raw)
                print("✅ Thumbnail generated using DALL·E!")
            else:
                raise Exception("DALL·E did not return a valid image URL.")
        else:
            raise Exception("DALL·E API returned an empty response.")

    except Exception as e:
        print(f"⚠ DALL·E failed: {e}")
        print("🖼 Using default background for thumbnail...")
        img = Image.open("thumbnail_bg.jpg").resize((1280, 720))

    # ایجاد متن روی تصویر
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("impact.ttf", 90)
    text_position = (100, 550)

    # افکت استروک برای خوانایی بهتر
    for offset in range(-3, 4, 2):
        draw.text((text_position[0] + offset, text_position[1]), topic, font=font, fill="black")
        draw.text((text_position[0], text_position[1] + offset), topic, font=font, fill="black")

    draw.text(text_position, topic, font=font, fill="yellow")

    # ذخیره‌ی تصویر نهایی
    img.save(output_file)
    print(f"✅ Thumbnail saved as {output_file}")
    return output_file

def generate_video_metadata(topic):
    
    #تولید عنوان، توضیحات و هشتگ‌های بهینه‌شده برای یوتیوب.
    
    print("📝 Generating video metadata...")

    prompt = f"""
    Generate an engaging YouTube video title, description, and relevant hashtags for a video about "{topic}".
    
    - The title should be eye-catching and optimized for high CTR.
    - The description should include a short summary of the video, a call to action, and links.
    - The hashtags should be relevant and increase discoverability.
    
    Return the output in **valid JSON format** with keys: "title", "description", and "hashtags".
    """

    try:
        client = openai.Client()  # مقداردهی صحیح کلاینت OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250
        )
        
        content = response.choices[0].message.content.strip()

        # تلاش برای تبدیل JSON
        try:
            metadata = json.loads(content)
            if not all(key in metadata for key in ["title", "description", "hashtags"]):
                raise ValueError("Missing expected keys in JSON")
        except (json.JSONDecodeError, ValueError):
            print("⚠ Warning: Invalid JSON received from OpenAI. Using default metadata.")
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

metadata = generate_video_metadata(topic)
print(metadata)



def analyze_past_videos():

    #تحلیل داده‌های عملکرد ویدیوهای قبلی و بهینه‌سازی استراتژی محتوا

    analytics_file = "video_analytics.json"

    if not os.path.exists(analytics_file):
        print("⚠ No past video analytics found.")
        return None

    with open(analytics_file, "r") as file:
        try:
            data = json.load(file)
            if not isinstance(data, dict):
                print("⚠ Invalid analytics data format.")
                return None
        except json.JSONDecodeError:
            print("⚠ Error reading analytics file.")
            return None

    best_videos = sorted(
        [(vid, stats) for vid, stats in data.items() if "engagement_rate" in stats],
        key=lambda x: x[1]["engagement_rate"],
        reverse=True
    )

    if not best_videos:
        print("⚠ No valid engagement data found.")
        return None

    print("\n📊 **Top Performing Videos:**")
    for video_id, stats in best_videos[:5]:
        print(f"- Video ID: {video_id}, Engagement Rate: {stats['engagement_rate']:.2%}")

    return best_videos

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

def check_copyright_violation(script):
    
    #بررسی متن تولید شده برای جلوگیری از کپی‌رایت.
    prompt = f"""
    Please analyze the following script for any copyright violations, plagiarism, or YouTube policy violations.
    If the script is safe, return "SAFE".
    If the script contains potential copyright or policy issues, return a short explanation.

    Script:
    {script}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        result = response["choices"][0]["message"]["content"]

        if "SAFE" in result:
            print("✅ Script is safe.")
            return True
        else:
            print(f"⚠ Potential issue detected: {result}")
            return False
    except Exception as e:
        print("❌ Error checking copyright:", str(e))
        return True  # اگر چکینگ انجام نشد، اجازه ادامه بده

# استفاده از این بررسی در روند تولید متن
if script and check_copyright_violation(script):
    with open("video_script.txt", "w") as file:
        file.write(script)
    print("📜 Video script saved successfully!")
else:
    print("❌ Script rejected due to potential copyright or policy violations.")

def check_youtube_policy(title, description):
    
    #بررسی عنوان و توضیحات برای اطمینان از عدم نقض قوانین یوتیوب.
    
    prompt = f"""
    Please analyze the following YouTube video metadata to check if it violates YouTube's policies.
    If it's safe, return "SAFE".
    If there is a potential issue, return a short explanation.

    Title: {title}
    Description: {description}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        result = response["choices"][0]["message"]["content"]

        if "SAFE" in result:
            print("✅ Metadata is safe.")
            return True
        else:
            print(f"⚠ Potential policy issue detected: {result}")
            return False
    except Exception as e:
        print("❌ Error checking YouTube policy:", str(e))
        return True
video_metadata = generate_video_metadata(topic)
# بررسی قبل از آپلود
if video_metadata and check_youtube_policy(video_metadata["title"], video_metadata["description"]):
    upload_video(enhanced_video, video_id)
else:
    print("❌ Video upload blocked due to policy violation.")

def check_audio_copyright(audio_file):
    
    #بررسی اینکه آیا موسیقی یا صداگذاری استفاده شده کپی‌رایت دارد یا خیر.
    
    prompt = f"""
    Please analyze the following audio file and determine if it contains copyrighted music or speech.
    If it's safe, return "SAFE".
    If there is a potential copyright issue, return a short explanation.

    Audio file: {audio_file}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        result = response["choices"][0]["message"]["content"]

        if "SAFE" in result:
            print("✅ Audio is safe.")
            return True
        else:
            print(f"⚠ Potential copyright issue detected: {result}")
            return False
    except Exception as e:
        print("❌ Error checking audio copyright:", str(e))
        return True

# بررسی قبل از اضافه کردن موسیقی یا صداگذاری
if check_audio_copyright("voiceover.mp3"):
    enhanced_voiceover = enhance_audio("voiceover.mp3")
else:
    print("❌ Audio rejected due to potential copyright violation.")

def check_video_content(video_file):
    
    #بررسی محتوای ویدیو برای محتوای حساس یا ممنوعه.
    
    prompt = f"""
    Please analyze the following video file and determine if it contains sensitive, inappropriate, or copyrighted content.
    If it's safe, return "SAFE".
    If there is a potential issue, return a short explanation.

    Video file: {video_file}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        result = response["choices"][0]["message"]["content"]

        if "SAFE" in result:
            print("✅ Video content is safe.")
            return True
        else:
            print(f"⚠ Potential issue detected: {result}")
            return False
    except Exception as e:
        print("❌ Error checking video content:", str(e))
        return True

# بررسی قبل از آپلود ویدیو
if check_video_content("final_video.mp4"):
    upload_video(enhanced_video, video_id)
else:
    print("❌ Video upload blocked due to potential violation.")

# بررسی اینکه امروز چند ویدیو آپلود شده
def check_upload_limit():
    today = datetime.now(EST).strftime('%Y-%m-%d')

    # اگر فایل لاگ وجود نداشت، بساز
    if not os.path.exists(UPLOAD_LOG_FILE):
        with open(UPLOAD_LOG_FILE, "w") as file:
            json.dump({"date": today, "long_videos": 0, "shorts": 0}, file)

    # مقدار آپلودهای قبلی را بخوان
    with open(UPLOAD_LOG_FILE, "r") as file:
        data = json.load(file)

    # اگر تاریخ تغییر کرده، لاگ را ریست کن
    if data["date"] != today:
        data = {"date": today, "long_videos": 0, "shorts": 0}

    return data

# ذخیره‌ی تعداد آپلودها
def log_upload(video_type):
    data = check_upload_limit()
    data[video_type] += 1  # تعداد آپلودهای نوع موردنظر را افزایش بده

    with open(UPLOAD_LOG_FILE, "w") as file:
        json.dump(data, file)

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
