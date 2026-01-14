# Copilot Instructions for Sejm Audit Tool

## Project Overview

This repository contains tools for downloading and analyzing legislative processes from the Polish Parliament (Sejm). The project includes:

- **sejm_process_downloader.py**: Simple downloader for individual legislative processes
- **sejm_process_downloader.ipynb**: Jupyter Notebook version for cloud environments
- **main.py**: Heavy audit mode scanner with OCR and risk analysis
- **demo.py**: Demonstration script

## Programming Languages & Frameworks

- **Primary Language**: Python 3
- **Key Libraries**: 
  - requests (HTTP requests)
  - BeautifulSoup4 (web scraping)
  - pandas (data analysis)
  - PaddleOCR (OCR processing)
  - pypdf, pdf2image (PDF processing)
  - openpyxl, xlrd, python-docx (document processing)

## Code Style & Conventions

### General Guidelines

1. **Language**: Code comments and documentation should be in **Polish** to match the domain (Polish Parliament data)
2. **Encoding**: Always use UTF-8 encoding with `# -*- coding: utf-8 -*-` header
3. **Shebang**: Use `#!/usr/bin/env python3` for executable scripts
4. **String Formatting**: Prefer f-strings for string formatting
5. **Type Hints**: Use type hints where appropriate (e.g., `Dict`, `List`, `Optional`)

### Naming Conventions

- **Variables**: Use `snake_case` (e.g., `process_number`, `output_dir`)
- **Constants**: Use `UPPER_SNAKE_CASE` (e.g., `API_URL`, `TERM`, `DOWNLOAD_ATTACHMENTS`)
- **Functions**: Use `snake_case` with descriptive names
- **Classes**: Use `PascalCase` (if adding any)

### Configuration

- Configuration variables should be defined at the top of files in a dedicated section
- Use clear section headers with ASCII art for better readability:
  ```python
  # ==============================================================================
  # KONFIGURACJA
  # ==============================================================================
  ```

### Comments

- Use emoji prefixes for important messages (e.g., `⚠️`, `✅`, `🔍`, `📁`)
- Document functions with docstrings in Polish when the function is domain-specific
- Use English docstrings for generic utility functions

## Dependencies & Security

### Dependency Management

- All dependencies are listed in `requirements.txt`
- **Critical**: PaddlePaddle must be pinned to version 3.0.0 to avoid security vulnerabilities (CVEs in <= 2.6.0)
- PaddleOCR must be >= 2.8.1 for compatibility
- NumPy must be < 2.0.0 for PaddlePaddle compatibility

### Security Considerations

**IMPORTANT**: Follow security guidelines in `SECURITY.md`:

1. **Never use vulnerable PaddlePaddle functions**:
   - Do NOT use `paddle.vision.ops.read_file`
   - Do NOT use `paddle.utils.download._wget_download`
   - Only use PaddleOCR high-level API

2. **Input Validation**:
   - Validate all API responses from sejm.gov.pl
   - Use timeout protection on network requests
   - Process PDFs in memory (no direct file system access via Paddle)

3. **Credential Handling**:
   - Mask proxy credentials in logs
   - Store credentials in environment variables
   - Never hardcode secrets

4. **Network Security**:
   - Implement retry mechanisms with exponential backoff
   - Handle rate limiting (HTTP 429)
   - Use timeouts on all requests

## API Usage

### Sejm API

- **Base URL**: `https://api.sejm.gov.pl/sejm`
- **Web URL**: `https://www.sejm.gov.pl`
- **Current Term**: 10 (X kadencja)

### API Patterns

- Use `requests` library for all HTTP calls
- Handle JSON responses from the API
- Implement proper error handling for network failures
- Respect rate limits and use appropriate delays

## File Processing

### PDF Processing

- Use `pypdf.PdfReader` for text extraction
- Use `pdf2image.convert_from_bytes` for converting PDFs to images
- Use `PaddleOCR.ocr()` for OCR processing
- Always process files in memory when possible

### Output Files

The project creates structured output:
- `process_data.json` - Raw JSON data
- `drzewo_struktury.txt` - Process structure tree (ASCII)
- `drzewo_chronologiczne.txt` - Timeline of events
- `raport_podsumowujacy.txt` - Summary report
- Downloaded attachments in organized folders

## Testing & Validation

### Manual Testing

- Test with example process number 471 (well-documented case)
- Verify downloads are saved to correct directories
- Check that JSON output is valid
- Validate generated reports for completeness

### System Dependencies

**Linux/Ubuntu**:
```bash
sudo apt-get install poppler-utils libgl1
```

### Installation & Setup

```bash
# Basic setup (for sejm_process_downloader.py)
pip install requests beautifulsoup4

# Full setup (for main.py)
pip install -r requirements.txt
```

## Error Handling

- Use try-except blocks for network operations
- Provide clear error messages in Polish for domain-specific errors
- Log important operations with emoji prefixes for visibility
- Handle missing optional dependencies gracefully (e.g., BeautifulSoup)

## Code Organization

### Import Order

1. Standard library imports
2. Third-party library imports
3. Local application imports

### Function Organization

- Check system dependencies at the start (if needed)
- Define configuration constants
- Define utility functions
- Define main processing functions
- Include main execution block with `if __name__ == '__main__':`

## Performance Considerations

- Use `concurrent.futures` for parallel processing when appropriate
- Implement progress indicators for long-running operations
- Cache API responses when reasonable
- Use efficient data structures (pandas DataFrame for tabular data)

## Documentation

- Keep README.md up to date with usage examples
- Document configuration options clearly
- Provide quick start instructions for different platforms (Windows, Linux, Mac, Jupyter)
- Include links to relevant Sejm resources

## Jupyter Notebook Compatibility

- Ensure code works in both script and notebook formats
- Test compatibility with cloud platforms (Vast.ai, Google Colab)
- Provide clear cell-by-cell execution instructions

## Common Patterns

### Configuration Pattern
```python
TERM = 10  # Kadencja
PROCESS_NUMBER = 471  # Numer druku
OUTPUT_DIR = f"druk_{PROCESS_NUMBER}_dokumentacja"
DOWNLOAD_ATTACHMENTS = True
```

### API Request Pattern
```python
response = requests.get(url, timeout=30)
response.raise_for_status()
data = response.json()
```

### Logging Pattern
```python
print(f"🔍 [INFO] Processing document: {doc_name}")
print(f"⚠️  [WARNING] Failed to download: {url}")
print(f"✅ [SUCCESS] Completed successfully")
```

## When Making Changes

1. **Preserve existing functionality** - This tool is actively used for civic oversight
2. **Test with real Sejm data** - Use process 471 as a reference
3. **Maintain Polish language context** - Comments and messages should remain in Polish
4. **Follow security guidelines** - Always check SECURITY.md before modifying dependencies
5. **Keep it simple** - The tool should work on basic Python installations when possible
6. **Consider multiple platforms** - Test on Windows, Linux, and Jupyter environments

## Additional Notes

- The project analyzes Polish legislative processes, so domain knowledge of parliamentary procedures is helpful
- Output files use Polish language for headers and descriptions
- Date formats should follow ISO 8601 or Polish conventions
- File naming should use underscores and be descriptive in Polish
