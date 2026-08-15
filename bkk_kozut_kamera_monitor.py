import os
import requests
from PIL import Image
from io import BytesIO

# Figyelni kívánt kamerák közvetlen képlinkje
CAMERAS = {
    "lanchid": "https://www.idokep.hu/webcam/lanchid.jpg",
    "erzsebethid": "https://www.idokep.hu/webcam/erzsebethid.jpg",
    "margithid": "https://www.idokep.hu/webcam/margithid.jpg",
    "balatonvilagos": "https://www.idokep.hu/webcam/balatonvilagos.jpg"
}

OUTPUT_DIR = "images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_and_save():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for cam_id, url in CAMERAS.items():
        try:
            print(f"Letöltés: {cam_id} ({url})...")
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.verify()
                
                image = Image.open(BytesIO(response.content))
                output_path = os.path.join(OUTPUT_DIR, f"{cam_id}.jpg")
                image.save(output_path, "JPEG", quality=85)
                print(f"  -> Mentve: {cam_id}.jpg")
            else:
                print(f"  -> Sikertelen letöltés (HTTP status: {response.status_code})")
        except Exception as e:
            print(f"  -> Hiba történt {cam_id} feldolgozásakor: {e}")

if __name__ == "__main__":
    fetch_and_save()
