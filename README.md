# 🔍 Fabric Defect Detection - Static Images

A robust application for detecting and analyzing defects in fabric images using deep learning object detection techniques.

## 📁 Project Structure

```
D:\Fabrics-Defect-Detection\Model_Fabric_Defect_Detection\
├── config/               # Configuration files for model and application settings
├── core/                 # Core logic for defect detection and image processing
├── detected_objects/     # Output directory for images with detected defects
├── ui/                   # User interface components
└── main.py               # Main application entry point
```

## 🎯 Purpose

This application provides a streamlined workflow to:
- Detect fabric defects in static images using computer vision
- Classify defects into predefined categories
- Generate visual reports of detected defects
- Support quality control in textile manufacturing

## ✨ Features

- **Multiple Defect Detection**: Identifies various fabric defects including holes, tears, stains, contamination, and thread abnormalities
- **Visual Marking**: Highlights detected defects with bounding boxes and labels
- **Confidence Scoring**: Provides confidence scores for each detection
- **Batch Processing**: Processes multiple images in sequence
- **Results Export**: Saves detection results for documentation and further analysis

## 🚀 Getting Started

### Prerequisites

```bash
pip install -r requirements.txt
```

### Running the Application

```bash
python main.py --image-dir "path/to/images" --output-dir "detected_objects"
```

#### Command-line Arguments

- `--image-dir`: Directory containing fabric images to process
- `--output-dir`: Directory where detected images will be saved (default: detected_objects)
- `--conf-threshold`: Confidence threshold for detections (default: 0.5)
- `--model-path`: Path to the detection model file (default: config/models/best.pt)
- `--gui`: Launch the graphical user interface (flag)

## 📋 Detection Classes

The model can detect the following fabric defects:
1. Holes
2. Tears/Cuts
3. Oil Stains
4. Color Variations
5. Thread Defects
6. Folding Marks
7. Pattern Misalignments

## 🖥️ User Interface

The application includes a user-friendly interface with:
- Image preview panel
- Detection results summary
- Settings adjustment panel
- Batch processing controls
- Export functionality

To launch the GUI:
```bash
python main.py --gui
```

## 📊 Sample Detection Output

When defects are detected in an image, the application:
1. Draws bounding boxes around identified defects
2. Labels each defect with its class and confidence score
3. Saves the marked image to the `detected_objects` directory
4. Generates a JSON file with detailed detection information

## 🔧 Project Components

### Config Module
Contains configuration files for:
- Model parameters
- Detection thresholds
- Class definitions
- Application settings

### Core Module
Implements the fundamental detection logic:
- Image preprocessing
- Model inference
- Post-processing results
- Detection visualization

### UI Module
Provides the graphical interface components:
- Main application window
- Image selection dialogs
- Results display
- Settings panels

## 🛠️ Advanced Usage

### Customizing Detection Parameters

Edit `config/detection_config.yaml` to adjust:
- Detection thresholds
- Visualization settings
- Class colors

### Processing Large Batches

For large image sets:
```bash
python main.py --image-dir "extensive_dataset" --batch-size 32 --no-display
```

## 📌 TODO

- [ ] Add real-time processing with webcam support
- [ ] Implement defect measurement functionality
- [ ] Add reporting features with statistics and analytics
- [ ] Support for export to multiple formats (CSV, PDF)
- [ ] Integration with automated quality control systems

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Projects

- [Fabric Defect Dataset](https://github.com/yourusername/fabric-defect-dataset)
- [YOLOv11 Training Pipeline](https://github.com/yourusername/yolov11-training)
