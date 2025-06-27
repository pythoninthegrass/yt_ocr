#!/usr/bin/env python

import csv
import easyocr
import platform
import pytesseract
import re
import sys
import warnings
from decouple import config
from pathlib import Path
from PIL import Image

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

file_name = config("FILE_NAME", default="extracted_usernames.csv")

# Suppress PyTorch MPS pin_memory warning on macOS
warnings.filterwarnings("ignore", message=".*pin_memory.*not supported on MPS.*")

# Global EasyOCR reader instance
_easyocr_reader = None


def detect_optimal_device():
    """Detect the optimal device for EasyOCR processing."""
    if not TORCH_AVAILABLE:
        return False, "CPU (PyTorch not available)"

    # Check for Apple Silicon MPS support
    if platform.system() == "Darwin" and torch.backends.mps.is_available():
        return True, "MPS (Apple Silicon GPU)"

    # Check for CUDA support
    if torch.cuda.is_available():
        return True, f"CUDA (GPU {torch.cuda.get_device_name()})"

    return False, "CPU (No GPU acceleration available)"

# Username pattern that excludes email addresses
USERNAME_PATTERN = re.compile(r"""
@(?!(?:
    # Common email providers (with or without dots)
    # * `gmall` [sic] is included due to ocr consistently returning it
    aol(?:\.?com)?|
    gmail(?:\.?com)?|
    gmall(?:\.?com)?|
    hotmail(?:\.?com)?|
    icloud(?:\.?com)?|
    outlook(?:\.?com)?|
    proton(?:\.?(?:me))?|
    yahoo(?:\.?com)?|
    # General email pattern with TLDs
    [a-zA-Z0-9]*\.(?:com|org|net|edu|gov|mil|int|biz|info|name)
)(?:\s|$))[a-zA-Z0-9_]+
""", re.VERBOSE)


def get_easyocr_reader():
    """Get EasyOCR reader instance with MPS optimization and model selection."""
    global _easyocr_reader
    if _easyocr_reader is None:
        # Auto-detect optimal device or use config override
        optimal_gpu, device_info = detect_optimal_device()
        use_gpu = config("EASYOCR_GPU", default=str(optimal_gpu), cast=bool)
        use_quantization = config("EASYOCR_QUANTIZE", default="false", cast=bool)
        model = config("EASYOCR_MODEL", default="DBNet")

        print(f"EasyOCR Device: {device_info}")
        print(f"Initializing EasyOCR with GPU={use_gpu}, Quantization={use_quantization}, Model={model}")

        _easyocr_reader = easyocr.Reader(
            ['en'],
            gpu=use_gpu,
            quantize=use_quantization,
            model_storage_directory=None,
            download_enabled=True,
            detector=model,
            verbose=False
        )
    return _easyocr_reader


def extract_usernames_pytesseract(image_path):
    """
    Extract usernames using Pytesseract OCR.

    Args:
        image_path (str): Path to the image file

    Returns:
        list: List of usernames found
    """
    try:
        # Open the image
        image = Image.open(image_path)

        # Perform OCR
        text = pytesseract.image_to_string(image)

        # Find all matches using the global USERNAME_PATTERN
        matches = USERNAME_PATTERN.findall(text)

        # Remove duplicates while preserving order
        unique_matches = list(dict.fromkeys(matches))

        return unique_matches

    except Exception as e:
        print(f"Error with Pytesseract: {e}")
        return []


def extract_usernames_easyocr(image_path):
    """
    Extract usernames using EasyOCR with thread-safe reader.

    Args:
        image_path (str): Path to the image file

    Returns:
        list: List of usernames found
    """
    try:
        # Get thread-local EasyOCR reader for thread safety
        reader = get_easyocr_reader()

        # Perform OCR
        results = reader.readtext(image_path)

        # Combine all text
        text = ' '.join([result[1] for result in results])

        # Find all matches using the global USERNAME_PATTERN
        matches = USERNAME_PATTERN.findall(text)

        # Remove duplicates while preserving order
        unique_matches = list(dict.fromkeys(matches))

        return unique_matches

    except Exception as e:
        print(f"Error with EasyOCR: {e}")
        return []


def extract_usernames_simple(image_path):
    """
    Simple function to extract usernames using only Pytesseract.

    Args:
        image_path (str): Path to the image file

    Returns:
        list: List of usernames found
    """
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)

        # Find all matches using the global USERNAME_PATTERN
        matches = USERNAME_PATTERN.findall(text)

        return list(dict.fromkeys(matches))

    except Exception as e:
        print(f"Error: {e}")
        return []


def main():
    # Check if image path is provided
    if len(sys.argv) < 2:
        print("Usage:\n\tpython main.py <image_path>")
        print("Example:\n\tpython main.py screenshot.png")
        print("Example:\n\tpython main.py tests/test.png")
        exit(0)

    image_path = sys.argv[1]

    # Check if file exists, if not try in tests directory
    if not Path(image_path).exists():
        # Try looking in tests directory
        test_path = Path("tests") / image_path
        if test_path.exists():
            image_path = str(test_path)
            print(f"Found image in tests directory: {image_path}")
        else:
            print(f"Error: Image file '{sys.argv[1]}' not found.")
            print(f"Tried: {sys.argv[1]} and {test_path}")
            print("Available test image: tests/test.png")
            exit(1)

    print(f"Processing image: {image_path}\n")

    print("=== Processing OCR Engines ===")

    print("--- Processing with Pytesseract ---")
    pytesseract_results = extract_usernames_pytesseract(image_path)

    print("--- Processing with EasyOCR ---")
    easyocr_results = extract_usernames_easyocr(image_path)

    # Display results
    print("\n=== Pytesseract Results ===")
    if pytesseract_results:
        print("Found usernames:")
        for username in pytesseract_results:
            print(f"  {username}")
    else:
        print("No usernames found or Pytesseract not available.")

    print("\n=== EasyOCR Results ===")
    if easyocr_results:
        print("Found usernames:")
        for username in easyocr_results:
            print(f"  {username}")
    else:
        print("No usernames found or EasyOCR not available.")

    # Combine results from both OCR engines and remove duplicates
    all_results = list(dict.fromkeys(pytesseract_results + easyocr_results))

    print("\n=== Combined Unique Results ===")
    if all_results:
        print("All unique usernames found:")
        for username in all_results:
            print(f"  {username}")

        # Save to CSV file
        with open(file_name, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(['username', 'url', 'channel'])
            # Write usernames with empty url and channel fields for now
            for username in all_results:
                writer.writerow([username, '', ''])
        print(f"\nResults saved to '{file_name}'")
    else:
        print("No usernames found in the image.")


if __name__ == "__main__":
    main()
