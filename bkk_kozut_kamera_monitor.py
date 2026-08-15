import os
import requests
from PIL import Image
from io import BytesIO

# ⚠️ Cseréld ki az Insecamról kimásolt KÖZVETLEN kép/stream URL-ekre!
# Megszerzés: Insecam oldalon a képre JOBB KLIKK -> "Kép címének másolása"
CAMERAS = {
    "kamera_1": "http://195.228.x.x:8080/mjpg/video.mjpg",
    "kamera_2": "http://82.131.x.x/cgi-bin/faststream.jpg",
    "kamera_3": "http://185.51.x.x/jpg/image.jpg"
}

OUTPUT_DIR = "images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def download_camera_frame(url):
    """Lekéri a képet, kezeli a sima JPG-t és az MJPEG stream-et is."""
    # stream=True kell, ha folyamatos MJPEG streamről van szó
    response = requests.get(url, headers=HEADERS, timeout=15, stream=True)
    
    if response.status_code != 200:
        return None

    content_type = response.headers.get("Content-Type", "")
    
    # Ha folyamatos MJPEG streamről van szó, kivágjuk az első teljes JPEG képkockát
    if "multipart" in content_type or "mjpeg" in content_type:
        bytes_data = b""
        for chunk in response.iter_content(chunk_size=1024):
            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8') # JPEG start
            b = bytes_data.find(b'\xff\xd9') # JPEG end
            if a != -1 and b != -1:
                jpg_data = bytes_data[a:b+2]
                response.close()
                return jpg_data
        return None
    else:
        # Sima állókép (JPG/PNG) esetén a teljes tartalmat adjuk vissza
        return response.content

def fetch_and_save():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for cam_id, url in CAMERAS.items():
        print(f"Letöltés indítása: {cam_id}...")
        
        # Kihagyja a mintacímeket, ha véletlenül nem cserélted ki
        if "x.x" in url or "YOUR_CAMERA" in url:
            print(f"  -> SKIPPED: Cseréld ki a valós URL-re a(z) {cam_id} kameránál!")
            continue

        try:
            raw_data = download_camera_frame(url)
            
            if raw_data:
                # Kép érvényességének ellenőrzése
                image = Image.open(BytesIO(raw_data))
                image.verify()
                
                # Mentés JPEG formátumban
                image = Image.open(BytesIO(raw_data))
                output_path = os.path.join(OUTPUT_DIR, f"{cam_id}.jpg")
                image.save(output_path, "JPEG", quality=85)
                print(f"  -> SIKER! Mentve: {output_path}")
            else:
                print(f"  -> Hiba: Nem sikerült érvényes képadatot letölteni a szerverről.")
                
        except Exception as e:
            print(f"  -> Kivétel hiba történt {cam_id} feldolgozásakor: {e}")

if __name__ == "__main__":
    fetch_and_save()
