"""RAG MCP server — fuzzy exam code lookup over a SIGTAP-derived catalog.

Exposes tools:
    search_exam_code(exam_name: str) -> ExamMatch | None
    list_exams(limit: int = 100) -> list[ExamSummary]

Transport: SSE on port 8002 (ADR-0001).
Catalog: rag_mcp/data/exams.csv, >= 100 rows, UTF-8, columns: name,code,category,aliases.
Matching: rapidfuzz WRatio, threshold 80 (ADR-0007).
"""
