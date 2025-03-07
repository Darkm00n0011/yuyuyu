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
        "Content-Type": "application/json; charset=UTF-8"
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
    
    # Step 1: Upload metadata
    metadata_response = requests.post(UPLOAD_URL, headers=headers, params=params, json=metadata)
    metadata_response_json = metadata_response.json()

    if "id" not in metadata_response_json:
        print("Error uploading metadata:", metadata_response_json)
        return
    
    video_id = metadata_response_json["id"]

    # Step 2: Upload video file using resumable upload
    headers["X-Upload-Content-Type"] = "video/mp4"
    init_request = requests.post(
        f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status&id={video_id}",
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
        file_data = file.read()
        upload_response = requests.put(upload_url, headers={"Content-Length": str(len(file_data))}, data=file_data)

    print("Upload response:", upload_response.json())

# Example usage
if __name__ == "__main__":
    upload_video("video.mp4", "Test Video", "This is an automated upload.")
