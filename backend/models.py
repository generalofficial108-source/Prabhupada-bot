# =============================================================================
# backend/models.py
# Single source of truth for all Pydantic request/response models.
# Kept in sync with main.py and core.py GeneratedResponse.
# =============================================================================

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class SourceVerse(BaseModel):
    """A single retrieved verse with all its fields."""
    reference:      str
    book:           str
    book_code:      str
    verse_sanskrit: str
    word_for_word:  str
    translation:    str
    purport:        str
    part:           int
    total_parts:    int
    vector_score:   float
    rerank_score:   float
    direct_lookup:  bool


TaskType = Literal["ask", "reference", "explain", "quiz", "summarise"]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    """Universal request body — used for all task types."""
    task:           TaskType                    = Field(default="ask")
    query:          str                         = Field(..., min_length=1, max_length=1000)
    book_filter:    list[str]                   = Field(default=[])
    top_n:          int                         = Field(default=5, ge=1, le=15)
    scope:          str | None                  = Field(default=None)
    history:        list[ConversationMessage]   = Field(default=[])
    use_expansion:  bool                        = Field(default=True)

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "task":   "ask",
                    "query":  "What is the nature of the eternal soul?",
                    "book_filter": [],
                    "top_n": 5,
                },
                {
                    "task":   "reference",
                    "query":  "BG 2.47",
                    "book_filter": ["bg"],
                    "top_n": 1,
                },
                {
                    "task":   "quiz",
                    "query":  "Make 10 MCQs from Nectar of Instruction",
                    "scope":  "noi",
                    "top_n":  10,
                },
            ]
        }


class WhatsAppWebhookRequest(BaseModel):
    """Incoming webhook payload from Meta WhatsApp Cloud API."""
    object: str
    entry:  list[dict]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AskResponse(BaseModel):
    """Universal response body — returned for all task types."""
    task:         TaskType
    query:        str
    answer:       str
    sources:      list[SourceVerse]
    context_used: list[str]
    is_direct:    bool
    llm_model:    str
    mode:         str
    quiz_data:    list[dict] | None = None   # parsed MCQs for quiz task


class HealthResponse(BaseModel):
    status:         str
    db_count:       int
    llm_provider:   str
    llm_model:      str
    embed_provider: str


class QuizQuestion(BaseModel):
    question:    str
    options:     list[str]   # exactly 4 options
    answer:      str         # the correct option text
    reference:   str         # source verse reference
    explanation: str         # one-sentence explanation


class QuizResponse(BaseModel):
    scope:     str
    questions: list[QuizQuestion]
    llm_model: str