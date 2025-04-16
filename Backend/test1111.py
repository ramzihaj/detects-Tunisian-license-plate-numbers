from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
import base64
import os
import logging
import json
import asyncio
from format_tun_plate import format_tunisian_plate_cam_center,format_tunisian_plate_cam_right,format_tunisian_plate_cam_left
app = FastAPI()
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

@app.get("/")
async def home():
    return FileResponse("templates/index.html")

# Chargement du modèle
try:
    model = YOLO(r"C:\Users\PCS\Desktop\PFA projet\Backend\Model\best002.pt")
    print("✅ Modèle YOLO chargé avec succès.")
except Exception as e:
    logging.error(f"❌ Erreur de chargement du modèle: {e}")
    raise e

reader = easyocr.Reader(['en'])
@app.websocket("/ws")
async def detect_video(websocket: WebSocket):
    await websocket.accept()
    detected_plates = []

    video_path = r"C:\Users\PCS\Desktop\PFA projet\Backend\static\video\test1.mp4"

    if not os.path.exists(video_path):
        await websocket.send_text(json.dumps({"error": "Vidéo introuvable"}))
        return

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        await websocket.send_text(json.dumps({"error": "Impossible d'ouvrir la vidéo"}))
        return

    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("🎞️ Fin de la vidéo.")
                break

            frame_count += 1
            print(f"🎬 Traitement de la frame {frame_count}")

            results = model(frame)
            print(f"🔎 {len(results)} détections trouvées par YOLO à la frame {frame_count}.")

            for result in results:
                for box in result.boxes.xyxy:
                    x1, y1, x2, y2 = map(int, box[:4])
                    plate_roi = frame[y1:y2, x1:x2]

                    if plate_roi.size != 0:
                        gray_plate = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
                        texts = reader.readtext(gray_plate, detail=0)
                        print(f"📝 Texte détecté brut: {texts}")

                        if texts:
                            formatted_plate = format_tunisian_plate_cam_center(texts)

                            if formatted_plate not in detected_plates:
                                detected_plates.append(formatted_plate)

                            cv2.putText(frame, formatted_plate, (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            _, buffer = cv2.imencode('.jpg', frame)
            image_base64 = base64.b64encode(buffer).decode()

            data = {
                "frame": frame_count,
                "plates": detected_plates,
                "image": image_base64
            }

            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(0.1)  # pour ralentir un peu le flux

    except Exception as e:
        logging.error(f"❌ Erreur lors du traitement vidéo: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))
    finally:
        cap.release()
