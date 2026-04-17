# =============================================================================
# backend/main.py  —  Phase 7 revision
# Changes: quiz_data in response, history param, quiz auto-parse
# =============================================================================

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, Field
from typing import Literal

from backend.config import (
    ALLOWED_ORIGINS, RATE_LIMIT_PER_MINUTE,
    WHATSAPP_VERIFY_TOKEN, ACTIVE_LLM, LLM_SPECS, ACTIVE_PROVIDER,
)
from backend import core
from backend.whatsapp import (
    parse_incoming_message, detect_task_from_message,
    send_whatsapp_message, format_for_whatsapp,
    send_welcome_message, is_greeting, GREETING_REPLY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")
_welcomed: set[str] = set()


# =============================================================================
# REQUEST / RESPONSE MODELS  (defined here to include quiz_data)
# =============================================================================

TaskType = Literal["ask", "reference", "explain", "quiz", "summarise"]


class SourceVerse(BaseModel):
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


class ConversationMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    task:        TaskType               = Field(default="ask")
    query:       str                    = Field(..., min_length=1, max_length=1000)
    book_filter: list[str]              = Field(default=[])
    top_n:       int                    = Field(default=5, ge=1, le=15)
    scope:       str | None             = Field(default=None)
    history:     list[ConversationMessage] = Field(default=[])
    use_expansion: bool                 = Field(default=True)


class AskResponse(BaseModel):
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


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    core.startup()
    yield
    logger.info("Shutdown.")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Prabhupada RAG API",
    description="RAG over Srila Prabhupada's books — BG, ISO, NOI, BS",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# =============================================================================
# ROUTES
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    return HealthResponse(
        status="ok",
        db_count=core.get_db_count(),
        llm_provider=ACTIVE_LLM,
        llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
        embed_provider=ACTIVE_PROVIDER,
    )


@app.post("/api/ask", response_model=AskResponse, tags=["RAG"])
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def ask(request: Request, body: AskRequest):
    logger.info(f"POST /api/ask | task={body.task} | query={body.query[:60]!r}")

    try:
        book_filter = body.book_filter or []

        # Auto-parse quiz intent from natural language
        if body.task == "quiz":
            num_questions, book_code, chapter = core.parse_quiz_intent(body.query)
            effective_scope   = book_code or (body.scope if body.scope else None)
            effective_chapter = chapter
            # top_n passed to generate() = question count; retrieval uses its own limit
            quiz_top_n = num_questions
        else:
            quiz_top_n        = body.top_n
            effective_scope   = body.scope
            effective_chapter = None

        # Retrieve
        if body.task in ("quiz", "summarise") and effective_scope:
            scope = effective_scope.lower().strip()
            if scope in ("bg", "iso", "noi", "bs"):
                if effective_chapter and scope == "bg":
                    # Chapter-specific: fetch all verses in that chapter
                    results = core.retrieve_by_chapter(scope, effective_chapter)
                else:
                    # Whole-book: fetch a broad random sample for variety
                    results = core.retrieve_by_scope(
                        scope, top_n=max(quiz_top_n * 3, 20)
                    )
            else:
                results = core.retrieve(
                    query=body.query, top_n=quiz_top_n,
                    book_filter=book_filter, use_expansion=body.use_expansion,
                )
        else:
            results = core.retrieve(
                query=body.query, top_n=body.top_n,
                book_filter=book_filter, use_expansion=body.use_expansion,
            )

        # Convert history
        history = [{"role": m.role, "content": m.content}
                   for m in body.history] if body.history else []

        # Generate — pass question count as top_n for quiz, else use body.top_n
        effective_top_n = quiz_top_n if body.task == "quiz" else body.top_n
        response = core.generate(
            task=body.task, query=body.query,
            results=results, top_n=effective_top_n, history=history,
        )

    except Exception as e:
        logger.exception(f"Error in /api/ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    sources = [
        SourceVerse(
            reference=r.reference, book=r.book, book_code=r.book_code,
            verse_sanskrit=r.verse_sanskrit, word_for_word=r.word_for_word,
            translation=r.translation, purport=r.purport,
            part=r.part, total_parts=r.total_parts,
            vector_score=r.vector_score, rerank_score=r.rerank_score,
            direct_lookup=r.direct_lookup,
        )
        for r in response.sources
    ]

    return AskResponse(
        task=response.task, query=response.query, answer=response.answer,
        sources=sources, context_used=response.context_used,
        is_direct=response.is_direct, llm_model=response.llm_model,
        mode=response.mode, quiz_data=response.quiz_data,
    )


# =============================================================================
# WHATSAPP
# =============================================================================

@app.get("/whatsapp/webhook", tags=["WhatsApp"])
async def whatsapp_verify(
    hub_mode:          str = Query(alias="hub.mode",          default=""),
    hub_challenge:     str = Query(alias="hub.challenge",     default=""),
    hub_verify_token:  str = Query(alias="hub.verify_token",  default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/whatsapp/webhook", tags=["WhatsApp"])
async def whatsapp_incoming(request: Request):
    payload = await request.json()
    parsed  = parse_incoming_message(payload)
    if parsed is None:
        return {"status": "ok"}
    sender, text = parsed
    asyncio.create_task(_process_whatsapp(sender, text))
    return {"status": "ok"}


async def _process_whatsapp(sender: str, text: str):
    try:
        # Welcome first-time senders
        is_new = sender not in _welcomed
        if is_new:
            _welcomed.add(sender)
            await send_welcome_message(to=sender)

        # Greeting-only messages: avoid costly RAG call
        if is_greeting(text):
            if not is_new:
                await send_whatsapp_message(to=sender, text=GREETING_REPLY)
            return

        task, query = detect_task_from_message(text)
        loop        = asyncio.get_event_loop()

        if task == "quiz":
            num_q, book_code, chapter = core.parse_quiz_intent(query)
            num_q = min(num_q, 5)  # keep WA answers compact

            if book_code and chapter and book_code == "bg":
                results = await loop.run_in_executor(
                    None, lambda: core.retrieve_by_chapter(book_code, chapter)
                )
            elif book_code:
                results = await loop.run_in_executor(
                    None, lambda: core.retrieve_by_scope(book_code, top_n=max(num_q * 3, 15))
                )
            else:
                results = await loop.run_in_executor(
                    None, lambda: core.retrieve(query=query, top_n=num_q)
                )

            response = await loop.run_in_executor(
                None, lambda: core.generate(task=task, query=query, results=results, top_n=num_q)
            )
        else:
            results  = await loop.run_in_executor(
                None, lambda: core.retrieve(query=query, top_n=4)
            )
            response = await loop.run_in_executor(
                None, lambda: core.generate(task=task, query=query, results=results, top_n=4)
            )

        reply = format_for_whatsapp(task, response.answer,
                                    response.sources, response.context_used)
        await send_whatsapp_message(to=sender, text=reply)
    except Exception as e:
        logger.exception(f"WhatsApp error for {sender}: {e}")
        await send_whatsapp_message(
            to=sender,
            text="Hare Krishna! Sorry, I encountered an error. Please try again.",
        )