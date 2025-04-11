import os
import logging
import torch
import cv2
import time
import threading
import serial
import json
from ultralytics import YOLO
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox

# Configure Logger
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fabric_robot.log"),
        logging.StreamHandler()
    ]
)

class Settings:
    PROJECT_NAME = "Live Fabric Defect Detector with Robot Arm"
    VERSION = "2.0.0"
    MODEL_PATH = "C:/Users/spgir/OneDrive/Documents/BE Project/codebase/model_training/models/runs/train/weights/best.pt"  # Update this path to where your model is stored
    CLASS_NAMES = ['Hole', 'Stitch', 'Seam']
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    CAMERA_SOURCES = {'LAPTOP': 0, 'IP_CAMERA': "http://192.168.195.198:4747/video"}
    DEFAULT_CAMERA = 'LAPTOP'
    FRAME_RATE = 10
    WINDOW_SIZE = "1280x720"
    
    # Arduino settings
    ARDUINO_PORT = "COM3"  # Change this to match your Arduino port (e.g., "/dev/ttyACM0" on Linux)
    ARDUINO_BAUDRATE = 115200
    
    # Robot arm settings
    GRIPPER_CHANNEL = 3
    DETECTION_THRESHOLD = 0.6  # Confidence threshold for defect detection
    DETECTION_COOLDOWN = 5  # Seconds between robot actions to avoid rapid movements

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
        try:
            self.model = YOLO(Settings.MODEL_PATH)
            self.class_names = Settings.CLASS_NAMES
            logging.info("YOLO model loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load YOLO model: {e}")
            raise

    def predict(self, frame):
        results = self.model.predict(source=frame, save=False, show=False)
        return results[0]

# Robot Arm Controller using Arduino
class RobotArmController:
    def __init__(self):
        self.arm_ready = False
        try:
            # Connect to Arduino
            self.arduino = serial.Serial(
                port=Settings.ARDUINO_PORT,
                baudrate=Settings.ARDUINO_BAUDRATE,
                timeout=2.0
            )
            time.sleep(2)  # Wait for Arduino to initialize
            
            # Define arm positions (servo angles)
            self.positions = {
                "home":         [120, 45, 45, 180],  # Last value is gripper (closed)
                "pickup":       [0, 0, 180, 180],
                "defective":    [180, 0, 180, 180],
                "non_defective":[90, 0, 180, 180]
            }
            
            self.is_busy = False
            self.last_action_time = 0
            
            # Initialize arm position
            self.move_to_position(self.positions["home"])
            logging.info("Robot arm initialized successfully in home position with gripper closed")
            self.arm_ready = True
            
        except Exception as e:
            logging.error(f"Failed to initialize robot arm: {e}")
            self.arm_ready = False
    
    def send_command(self, command_dict):
        """Send a command to the Arduino as JSON"""
        try:
            command_json = json.dumps(command_dict)
            self.arduino.write(f"{command_json}\n".encode())
            response = self.arduino.readline().decode().strip()
            logging.info(f"Arduino response: {response}")
            return response
        except Exception as e:
            logging.error(f"Error sending command to Arduino: {e}")
            return "ERROR"
    
    def move_servo(self, channel, angle):
        """Move a single servo to the specified angle"""
        command = {
            "cmd": "move",
            "servo": channel,
            "angle": angle
        }
        return self.send_command(command)
    
    def move_to_position(self, position_list):
        """Move all servos to a predefined position"""
        command = {
            "cmd": "move_all",
            "angles": position_list
        }
        return self.send_command(command)
    
    def gripper_open(self):
        logging.info("Gripper Opening...")
        command = {
            "cmd": "move",
            "servo": Settings.GRIPPER_CHANNEL,
            "angle": 0
        }
        self.send_command(command)
        time.sleep(1.0)
        
    def gripper_close(self):
        logging.info("Gripper Closing...")
        command = {
            "cmd": "move",
            "servo": Settings.GRIPPER_CHANNEL,
            "angle": 180
        }
        self.send_command(command)
        time.sleep(1.0)
    
    def handle_object(self, defective=True):
        self.is_busy = True
        
        try:
            # 1. Start at home position with gripper closed
            logging.info("-> At Home Position")
            self.move_to_position(self.positions["home"])
            time.sleep(0.5)
            
            # 2. Move to pickup position, open gripper, then close to grab fabric
            logging.info("-> Moving to Pickup Position")
            self.move_to_position(self.positions["pickup"])
            time.sleep(0.5)
            
            logging.info("-> Opening gripper to prepare for pickup")
            self.gripper_open()
            time.sleep(0.5)
            
            logging.info("-> Closing gripper to grab fabric")
            self.gripper_close()
            time.sleep(0.5)
            
            # 3. Move to appropriate placement position based on defect status
            if defective:
                logging.info("-> Defective item detected. Moving to Defective Section")
                self.move_to_position(self.positions["defective"])
            else:
                logging.info("-> Non-defective item detected. Moving to Correct Section")
                self.move_to_position(self.positions["non_defective"])
                
            time.sleep(0.5)
            
            # 4. Open gripper to release fabric, then close gripper
            logging.info("-> Opening gripper to release fabric")
            self.gripper_open()
            time.sleep(0.5)
            
            logging.info("-> Closing gripper after release")
            self.gripper_close()
            time.sleep(0.5)
            
            # 5. Return to home position with gripper closed
            logging.info("-> Returning to Home Position")
            self.move_to_position(self.positions["home"])
            
        except Exception as e:
            logging.error(f"Error in robot movement: {e}")
        finally:
            self.is_busy = False
            self.last_action_time = time.time()

