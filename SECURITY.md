# Security Policy

## Dependency Security

### PaddlePaddle Vulnerabilities (Addressed)

**Issue**: PaddlePaddle versions <= 2.6.0 contain multiple critical vulnerabilities:
- Arbitrary file read via `paddle.vision.ops.read_file`
- Command injection in `paddle.utils.download._wget_download`
- Remote code execution vulnerability
- Path traversal vulnerability

**Resolution**: 
- **Updated to PaddlePaddle 3.0.0** (Latest stable version without known vulnerabilities)
- Updated PaddleOCR to >= 2.8.1 for compatibility

**Mitigation**: The application does not use any of the vulnerable functions:
- Does NOT use `paddle.vision.ops.read_file`
- Does NOT use `paddle.utils.download._wget_download`
- Only uses PaddleOCR high-level API (`PaddleOCR.ocr()`)
- Does NOT download models from untrusted sources

## Security Best Practices

### Input Validation
- All PDF files are processed in memory (no direct file system access via Paddle)
- API responses from sejm.gov.pl are validated before processing
- Network requests use timeout protection

### Proxy Security
- Proxy credentials are masked in logs
- Credentials stored in environment variables (not in code)
- HTTPS proxy support for encrypted traffic

### File Processing
- PDFs are processed through PyPDF and pdf2image libraries
- OCR processing is isolated to in-memory operations
- No user-controlled file paths in Paddle operations

### Network Security
- Robust retry mechanism with exponential backoff
- Rate limiting awareness (429 handling)
- Timeout protection on all network requests

## Reporting Security Issues

If you discover a security vulnerability in this project:
1. Do NOT open a public issue
2. Contact the repository maintainers privately
3. Provide details about the vulnerability and steps to reproduce

## Security Checklist

- [x] Updated PaddlePaddle to version 3.0.0 (no known CVEs)
- [x] Updated PaddleOCR to compatible version (>= 2.8.1)
- [x] Verified no use of vulnerable Paddle functions
- [x] Input validation on all external data
- [x] Credential masking in logs
- [x] No hardcoded secrets
- [x] Timeout protection on network requests
- [x] Safe file handling (memory-based processing)

## Dependency Monitoring

Regularly check for security updates:
```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade paddlepaddle paddleocr
```

## Version History

### 2026-01-12
- **Security Fix**: Updated PaddlePaddle from 2.6.0 to 3.0.0
- **Reason**: Multiple CVEs in versions <= 2.6.0
- **Impact**: Eliminates 5 critical vulnerabilities
- **Status**: No breaking changes to application functionality
