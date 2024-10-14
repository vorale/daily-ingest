import cv2
import numpy as np
from paddleocr import PaddleOCR
import pytesseract
import os
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import psutil
import GPUtil
import logging
import sys

# Set up logging to print to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray)
    thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return thresh

def process_image(image_path):
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
    paddle_result = ocr.ocr(image_path, cls=True)
    
    logging.info(f"OCR result for {image_path}: {paddle_result}")
    
    if paddle_result is None or len(paddle_result) == 0:
        return "No text detected in the image."
    
    text = "\n".join([line[1][0] for result in paddle_result for line in result])
    return text

def log_system_usage():
    # CPU usage
    cpu_percent = psutil.cpu_percent()
    
    # Memory usage
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_usage = memory_info.rss / 1024 / 1024  # in MB
    
    # GPU usage
    gpus = GPUtil.getGPUs()
    gpu_usage = gpus[0].load * 100 if gpus else "N/A"
    
    logging.info(f"CPU Usage: {cpu_percent}% | Memory Usage: {memory_usage:.2f} MB | GPU Usage: {gpu_usage}%")

def process_and_save(source_path, dest_path, tm_daily_ingest):
    # Copy image to tm_daily_ingest folder, replacing if it already exists
    shutil.copy2(source_path, dest_path)
    
    # Process image and save OCR result
    ocr_result = process_image(dest_path)
    base_name = os.path.splitext(os.path.basename(dest_path))[0]
    txt_path = os.path.join(tm_daily_ingest, base_name + ".txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(ocr_result)

    logging.info(f"Processed: {os.path.basename(dest_path)}")
    log_system_usage()

def main(max_workers):
    # 1. Create tm_daily_ingest folder
    downloads_folder = os.path.expanduser("~/Downloads")
    tm_daily_ingest = os.path.join(downloads_folder, "tm_daily_ingest")
    os.makedirs(tm_daily_ingest, exist_ok=True)

    # 2. Search for images in Desktop folder
    desktop_folder = os.path.expanduser("~/Desktop")
    screenshot_files = [f for f in os.listdir(desktop_folder) if f.startswith("Screenshot")]
    
    # 3. Filter out already processed files
    to_process = []
    for screenshot in screenshot_files:
        base_name = os.path.splitext(screenshot)[0]
        if not os.path.exists(os.path.join(tm_daily_ingest, base_name + ".txt")):
            to_process.append(screenshot)

    # Sort files by creation time
    to_process.sort(key=lambda x: os.path.getctime(os.path.join(desktop_folder, x)))

    # 4. Process files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for screenshot in to_process:
            source_path = os.path.join(desktop_folder, screenshot)
            dest_path = os.path.join(tm_daily_ingest, screenshot)
            futures.append(executor.submit(process_and_save, source_path, dest_path, tm_daily_ingest))

        # Wait for all tasks to complete
        for future in as_completed(futures):
            future.result()  # This will raise any exceptions that occurred during processing

    logging.info("All files processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process images with OCR")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads (default: 4)")
    args = parser.parse_args()

    main(args.workers)
