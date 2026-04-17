# =============================================================================
# generate.py
# Phase 5 — LLM response generation.
#
# KEY FIXES vs previous version:
#   1. SYSTEM_PROMPT is much stricter — explicitly forbids referencing verse
#      numbers not present in the provided sources (fixes hallucination of
#      BG 3.25 etc.)
#   2. Word-for-word is now included in the context block when the query
#      is a direct lookup — so "give me BG 3.9 word-for-word" works.
#   3. Direct lookup queries get a special prompt that instructs the LLM
#      to display all fields (Sanskrit, word-for-word, translation, purport).
# =============================================================================

import os
import logging
from dataclasses import dataclass, field

from retrieve import RetrievalResult

from dotenv import load_dotenv
from groq import Groq

# load env variables
load_dotenv()

# ---------------------------------------------------------------------------
# ┌──────────────────────────────────────────────────┐
# │         CHANGE ONLY THIS ONE LINE                │
# │  Options: "gemini"  |  "openai"  |  "anthropic"  |  "groq"  │
ACTIVE_LLM = "groq"
# └──────────────────────────────────────────────────┘

LLM_SPECS = {
    "groq": {
        "model":   "llama-3.3-70b-versatile",
        "key_env": os.getenv("GROQ_API_KEY"),
        "install": "pip install groq",
    },
    "gemini": {
        "model":   "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
        "install": "pip install google-generativeai",
    },
    "openai": {
        "model":   "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
        "install": "pip install openai",
    },
    "anthropic": {
        "model":   "claude-haiku-4-5-20251001",
        "key_env": "ANTHROPIC_API_KEY",
        "install": "pip install anthropic",
    },
}

MAX_TOKENS  = 1500
TEMPERATURE = 0.1    # lower = more faithful, less creative

# ISKCON contact — also used in app.py
ISKCON_NAME    = "ISKCON Pune NVCC"
ISKCON_PHONE   = "+91-XXXXXXXXXX"
ISKCON_EMAIL   = "nvcc@iskconpune.org"

logger = logging.getLogger("generator")


# =============================================================================
# RESPONSE DATACLASS
# =============================================================================

@dataclass
class GeneratedResponse:
    query:        str
    answer:       str
    sources:      list[RetrievalResult]
    llm_model:    str
    context_used: list[str] = field(default_factory=list)
    is_direct:    bool = False    # True when query was a direct verse lookup


# =============================================================================
# SYSTEM PROMPTS
# Two separate prompts: one for Q&A, one for direct verse display.
# =============================================================================

QA_SYSTEM_PROMPT = f"""You are a knowledgeable and respectful assistant specializing in the teachings of His Divine Grace A.C. Bhaktivedanta Swami Prabhupada.

Your role is to answer questions strictly and ONLY from the provided source passages.

ABSOLUTE RULES — violating these is not permitted:
1. Answer ONLY from the [SOURCE] passages provided. NEVER use any outside knowledge.
2. NEVER cite or mention any verse reference (e.g. BG 3.25) that does not appear in the provided [SOURCE] list. If you reference a verse, it MUST be one of the numbered sources given to you.
3. Cite every claim using the source reference in square brackets, e.g. [BG 2.47].
4. If the provided sources do not contain enough information, say exactly:
   "The provided passages do not directly address this question. Please try rephrasing or ask about a related topic."
   Then optionally suggest the user contact {ISKCON_NAME} (Phone: {ISKCON_PHONE} | Email: {ISKCON_EMAIL}) for personal guidance.
5. Do not speculate, infer, or add information not explicitly stated in the sources.
6. Maintain a respectful, devotional tone consistent with Vaishnava etiquette.
7. Do not repeat the same point multiple times."""


VERSE_DISPLAY_PROMPT = """You are a respectful assistant displaying a verse from Srila Prabhupada's books.

The user has requested a specific verse. Present it clearly in this EXACT order:
1. Reference and book name
2. Sanskrit transliteration (label: "Sanskrit Verse:")
3. Word-for-word meaning (label: "Word-for-Word:")
4. Translation (label: "Translation:")
5. Brief note from the Purport if it adds essential context (label: "From the Purport:" — 2-3 sentences max)

Use ONLY the content provided in the source. Do not add any information not present in the source."""


# =============================================================================
# DEDUPLICATION
# =============================================================================

