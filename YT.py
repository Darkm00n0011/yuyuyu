import os
import requests
import json
from datetime import datetime
import pytz

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
