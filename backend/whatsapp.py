# =============================================================================
# backend/whatsapp.py
# WhatsApp Meta Cloud API integration.
# =============================================================================

import re
import logging
import httpx

from backend.config import (
    WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_API_VERSION
)

logger = logging.getLogger("whatsapp")

WHATSAPP_API_URL = (
    f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"
    f"/{WHATSAPP_PHONE_ID}/messages"
)

WA_MAX_CHARS = 4096


# =============================================================================
# MARKDOWN → WHATSAPP FORMAT CONVERTER
#
# WhatsApp supports:   *bold*   _italic_   ~strikethrough~   ```code```
# WhatsApp does NOT:  **bold**  ##headings  [citations]  ---dividers
# =============================================================================

def _md_to_wa(text: str) -> str:
    """
    Convert LLM markdown output to WhatsApp-compatible plain text with
    WhatsApp's own formatting markers.
    """
    # 1. Strip [SOURCE N] / [SOURCE 1] tags the LLM leaks into answers
    text = re.sub(r'\[SOURCE\s*\d+\]', '', text)

    # 2. Strip markdown headings (## Title → *Title*)
    text = re.sub(r'^#{1,4}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)

    # 3. Convert **bold** → *bold* (WhatsApp bold)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # 4. Convert __italic__ → _italic_
    text = re.sub(r'__(.+?)__', r'_\1_', text)

    # 5. Convert verse citations [BG 2.47] → (BG 2.47)
    text = re.sub(r'\[([A-Z]{1,4}\s[\d.]+)\]', r'(\1)', text)

    # 6. Convert markdown horizontal rules to WhatsApp-friendly divider
    text = re.sub(r'^[-*_]{3,}$', '─────────────────', text, flags=re.MULTILINE)

    # 7. Strip markdown links [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 8. Clean up excessive blank lines (max 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# =============================================================================
# GREETING DETECTION
# =============================================================================

_GREETINGS = {
    "hi", "hii", "hiii", "hello", "hey", "helo", "heyy",
    "namaste", "hari om", "hare krishna", "hare krsna",
    "good morning", "good afternoon", "good evening", "good night",
    "sup", "wassup", "yo", "greetings", "howdy",
}

def is_greeting(text: str) -> bool:
    """
    Return True if the message is just a greeting with no real question.
    Matches whole-message greetings only — 'hello, what is karma?' returns False.
    """
    cleaned = text.strip().lower().rstrip("!.,?")
    return cleaned in _GREETINGS


GREETING_REPLY = (
    "🙏 *Hare Krishna!*\n\n"
    "Ask me anything from Srila Prabhupada's books!\n\n"
    "Try:\n"
    "• _What is the purpose of life?_\n"
    "• _get BG 2.47_\n"
    "• _explain maya_\n"
    "• _quiz 5 questions from NOI_"
)


# =============================================================================
# TASK DETECTION FROM WHATSAPP MESSAGE
# =============================================================================

def detect_task_from_message(text: str) -> tuple[str, str]:
    """
    Detect which task the user wants from their WhatsApp message.
    Returns (task, cleaned_query).

    Triggers:
      "explain …"           → explain
      "quiz …"              → quiz
      "summary/summarise …" → summarise
      "get/ref BG 2.47"     → reference
      anything else         → ask  (smart auto-detect in core.py)
    """
    text_lower = text.strip().lower()

    if text_lower.startswith(("explain ", "explain:")):
        query = text[len("explain"):].strip().lstrip(":").strip()
        return "explain", query

    if text_lower.startswith(("quiz ", "quiz:")):
        query = text[len("quiz"):].strip().lstrip(":").strip()
        return "quiz", query

    for prefix in ("summary", "summarise", "summarize"):
        if text_lower.startswith(prefix):
            query = text[len(prefix):].strip().lstrip(":").strip()
            return "summarise", query

    for prefix in ("get", "show", "reference", "ref"):
        if text_lower.startswith(prefix + " ") or text_lower.startswith(prefix + ":"):
            query = text[len(prefix):].strip().lstrip(":").strip()
            return "reference", query

    return "ask", text.strip()


# =============================================================================
# RESPONSE FORMATTER FOR WHATSAPP
# =============================================================================

def format_for_whatsapp(task: str, answer: str, sources: list, context_used: list[str]) -> str:
    """
    Format the generated response for WhatsApp's rendering constraints.

    Pipeline:
      1. Convert LLM markdown to WhatsApp markers
      2. Append sources footer
      3. For reference task: append verse details
      4. Truncate at 4096 chars
    """
    lines = []

    # Convert markdown → WhatsApp format
    wa_answer = _md_to_wa(answer)
    lines.append(wa_answer)

    # Sources footer
    if context_used:
        lines.append("")
        lines.append("─────────────────")
        lines.append(f"📚 *Sources:* {', '.join(context_used)}")

    # Reference task: append full verse block (max 2 verses to stay under 4096)
    if task == "reference" and sources:
        for src in sources[:2]:
            lines.append("")
            lines.append(f"*{src.reference}* — _{src.book}_")
            if src.verse_sanskrit:
                lines.append(f"🕉️ _{src.verse_sanskrit[:200]}_")
            if src.word_for_word:
                lines.append(f"📖 {src.word_for_word[:250]}")
            if src.translation:
                lines.append(f"📝 {src.translation}")

    # Quiz task: strip JSON from raw answer if quiz_data wasn't parsed
    # (the LLM answer for quiz is JSON — not readable on WhatsApp)
    if task == "quiz":
        lines = ["📝 *Quiz generated!* Open the web app to take the quiz interactively.",
                 "",
                 "─────────────────",
                 f"📚 *Sources:* {', '.join(context_used)}"]

    full_text = "\n".join(lines)

    # Truncate at WhatsApp limit
    if len(full_text) > WA_MAX_CHARS:
        full_text = (full_text[:WA_MAX_CHARS - 120]
                     + "\n\n_(Message truncated — visit our website for the full response)_")

    return full_text


# =============================================================================
# SEND MESSAGE VIA WHATSAPP API
# =============================================================================

async def send_whatsapp_message(to: str, text: str):
    """
    Send a text message to a WhatsApp number via Meta Cloud API.

    Args:
        to:   Phone number with country code, no + e.g. "919876543210"
        text: Message body (plain text with WhatsApp formatting)
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_ID:
        logger.error("WhatsApp credentials not configured.")
        return

    payload = {
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "text",
        "text":              {"body": text},
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, json=payload, headers=headers, timeout=15)

    if resp.status_code == 200:
        logger.info(f"Sent to {to} ({len(text)} chars)")
    else:
        logger.error(f"Send failed {resp.status_code}: {resp.text}")


# =============================================================================
# WELCOME MESSAGE
# =============================================================================

async def send_welcome_message(to: str):
    """
    Send a one-time welcome message when a user first contacts the bot.
    Call this from webhook.py when you detect a new sender.
    """
    welcome = (
        "🪷 *Hare Krishna! Welcome to Prabhupada GPT* 🪷\n\n"
        "I can answer questions from Srila Prabhupada's books:\n"
        "📖 *Bhagavad Gita As It Is* (BG)\n"
        "📖 *Sri Isopanishad* (ISO)\n"
        "📖 *Nectar of Instruction* (NOI)\n"
        "📖 *Brahma Samhita* (BS)\n\n"
        "─────────────────\n"
        "*How to ask:*\n"
        "Just type any question naturally:\n"
        "• _What is the purpose of life?_\n"
        "• _get BG 2.47_ → fetch exact verse\n"
        "• _explain karma yoga_\n"
        "• _quiz 5 questions from NOI_\n"
        "• _summary of devotional service_\n\n"
        "─────────────────\n"
        "🏛️ *ISKCON Pune NVCC* — for personal guidance\n"
        "📞 +91-XXXXXXXXXX | 🌐 iskconpune.com"
    )
    await send_whatsapp_message(to=to, text=welcome)


# =============================================================================
# PARSE INCOMING WEBHOOK PAYLOAD
# =============================================================================

def parse_incoming_message(payload: dict) -> tuple[str, str] | None:
    """
    Extract (sender_phone, message_text) from a Meta webhook payload.
    Returns None if not a valid user text message.
    """
    try:
        entry   = payload["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]

        if "messages" not in value:
            return None

        message = value["messages"][0]

        if message["type"] != "text":
            logger.info(f"Ignoring non-text type: {message['type']}")
            return None

        sender = message["from"]
        text   = message["text"]["body"]
        return sender, text

    except (KeyError, IndexError) as e:
        logger.warning(f"Could not parse payload: {e}")
        return None