import os
import requests
import json
from datetime import datetime
import pytz

# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

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