# Integrated UI Class
class IntegratedFabricDetectionApp:
    def __init__(self):
        try:
            # Initialize detector
            self.detector = LiveFabricDefectDetector()
            
            # Initialize robot arm controller
            self.robot_arm = RobotArmController()
            
            # Try to open camera with error handling
            try:
                self.cap = cv2.VideoCapture(Settings.CAMERA_SOURCES[Settings.DEFAULT_CAMERA])
                if not self.cap.isOpened():
                    logging.error(f"Failed to open camera at {Settings.CAMERA_SOURCES[Settings.DEFAULT_CAMERA]}")
                    # Try fallback camera source
                    if Settings.DEFAULT_CAMERA == 'IP_CAMERA':
                        logging.info("Trying laptop camera as fallback...")
                        self.cap = cv2.VideoCapture(Settings.CAMERA_SOURCES['LAPTOP'])
                    else:
                        logging.info("Trying IP camera as fallback...")
                        self.cap = cv2.VideoCapture(Settings.CAMERA_SOURCES['IP_CAMERA'])
                        
                    if not self.cap.isOpened():
                        logging.error("Failed to open any camera source")
                        messagebox.showerror("Camera Error", "Failed to open camera. Please check connections and try again.")
            except Exception as e:
                logging.error(f"Error initializing camera: {e}")
                messagebox.showerror("Camera Error", f"Failed to initialize camera: {e}")
            
            # Detection state
            self.last_detection_time = 0
            self.detection_cooldown = Settings.DETECTION_COOLDOWN
            self.detection_threshold = Settings.DETECTION_THRESHOLD
            self.detected_defects = []
            self.auto_mode = False

            # --- Initialize Tkinter Root ---
            self.root = tk.Tk()
            self.root.title(Settings.PROJECT_NAME)
            self.root.geometry(Settings.WINDOW_SIZE)
            self.root.configure(bg="#f0f0f0")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            # --- Title Frame ---
            self.title_frame = tk.Frame(self.root, bg="#004080", height=50)
            self.title_frame.pack(fill="x")
            tk.Label(self.title_frame, text=Settings.PROJECT_NAME, font=("Helvetica", 20, "bold"), fg="white", bg="#004080").pack(pady=10)

            # --- Content Frame (Camera + Info + Controls) ---
            self.content_frame = tk.Frame(self.root, bg="white")
            self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # --- Camera Frame ---
            self.camera_label = tk.Label(self.content_frame, bg="black", width=640, height=480)
            self.camera_label.grid(row=0, column=0, padx=10, rowspan=2)

            # --- Classification Info Frame ---
            self.info_frame = tk.Frame(self.content_frame, bg="white")
            self.info_frame.grid(row=0, column=1, sticky="n", pady=10)

            self.class_label = tk.Label(self.info_frame, text="Initializing...", font=("Arial", 14), bg="white", fg="green", wraplength=300, justify="left")
            self.class_label.pack(pady=10)
            
            # Robot arm status
            self.robot_status = tk.Label(
                self.info_frame, 
                text="Robot Arm: " + ("Ready" if self.robot_arm.arm_ready else "Not Connected"), 
                font=("Arial", 12), 
                bg="white", 
                fg="green" if self.robot_arm.arm_ready else "red"
            )
            self.robot_status.pack(pady=10)
            
            # Arduino connection status
            self.arduino_status = tk.Label(
                self.info_frame,
                text=f"Arduino: Connected to {Settings.ARDUINO_PORT}" if self.robot_arm.arm_ready else "Arduino: Not Connected",
                font=("Arial", 12),
                bg="white",
                fg="green" if self.robot_arm.arm_ready else "red"
            )
            self.arduino_status.pack(pady=10)
            
            # --- Control Frame ---
            self.control_frame = tk.Frame(self.content_frame, bg="white")
            self.control_frame.grid(row=1, column=1, sticky="n", pady=10)
            
            # Auto mode toggle
            self.auto_var = tk.BooleanVar(value=False)
            self.auto_check = tk.Checkbutton(
                self.control_frame,
                text="Automatic Robot Control",
                variable=self.auto_var,
                command=self.toggle_auto_mode,
                font=("Arial", 12)
            )
            self.auto_check.pack(pady=5)
            
            # Manual control buttons
            self.manual_frame = tk.Frame(self.control_frame, bg="white")
            self.manual_frame.pack(pady=10)
            
            tk.Button(
                self.manual_frame, 
                text="Handle as Defective", 
                command=lambda: self.manual_robot_action(defective=True),
                bg="#e74c3c",
                fg="white",
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                self.manual_frame, 
                text="Handle as Good", 
                command=lambda: self.manual_robot_action(defective=False),
                bg="#2ecc71",
                fg="white",
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                self.manual_frame, 
                text="Home Position", 
                command=self.reset_robot,
                bg="#3498db",
                fg="white",
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=5)
            
            # Threshold control
            self.threshold_frame = tk.Frame(self.control_frame, bg="white")
            self.threshold_frame.pack(pady=10, fill="x")
            
            tk.Label(
                self.threshold_frame, 
                text="Detection Threshold:", 
                font=("Arial", 10),
                bg="white"
            ).pack(side=tk.LEFT, padx=5)
            
            self.threshold_var = tk.DoubleVar(value=self.detection_threshold)
            self.threshold_slider = tk.Scale(
                self.threshold_frame,
                from_=0.1,
                to=0.9,
                resolution=0.05,
                orient=tk.HORIZONTAL,
                variable=self.threshold_var,
                command=self.update_threshold,
                length=150
            )
            self.threshold_slider.pack(side=tk.LEFT, padx=5)

            # Arduino port selection
            self.port_frame = tk.Frame(self.control_frame, bg="white")
            self.port_frame.pack(pady=10, fill="x")
            
            tk.Label(
                self.port_frame,
                text="Arduino Port:",
                font=("Arial", 10),
                bg="white"
            ).pack(side=tk.LEFT, padx=5)
            
            self.port_var = tk.StringVar(value=Settings.ARDUINO_PORT)
            self.port_entry = tk.Entry(
                self.port_frame,
                textvariable=self.port_var,
                width=10
            )
            self.port_entry.pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                self.port_frame,
                text="Connect",
                command=self.reconnect_arduino,
                bg="#3498db",
                fg="white",
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=5)

            # Camera source selection
            self.camera_frame = tk.Frame(self.control_frame, bg="white")
            self.camera_frame.pack(pady=10, fill="x")
            
            tk.Label(
                self.camera_frame,
                text="Camera Source:",
                font=("Arial", 10),
                bg="white"
            ).pack(side=tk.LEFT, padx=5)
            
            self.camera_var = tk.StringVar(value=Settings.DEFAULT_CAMERA)
            self.camera_dropdown = ttk.Combobox(
                self.camera_frame,
                textvariable=self.camera_var,
                values=list(Settings.CAMERA_SOURCES.keys()),
                width=10,
                state="readonly"
            )
            self.camera_dropdown.pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                self.camera_frame,
                text="Switch Camera",
                command=self.switch_camera,
                bg="#3498db",
                fg="white",
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=5)

            # --- Status Bar ---
            self.status_bar = tk.Label(self.root, text=f"Version: {Settings.VERSION}", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#d9d9d9")
            self.status_bar.pack(side="bottom", fill="x")

            # Start camera frame updates
            self.update_frame()
            
        except Exception as e:
            logging.error(f"Error initializing application: {e}")
            import traceback
            logging.error(traceback.format_exc())
            messagebox.showerror("Initialization Error", f"Failed to initialize application: {e}")
            raise
    
    def reconnect_arduino(self):
        """Attempt to reconnect to Arduino with the current port setting"""
        try:
            if hasattr(self.robot_arm, 'arduino') and self.robot_arm.arm_ready:
                self.robot_arm.arduino.close()
            
            Settings.ARDUINO_PORT = self.port_var.get()
            self.robot_arm = RobotArmController()
            
            self.arduino_status.config(
                text=f"Arduino: Connected to {Settings.ARDUINO_PORT}" if self.robot_arm.arm_ready else "Arduino: Connection Failed",
                fg="green" if self.robot_arm.arm_ready else "red"
            )
            
            self.robot_status.config(
                text="Robot Arm: " + ("Ready" if self.robot_arm.arm_ready else "Not Connected"), 
                fg="green" if self.robot_arm.arm_ready else "red"
            )
            
            if self.robot_arm.arm_ready:
                self.update_status(f"Successfully connected to Arduino on {Settings.ARDUINO_PORT}")
            else:
                self.update_status(f"Failed to connect to Arduino on {Settings.ARDUINO_PORT}")
                
        except Exception as e:
            logging.error(f"Error reconnecting to Arduino: {e}")
            self.update_status(f"Error: {e}")
    
    def switch_camera(self):
        """Switch between available camera sources"""
        try:
            # Release current camera
            if self.cap.isOpened():
                self.cap.release()
            
            # Update settings and try new camera
            new_camera = self.camera_var.get()
            Settings.DEFAULT_CAMERA = new_camera
            
            self.cap = cv2.VideoCapture(Settings.CAMERA_SOURCES[new_camera])
            if not self.cap.isOpened():
                self.update_status(f"Failed to open camera: {new_camera}")
                messagebox.showerror("Camera Error", f"Failed to open camera source: {new_camera}")
                # Try reverting to previous camera
                self.cap = cv2.VideoCapture(0)  # Default fallback
            else:
                self.update_status(f"Switched to camera: {new_camera}")
                
        except Exception as e:
            logging.error(f"Error switching camera: {e}")
            self.update_status(f"Error switching camera: {e}")
            
    def update_frame(self):
        """Update the video frame and process detections"""
        if not hasattr(self, 'cap') or not self.cap.isOpened():
            self.update_status("Camera not available")
            self.root.after(1000, self.update_frame)  # Try again after a delay
            return
            
        try:
            ret, frame = self.cap.read()
            
            if not ret:
                logging.warning("Failed to read from camera")
                self.update_status("Camera error: No frame captured")
                self.root.after(100, self.update_frame)  # Try again after a short delay
                return
            
            # Process the frame with YOLO model
            results = self.detector.predict(frame)
            
            # Draw bounding boxes and get detections
            self.detected_defects = []
            for box in results.boxes:
                conf = float(box.conf[0])
                if conf >= self.detection_threshold:
                    cls_id = int(box.cls[0])
                    cls_name = self.detector.class_names[cls_id]
                    self.detected_defects.append((cls_name, conf))
                    
                    # Draw bounding box
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{cls_name} {conf:.2f}", (x1, y1 - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Update UI with detection results
            if self.detected_defects:
                defect_text = "Detected Defects:\n" + "\n".join([f"- {name} ({conf:.2f})" for name, conf in self.detected_defects])
                self.class_label.config(text=defect_text, fg="red")
                
                # Auto robot control if enabled
                if self.auto_mode and time.time() - self.last_detection_time > self.detection_cooldown:
                    if not self.robot_arm.is_busy and self.robot_arm.arm_ready:
                        threading.Thread(target=self.robot_arm.handle_object, args=(True,)).start()
                        self.last_detection_time = time.time()
            else:
                self.class_label.config(text="No defects detected", fg="green")
            
            # Convert frame for Tkinter display
            frame = cv2.resize(frame, (640, 480))  # Resize for display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            img = ImageTk.PhotoImage(image=img)
            
            self.camera_label.img = img  # Keep a reference to prevent garbage collection
            self.camera_label.config(image=img)
            
        except Exception as e:
            logging.error(f"Error updating frame: {e}")
            self.update_status(f"Frame update error: {e}")
            
        # Schedule the next frame update
        self.root.after(int(1000 / Settings.FRAME_RATE), self.update_frame)

    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_bar.config(text=message)
        logging.info(message)

    def toggle_auto_mode(self):
        """Toggle automatic robot control mode"""
        self.auto_mode = self.auto_var.get()
        status = "enabled" if self.auto_mode else "disabled"
        self.update_status(f"Automatic robot control {status}")

    def manual_robot_action(self, defective=True):
        """Manually trigger robot arm action"""
        if not self.robot_arm.arm_ready:
            self.update_status("Robot arm not connected")
            return
            
        if not self.robot_arm.is_busy:
            threading.Thread(target=self.robot_arm.handle_object, args=(defective,)).start()
            self.update_status("Manual robot action triggered")
        else:
            self.update_status("Robot arm is busy")

    def reset_robot(self):
        """Reset robot to home position"""
        if not self.robot_arm.arm_ready:
            self.update_status("Robot arm not connected")
            return
            
        if not self.robot_arm.is_busy:
            threading.Thread(target=lambda: self.robot_arm.move_to_position(self.robot_arm.positions["home"])).start()
            self.update_status("Robot returning to home position")
        else:
            self.update_status("Robot arm is busy")

    def update_threshold(self, value):
        """Update detection threshold from slider"""
        self.detection_threshold = float(value)
        self.update_status(f"Detection threshold set to {self.detection_threshold:.2f}")

    def on_closing(self):
        """Handle window closing"""
        try:
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()
            if hasattr(self.robot_arm, 'arduino') and self.robot_arm.arm_ready:
                self.robot_arm.arduino.close()
            logging.info("Application closed")
            self.root.destroy()
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")
            self.root.destroy()

def main():
    try:
        app = IntegratedFabricDetectionApp()
        app.root.mainloop()
    except Exception as e:
        logging.error(f"Application error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        messagebox.showerror("Application Error", f"Fatal error: {e}")

if __name__ == "__main__":
    main()