def deduplicate_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Keep highest-ranked part per verse reference."""
    seen = {}
    for r in results:
        if r.reference not in seen or r.rerank_score > seen[r.reference].rerank_score:
            seen[r.reference] = r
    return sorted(seen.values(), key=lambda r: r.rerank_score, reverse=True)


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

def build_context_block(results: list[RetrievalResult], include_wfw: bool = False) -> str:
    """
    Format results as numbered source passages for the prompt.

    include_wfw: include word-for-word field (used for direct verse lookups).
    """
    blocks = []
    for i, r in enumerate(results, start=1):
        lines = [f"[SOURCE {i}] {r.reference} — {r.book}"]

        if r.verse_sanskrit.strip():
            lines.append(f"Sanskrit: {r.verse_sanskrit}")

        if include_wfw and r.word_for_word.strip():
            lines.append(f"Word-for-Word: {r.word_for_word}")

        lines.append(f"Translation: {r.translation}")

        if r.purport.strip():
            lines.append(f"Purport: {r.purport}")

        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


# =============================================================================
# PROMPT BUILDERS
# =============================================================================

def build_qa_prompt(query: str, context: str) -> str:
    return f"""The following passages are from Srila Prabhupada's books. Use ONLY these passages to answer the question. Do NOT reference any verse not listed below.

===== SOURCE PASSAGES =====
{context}
===== END OF PASSAGES =====

Question: {query}

Answer (cite ONLY the sources listed above using [REFERENCE] format):"""


def build_verse_prompt(context: str) -> str:
    return f"""Please display the following verse completely and clearly.

===== VERSE DATA =====
{context}
===== END =====

Present the verse in the structured format described in your instructions."""


# =============================================================================
# LLM PROVIDERS
# =============================================================================

def call_groq(system_prompt: str, user_prompt: str) -> str:
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set.\n"
            "Get a free key at: https://console.groq.com\n"
            "Then: export GROQ_API_KEY=gsk_..."
        )
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=LLM_SPECS["groq"]["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content.strip()


def call_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=LLM_SPECS["gemini"]["model"],
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
    )
    return model.generate_content(user_prompt).text.strip()


def call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set.")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=LLM_SPECS["openai"]["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content.strip()


def call_anthropic(system_prompt: str, user_prompt: str) -> str:
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=LLM_SPECS["anthropic"]["model"],
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=TEMPERATURE,
    )
    return response.content[0].text.strip()


def call_llm(system_prompt: str, user_prompt: str) -> str:
    if ACTIVE_LLM == "groq":
        return call_groq(system_prompt, user_prompt)
    elif ACTIVE_LLM == "gemini":
        return call_gemini(system_prompt, user_prompt)
    elif ACTIVE_LLM == "openai":
        return call_openai(system_prompt, user_prompt)
    elif ACTIVE_LLM == "anthropic":
        return call_anthropic(system_prompt, user_prompt)
    else:
        raise ValueError(f"Unknown LLM: '{ACTIVE_LLM}'")


# =============================================================================
# MAIN GENERATE FUNCTION
# =============================================================================

def generate(query: str, results: list[RetrievalResult]) -> GeneratedResponse:
    """
    Generate a grounded answer from retrieved results.
    Automatically uses verse-display mode for direct lookups.
    """
    if not results:
        return GeneratedResponse(
            query=query,
            answer=(
                "No relevant passages were found for this question.\n\n"
                f"For personal guidance, please contact {ISKCON_NAME}: "
                f"📞 {ISKCON_PHONE} | 📧 {ISKCON_EMAIL}"
            ),
            sources=[],
            llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
        )

    is_direct = any(r.direct_lookup for r in results)
    deduped   = deduplicate_results(results)

    if is_direct:
        # Verse display mode — include word-for-word, use verse prompt
        context     = build_context_block(deduped, include_wfw=True)
        user_prompt = build_verse_prompt(context)
        sys_prompt  = VERSE_DISPLAY_PROMPT
    else:
        # Q&A mode — exclude word-for-word from context, use strict QA prompt
        context     = build_context_block(deduped, include_wfw=False)
        user_prompt = build_qa_prompt(query, context)
        sys_prompt  = QA_SYSTEM_PROMPT

    logger.info(f"LLM: {ACTIVE_LLM} | mode: {'direct' if is_direct else 'qa'} | sources: {len(deduped)}")
    answer = call_llm(sys_prompt, user_prompt)

    return GeneratedResponse(
        query        = query,
        answer       = answer,
        sources      = deduped,
        llm_model    = LLM_SPECS[ACTIVE_LLM]["model"],
        context_used = [r.reference for r in deduped],
        is_direct    = is_direct,
    )


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from retrieve import retrieve

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?",
                        default="How should one perform devotional service?")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--books", nargs="+", choices=["bg","iso","noi","bs"])
    args = parser.parse_args()

    results  = retrieve(query=args.query, top_n=args.top_n, book_filter=args.books)
    response = generate(query=args.query, results=results)

    print(f"\n{'='*60}")
    print(f"Question: {response.query}")
    print(f"{'='*60}\n")
    print(response.answer)
    print(f"\n{'─'*60}")
    print(f"Sources : {', '.join(response.context_used)}")
    print(f"Model   : {response.llm_model}")
    print(f"Mode    : {'direct verse lookup' if response.is_direct else 'semantic Q&A'}")
    print(f"{'─'*60}\n")