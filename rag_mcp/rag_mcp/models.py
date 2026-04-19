"""Data models for RAG MCP (ARCHITECTURE.md § Assinaturas exatas das tools MCP).

These models are frozen in ADR-0007. Any field change requires a new ADR.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExamEntry(BaseModel):
    """Internal catalog record loaded from exams.csv.

    Invariant (AC6, AC14):
        code is unique across all entries in the catalog.

    Attributes:
        name: Canonical exam name (e.g. 'Hemograma Completo').
        code: Canonical exam code (e.g. 'HMG-001').
        category: Clinical group (e.g. 'hematologia').
        aliases: Alternative names, e.g. ['Hemograma', 'HMG', 'HMC'].
    """

    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("name", "code", "category", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip surrounding whitespace from string fields.

        Args:
            v: Raw string value from CSV.

        Returns:
            Stripped string.
        """
        return v.strip()


class ExamMatch(BaseModel):
    """Return type of search_exam_code — a successful fuzzy match result.

    Invariant (AC13):
        score is in [0.0, 1.0]. Never None inside this model.
        None return from the tool indicates *no match* below threshold.

    Attributes:
        name: Canonical exam name from the catalog.
        code: Canonical exam code.
        score: Normalized match score in [0.0, 1.0] (rapidfuzz score / 100).
    """

    name: str
    code: str
    score: float = Field(..., ge=0.0, le=1.0)

    @field_validator("score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        """Validate score is strictly in [0.0, 1.0].

        Args:
            v: Raw score value.

        Returns:
            Validated score.

        Raises:
            ValueError: If score is outside [0.0, 1.0].
        """
        if not (0.0 <= v <= 1.0):
            msg = f"score must be in [0.0, 1.0], got {v}"
            raise ValueError(msg)
        return v


class ExamSummary(BaseModel):
    """Lightweight catalog entry for list_exams().

    Attributes:
        name: Canonical exam name.
        code: Canonical exam code.
    """

    name: str
    code: str
