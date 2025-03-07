import os
import requests
import json

# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# YouTube API URLs
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

# Function to get new access token
def get_access_token():
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(TOKEN_URL, data=data)
    response_json = response.json()
    if "access_token" not in response_json:
        raise Exception("Failed to get access token: " + str(response_json))
    return response_json.get("access_token")

# Function to upload a video
def upload_video(video_file, title, description, category_id="22", privacy_status="public"):
    access_token = get_access_token()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "multipart/related; boundary=boundary_string"
    }

    params = {
        "part": "snippet,status"
    }
    
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    # ساخت بادی برای درخواست
    metadata_str = json.dumps(metadata)
    body_start = f"--boundary_string\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata_str}\r\n"
    body_end = "\r\n--boundary_string--"

    with open(video_file, "rb") as file:
        video_data = file.read()
        body = body_start.encode() + video_data + body_end.encode()

    # ارسال درخواست آپلود
    response = requests.post(UPLOAD_URL, headers=headers, params=params, data=body)

    print("Upload response:", response.json())

# Example usage
if __name__ == "__main__":
    upload_video("video.mp4", "Test Video", "This is an automated upload.")
