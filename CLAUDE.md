# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Always use `uv run` to run python commands
- Run the OCR script: `uv run python main.py <image_path>`
- Test with sample image: `uv run python main.py test.png`
- Install dependencies: `uv sync`

## Code Architecture

This is a YouTube OCR tool that extracts social media usernames from images using dual OCR engines:

- **Dual OCR approach**: Uses both Pytesseract and EasyOCR for better accuracy
- **GPU acceleration**: EasyOCR optimized with MPS/CUDA for performance
- **Username filtering**: Regex patterns exclude email addresses and common TLDs (.com, .org, .net, .edu, .gov, .mil, .int, .biz, .info, .name)
- **Output format**: Saves extracted usernames to `extracted_usernames.txt`

## Performance Configuration

### EasyOCR Environment Variables

- `EASYOCR_GPU=true` (auto-detected): Enable MPS/CUDA GPU acceleration
- `EASYOCR_QUANTIZE=false` (default): Enable quantization for CPU optimization
- `EASYOCR_MODEL=DBNet` (default): Text detection model
  - `DBNet`: Typically faster detection
  - `CRAFT`: More accurate detection
- Auto-detects Apple Silicon MPS, CUDA, or falls back to CPU

## Key Functions

- `extract_usernames_pytesseract()`: Primary OCR using Pytesseract
- `extract_usernames_easyocr()`: Secondary OCR using EasyOCR with GPU optimization
- `extract_usernames_simple()`: Simplified Pytesseract-only extraction
- `get_easyocr_reader()`: EasyOCR reader with MPS optimization
- `detect_optimal_device()`: Auto-detects best GPU acceleration (MPS/CUDA)
- `main()`: Orchestrates OCR engines sequentially with performance timing

## Testing Requirements

When testing main.py, ensure the generated txt file contains only canonical usernames starting with `@` without internal field separators (e.g., @AYEON, @albertatech). No email addresses or TLD patterns should be included.

## Linting

- Follow linting from .markdownlint.jsonc and .editorconfig

## Development Best Practices

- When creating directories, always use `mkdir -p` in case it already exists

## Testing

- Run tests: `uv run pytest tests/ -v`
- Test image located at: `tests/test.png`
- Integration tests verify OCR accuracy and email filtering

## Performance Measurement

Use [hyperfine](https://github.com/sharkdp/hyperfine) to benchmark OCR performance with `--runs 3` for reliable measurements.

### Benchmark Commands

```bash
# Compare detection models (DBNet vs CRAFT)
hyperfine --runs 3 --parameter-list model DBNet,CRAFT \
  "EASYOCR_MODEL={model} uv run python main.py tests/test.png"

# Compare GPU vs CPU performance
hyperfine --runs 3 --parameter-list gpu true,false \
  "EASYOCR_GPU={gpu} uv run python main.py tests/test.png"

# Compare quantization settings
hyperfine --runs 3 --parameter-list quantize true,false \
  "EASYOCR_QUANTIZE={quantize} uv run python main.py tests/test.png"

# Comprehensive performance matrix
hyperfine --runs 3 \
  --parameter-list model DBNet,CRAFT \
  --parameter-list gpu true,false \
  --parameter-list quantize true,false \
  "EASYOCR_MODEL={model} EASYOCR_GPU={gpu} EASYOCR_QUANTIZE={quantize} uv run python main.py tests/test.png"
```

### Expected Performance Characteristics

Based on local benchmarks (Apple Silicon M3):

- **DBNet**: Faster detection (4.41s vs 4.52s), optimal for speed
- **CRAFT**: Slightly slower but more accurate detection
- **GPU=true**: 17% speedup (4.4s vs 5.1s) on Apple Silicon MPS
- **QUANTIZE=false**: Optimal with GPU (4.41s vs 4.47s)
- **QUANTIZE=true**: Better for CPU-only scenarios

**Optimal Configuration**: `DBNet + GPU=true + QUANTIZE=false` (4.41s average)