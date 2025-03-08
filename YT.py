import os
import requests
import json

# Load environment variables from Railway
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# YouTube API URLs
TOKEN_URL = "https://oauth2.googleapis.com/token"
METADATA_URL = "https://www.googleapis.com/youtube/v3/videos"
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
    if response.status_code != 200 or "access_token" not in response_json:
        raise Exception("Failed to get access token: " + str(response_json))
    return response_json.get("access_token")

# Function to get valid video categories
def get_video_categories():
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {
        "part": "snippet",
        "regionCode": "US"  # Change to your region if needed
    }
    response = requests.get("https://www.googleapis.com/youtube/v3/videoCategories", headers=headers, params=params)
    return response.json()

# Function to upload metadata and get video ID
def upload_metadata(title, description, category_id=24, privacy_status="public"):
    access_token = get_access_token()

    # Validate privacyStatus
    if privacy_status not in ["public", "private", "unlisted"]:
        print(f"Invalid privacy status: {privacy_status}. Defaulting to 'public'.")
        privacy_status = "public"

    # Validate title and description
    if not title or len(title) > 100:
        raise ValueError("Title must be between 1 and 100 characters.")
    if not description or len(description) > 5000:
        raise ValueError("Description must be less than 5000 characters.")

    # Validate category_id
    if not isinstance(category_id, int) or category_id <= 0:
        raise ValueError("category_id must be a positive integer.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    params = {"part": "snippet,status"}

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": int(category_id)  # Ensure categoryId is int
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    print("Uploading metadata with the following parameters:")
    print(json.dumps(metadata, indent=2))  # Log the metadata being sent

    metadata_response = requests.post(METADATA_URL, headers=headers, params=params, json=metadata)
    
    if metadata_response.status_code != 200:
        print("Error uploading metadata:", metadata_response.json())
        return None

    return metadata_response.json().get("id")

# Function to upload video using resumable upload
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
        print("Failed to retrieve upload URL
