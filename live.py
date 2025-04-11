import os
import logging
import torch
import cv2
from ultralytics import YOLO
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

# Configure Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings:
    PROJECT_NAME = "Live Fabric Defect Detector"
    VERSION = "1.0.0"
    MODEL_PATH = "C:/Users/spgir/OneDrive/Documents/BE Project/codebase/model_training/models/runs/train/weights/best.pt"
    CLASS_NAMES = ['Hole', 'Stitch', 'Seam']
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    CAMERA_SOURCES = {'LAPTOP': 0, 'IP_CAMERA': "http://192.168.195.198:4747/video"}
    DEFAULT_CAMERA = 'LAPTOP'
    FRAME_RATE = 10
    WINDOW_SIZE = "1280x720"

    @staticmethod
    def check_cuda():
        logging.info(f"Using device: {Settings.DEVICE}")
        if torch.cuda.is_available():
            logging.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            logging.warning("CUDA not available. Using CPU.")

Settings.check_cuda()

# Load YOLO model
class LiveFabricDefectDetector:
    def __init__(self):
        self.model = YOLO(Settings.MODEL_PATH)
        self.class_names = Settings.CLASS_NAMES

    def predict(self, frame):
        results = self.model.predict(source=frame, save=False, show=False)
        return results[0]

# UI Class
class LiveFabricDetectionApp:
    def __init__(self):
        self.detector = LiveFabricDefectDetector()
        self.cap = cv2.VideoCapture(Settings.CAMERA_SOURCES[Settings.DEFAULT_CAMERA])

        # --- Initialize Tkinter Root ---
        self.root = tk.Tk()
        self.root.title(Settings.PROJECT_NAME)
        self.root.geometry(Settings.WINDOW_SIZE)
        self.root.configure(bg="#f0f0f0")

        # --- Title Frame ---
        self.title_frame = tk.Frame(self.root, bg="#004080", height=50)
        self.title_frame.pack(fill="x")
        tk.Label(self.title_frame, text=Settings.PROJECT_NAME, font=("Helvetica", 20, "bold"), fg="white", bg="#004080").pack(pady=10)

        # --- Content Frame (Camera + Info) ---
        self.content_frame = tk.Frame(self.root, bg="white")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Camera Frame ---
        self.camera_label = tk.Label(self.content_frame, bg="black")
        self.camera_label.grid(row=0, column=0, padx=10)

        # --- Classification Info Frame ---
        self.info_frame = tk.Frame(self.content_frame, bg="white")
        self.info_frame.grid(row=0, column=1, sticky="n")

        self.class_label = tk.Label(self.info_frame, text="Initializing...", font=("Arial", 14), bg="white", fg="green", wraplength=300, justify="left")
        self.class_label.pack(pady=10)

        # --- Status Bar ---
        self.status_bar = tk.Label(self.root, text=f"Version: {Settings.VERSION}", bd=1, relief=tk.SUNKEN, anchor=tk.E, bg="#d9d9d9")
        self.status_bar.pack(side="bottom", fill="x")

        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            detections = self.detector.predict(frame)

            for box in detections.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                class_id = int(box.cls)
                label = f"{Settings.CLASS_NAMES[class_id]} ({box.conf[0]:.2f})"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Convert OpenCV frame (BGR to RGB)
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            img = img.resize((640, 480))  # Resize for better UI fit
            img_tk = ImageTk.PhotoImage(image=img)

            self.camera_label.config(image=img_tk)
            self.camera_label.image = img_tk

            # Update classification info
            detected_labels = [Settings.CLASS_NAMES[int(box.cls)] for box in detections.boxes]
            if detected_labels:
                text = "Detected Defects:\n" + "\n".join(set(detected_labels))
                self.class_label.config(text=text, fg="red")
            else:
                self.class_label.config(text="No Defects Detected", fg="green")

        self.root.after(Settings.FRAME_RATE, self.update_frame)

    def run(self):
        logging.info("Starting Fabric Defect Detection...")
        self.root.mainloop()
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    app = LiveFabricDetectionApp()
    app.run()

