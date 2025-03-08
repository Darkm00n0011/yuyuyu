# استفاده از نسخه جدیدتر پایتون
FROM python:3.10

# تنظیم دایرکتوری کاری در کانتینر
WORKDIR /app

# نصب پیش‌نیازهای سیستمی
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل‌های پروژه به کانتینر
COPY . /app

# نصب پکیج‌های موردنیاز
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

RUN pip install moviepy


# اجرای برنامه
CMD ["python", "YT.py"]
