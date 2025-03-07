import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

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
        raise Exception("Failed to retrieve access token: " + str(response_json))
    return response_json.get("access_token")

# Function to upload a video using resumable upload
def upload_video(video_file, title, description, category_id="22", privacy_status="public"):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params = {"part": "snippet,status", "notifySubscribers": True}
    metadata = {
        "snippet": {"title": title, "description": description, "categoryId": category_id},
        "status": {"privacyStatus": privacy_status}
    }
    
    # Step 1: Initiate resumable upload
    metadata_response = requests.post(UPLOAD_URL, headers=headers, params=params, json=metadata)
    if metadata_response.status_code != 200:
        raise Exception("Failed to initiate upload: " + str(metadata_response.json()))
    metadata_response_json = metadata_response.json()
    video_id = metadata_response_json.get("id")
    upload_url = metadata_response.headers.get("Location")
    
    if not video_id or not upload_url:
        raise Exception("Upload initialization failed: " + str(metadata_response_json))
    
    # Step 2: Upload video file in chunks
    with open(video_file, "rb") as file:
        chunk_size = 1024 * 1024 * 8  # 8MB chunks
        while chunk := file.read(chunk_size):
            chunk_headers = {"Authorization": f"Bearer {access_token}", "Content-Length": str(len(chunk)), "Content-Range": f"bytes 0-{len(chunk)-1}/{os.path.getsize(video_file)}"}
            upload_response = requests.put(upload_url, headers=chunk_headers, data=chunk)
            if upload_response.status_code not in [200, 201]:
                raise Exception("Chunk upload failed: " + str(upload_response.json()))

    print("Upload successful! Video ID:", video_id)

# Example usage
if __name__ == "__main__":
    upload_video("video.mp4", "Test Video", "This is an automated upload.")
