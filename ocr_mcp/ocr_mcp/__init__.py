"""OCR MCP server — extracts exam names from medical order images (mock, deterministic).

Exposes tool: extract_exams_from_image(image_base64: str) -> list[str]
Transport: SSE on port 8001 (ADR-0001).
PII: security.pii_mask() applied on every return value (ADR-0003 line 1).
"""
