import os
import requests
import json
import pytz
import collections
import openai
from datetime import datetime
from pytrends.request import TrendReq

# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
    """
    دریافت لیست ویدیوهای پرطرفدار یوتیوب و ذخیره در trending_topics.json
    """
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
    """
    دریافت لیست ترندهای روز از Google Trends
    """
    pytrends = TrendReq(hl='en-US', tz=360)  # مقداردهی اولیه API گوگل ترندز
    pytrends.build_payload(kw_list=["Minecraft", "AI", "Technology"], timeframe="now 1-d", geo="US")  
    trending_searches = pytrends.trending_searches(pn="united_states")  # دریافت ترندهای روز
    
    trends = trending_searches[0].tolist()  # تبدیل به لیست رشته‌ای
    return [{"title": trend, "source": "Google Trends"} for trend in trends]

def fetch_reddit_trends(subreddit="gaming", limit=10):
    """
    دریافت پست‌های ترند از Reddit
    """
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
    """
    دریافت و ترکیب داده‌های ترند از یوتیوب، گوگل ترندز، و ردیت
    """
    print("🔍 Fetching trending topics from multiple sources...")
    
    youtube_trends = fetch_youtube_trending()
    google_trends = fetch_google_trends()
    reddit_trends = fetch_reddit_trends()

    all_trends = youtube_trends + google_trends + reddit_trends  # ترکیب داده‌های ترند
    with open("trending_topics.json", "w") as file:
        json.dump(all_trends, file, indent=2)

    print(f"✅ {len(all_trends)} trending topics saved in trending_topics.json")

def select_best_trending_topic():
    """
    تحلیل داده‌های ترند و انتخاب بهترین موضوع برای تولید ویدیو.
    """
    # بارگذاری داده‌ها از trending_topics.json
    try:
        with open("trending_topics.json", "r") as file:
            trends = json.load(file)
    except FileNotFoundError:
        print("❌ Error: trending_topics.json not found.")
        return None

    if not trends:
        print("❌ No trending topics found.")
        return None

    # شمارش میزان تکرار موضوعات در منابع مختلف
    topic_count = collections.Counter([t["title"] for t in trends])

    # مرتب‌سازی بر اساس بیشترین تکرار
    sorted_topics = sorted(topic_count.items(), key=lambda x: x[1], reverse=True)

    # انتخاب اولین موضوع که مرتبط با Minecraft, AI, یا Gaming باشد
    keywords = ["minecraft", "gaming", "ai", "technology", "computers"]
    for topic, count in sorted_topics:
        if any(keyword in topic.lower() for keyword in keywords):
            print(f"✅ Best topic selected: {topic} (Found in {count} sources)")
            return topic

    print("⚠ No suitable trending topic found.")
    return None

def generate_video_script(topic):
    """
    تولید یک متن ویدیوی جذاب با لحن عامیانه و پرانرژی.
    """
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        script = response["choices"][0]["message"]["content"]
        print("✅ Video script generated successfully!")
        return script
    except Exception as e:
        print("❌ Error generating script:", str(e))
        return None

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
    print("Starting the YouTube Auto-Upload Bot...")

    # 1️⃣ دریافت ترندهای یوتیوب
    fetch_youtube_trending()  # دریافت موضوعات پرطرفدار و ذخیره در trending_topics.json

    # 1️⃣ دریافت و ذخیره‌ی ترندهای مختلف در `trending_topics.json`
    fetch_all_trends()

# 2️⃣ تحلیل داده‌های ترند و انتخاب بهترین موضوع
    selected_topic = select_best_trending_topic()
    if selected_topic:
        print(f"🔥 The system will generate a video on: {selected_topic}")
    else:
        print("⚠ No suitable topic found, skipping video creation.")

# 3️⃣ تولید متن ویدیوی جذاب با GPT
        script = generate_video_script(selected_topic)
        if script:
            with open("video_script.txt", "w") as file:
                file.write(script)
            print("📜 Video script saved successfully!")
    else:
        print("⚠ No suitable topic found, skipping video creation.")

    # 2️⃣ ادامه اجرای برنامه طبق روال قبلی
    upload_type = get_upload_type()
    upload_limits = check_upload_limit()
    
    if upload_type and upload_limits[upload_type] < (MAX_LONG_UPLOADS if upload_type == "long_videos" else MAX_SHORTS_UPLOADS):
        print(f"✅ It's time to upload a {upload_type.replace('_', ' ')}. Proceeding with upload.")
        try:
            video_file = LONG_VIDEO_FILE if upload_type == "long_videos" else SHORT_VIDEO_FILE
            category_id = 20  # دسته‌بندی Gaming
            video_id = upload_metadata("CreeperClues - New Video!", "Enjoy some cool Minecraft facts!", category_id, "public")
            if video_id:
                upload_video(video_file, video_id)
                log_upload(upload_type)  # ثبت آپلود در لاگ
        except Exception as e:
            print("An error occurred:", str(e))
    else:
        print("⏳ Either it's not the right time for upload or today's upload limit has been reached.")
