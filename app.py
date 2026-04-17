# =============================================================================
# app.py
# Phase 6 — Streamlit frontend.
#
# Fixes vs previous version:
#   - Word-for-word shown in source cards (always, not toggle-gated)
#   - Direct lookup queries show a "Exact verse match" badge
#   - Source cards now display verse_sanskrit prominently
#   - Mode indicator in the UI (Semantic Q&A vs Direct Lookup)
# =============================================================================

import sys
import os
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import core
from backend.config import ACTIVE_LLM, LLM_SPECS, ISKCON_NAME, ISKCON_PHONE, ISKCON_EMAIL

# =============================================================================
# ISKCON CONTACT — update these values
# =============================================================================
ISKCON_WEBSITE = "https://iskconpune.com"   # ← update if needed

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title  = "Prabhupada GPT",
    page_icon   = "🪷",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# =============================================================================
# STYLING
# =============================================================================
st.markdown("""
<style>
    .stApp { background-color: #fdf8f0; }

    .main-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
        color: #7B3F00;
    }
    .main-header h1 { font-size: 2.4rem; font-weight: 700; margin-bottom: 0.2rem; }
    .main-header p  { font-size: 1rem; color: #8B6340; margin-top: 0; }

    .answer-box {
        background-color: #fffdf7;
        border-left: 4px solid #c8860a;
        border-radius: 6px;
        padding: 1.2rem 1.5rem;
        margin: 1rem 0;
        color: #2c1a0e;
        font-size: 1.05rem;
        line-height: 1.8;
        white-space: pre-wrap;
    }

    .source-card {
        background-color: #f5ede0;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        border: 1px solid #ddc9a8;
    }
    .source-ref   { font-weight: 700; color: #7B3F00; font-size: 1rem; }
    .source-book  { color: #8B6340; font-size: 0.85rem; margin-bottom: 0.5rem; }
    .field-label  {
        font-size: 0.78rem; font-weight: 600; color: #7B3F00;
        text-transform: uppercase; letter-spacing: 0.05em;
        margin-top: 0.6rem; margin-bottom: 0.1rem;
    }
    .field-sanskrit    { font-style: italic; color: #4a2e0e; font-size: 0.93rem; line-height: 1.6; }
    .field-wfw         { color: #3d2b10; font-size: 0.88rem; line-height: 1.6; }
    .field-translation { color: #2c1a0e; font-size: 0.95rem; line-height: 1.65; }

    .badge-direct {
        display: inline-block; background: #2e7d32; color: white;
        border-radius: 10px; padding: 1px 9px; font-size: 0.75rem;
        margin-left: 8px; vertical-align: middle;
    }
    .badge-semantic {
        display: inline-block; background: #7B3F00; color: white;
        border-radius: 10px; padding: 1px 9px; font-size: 0.75rem;
        margin-left: 8px; vertical-align: middle;
    }
    .score-badge {
        display: inline-block; background: #c8860a; color: white;
        border-radius: 12px; padding: 1px 8px; font-size: 0.73rem; margin-left: 4px;
    }

    .contact-box {
        background-color: #eaf4ea; border: 1px solid #a8d5a2;
        border-radius: 8px; padding: 0.9rem 1.2rem;
        margin-top: 1.2rem; font-size: 0.93rem; color: #1a3d1a;
    }
    .contact-box strong { color: #1e5c1e; }
    .contact-box a { color: #1e5c1e; }

    section[data-testid="stSidebar"] { background-color: #f5ede0; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# MODEL LOADING (cached)
# =============================================================================

@st.cache_resource(show_spinner=False)
def load_models():
    core.startup()
    return True


@st.cache_data(show_spinner=False, ttl=3600)
def cached_retrieve(query: str, top_n: int, book_filter_tuple: tuple):
    book_filter = list(book_filter_tuple) if book_filter_tuple else None
    return core.retrieve(query=query, top_n=top_n, book_filter=book_filter)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🪷 Prabhupada GPT")
        st.markdown("*Ask questions from Srila Prabhupada's books*")
        st.divider()

        st.markdown("### 📚 Search Settings")

        book_options = {
            "Bhagavad Gita As It Is": "bg",
            "Sri Isopanishad":        "iso",
            "Nectar of Instruction":  "noi",
            "Brahma Samhita":         "bs",
        }
        selected_books = st.multiselect(
            "Search in books",
            options  = list(book_options.keys()),
            default  = list(book_options.keys()),
        )
        book_filter = [book_options[b] for b in selected_books]

        top_n = st.slider("Number of sources", 1, 10, 5)

        show_purport = st.toggle("Show full purport", value=False)
        show_scores  = st.toggle("Show relevance scores", value=False)

        st.divider()
        st.markdown(
            f"**Model:** `{LLM_SPECS[ACTIVE_LLM]['model']}`\n\n"
            "💡 **Tip:** To look up a specific verse, include the reference "
            "in your query, e.g. *give me BG 3.9* or *show NOI 2*."
        )

        st.divider()
        st.markdown("### 🙏 Sample Questions")
        samples = [
            "What is the nature of the eternal soul?",
            "How should one perform devotional service?",
            "Give me BG 2.47 with word-for-word",
            "Show NOI 1",
            "What is the purpose of human life?",
            "How to control the mind?",
            "What is pure love of God?",
            "Who is Krishna?",
        ]
        for q in samples:
            if st.button(q, use_container_width=True, key=f"s_{q[:15]}"):
                st.session_state["query_input"] = q
                st.rerun()

    return book_filter, top_n, show_purport, show_scores


# =============================================================================
# SOURCE CARD
# =============================================================================

def render_source_card(result, show_purport: bool, show_scores: bool):
    score_html = ""
    if show_scores and not result.direct_lookup:
        score_html = (
            f'<span class="score-badge">v {result.vector_score:.2f}</span>'
            f'<span class="score-badge">r {result.rerank_score:.2f}</span>'
        )
    direct_badge = '<span class="badge-direct">✓ Exact match</span>' if result.direct_lookup else ""

    part_label = f" · Part {result.part}/{result.total_parts}" if result.total_parts > 1 else ""

    # Build card HTML
    card = f"""
    <div class="source-card">
        <div class="source-ref">{result.reference}{part_label} {direct_badge} {score_html}</div>
        <div class="source-book">{result.book}</div>
    """

    if result.verse_sanskrit.strip():
        card += f"""
        <div class="field-label">Sanskrit Verse</div>
        <div class="field-sanskrit">{result.verse_sanskrit}</div>
        """

    if result.word_for_word.strip():
        card += f"""
        <div class="field-label">Word-for-Word</div>
        <div class="field-wfw">{result.word_for_word}</div>
        """

    card += f"""
        <div class="field-label">Translation</div>
        <div class="field-translation">{result.translation}</div>
    </div>
    """

    st.markdown(card, unsafe_allow_html=True)

    if show_purport and result.purport:
        with st.expander("📜 Full Purport"):
            st.markdown(result.purport)


# =============================================================================
# CONTACT BOX
# =============================================================================

def render_contact_box():
    st.markdown(f"""
    <div class="contact-box">
        <strong>🏛️ {ISKCON_NAME}</strong><br>
        Want to go deeper? Connect with devotees for personal guidance, classes, and spiritual programs.<br><br>
        📞 <strong>{ISKCON_PHONE}</strong> &nbsp;|&nbsp;
        📧 <a href="mailto:{ISKCON_EMAIL}">{ISKCON_EMAIL}</a> &nbsp;|&nbsp;
        🌐 <a href="{ISKCON_WEBSITE}" target="_blank">{ISKCON_WEBSITE}</a>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    with st.spinner("Loading models..."):
        load_models()

    book_filter, top_n, show_purport, show_scores = render_sidebar()

    st.markdown("""
    <div class="main-header">
        <h1>🪷 Prabhupada GPT</h1>
        <p>Ask questions from the teachings of His Divine Grace A.C. Bhaktivedanta Swami Prabhupada</p>
    </div>
    """, unsafe_allow_html=True)

    if "history"     not in st.session_state: st.session_state["history"]     = []
    if "query_input" not in st.session_state: st.session_state["query_input"] = ""

    query = st.text_input(
        label            = "Your question",
        value            = st.session_state["query_input"],
        placeholder      = "e.g. What is the nature of the soul?  |  Give me BG 2.47",
        label_visibility = "collapsed",
    )

    col1, col2, _ = st.columns([1, 1, 5])
    with col1:
        ask_clicked = st.button("🔍 Ask", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state["history"]     = []
            st.session_state["query_input"] = ""
            st.rerun()

    if ask_clicked and query.strip():
        st.session_state["query_input"] = ""

        with st.spinner("Searching scriptures..."):
            try:
                results  = cached_retrieve(
                    query            = query.strip(),
                    top_n            = top_n,
                    book_filter_tuple = tuple(book_filter) if book_filter else (),
                )
                response = core.generate(task="ask", query=query.strip(), results=results, top_n=top_n)
                st.session_state["history"].insert(0, (query.strip(), response))
            except Exception as e:
                st.error(f"Error: {e}")
                return

    # Display history
    for query_text, response in st.session_state["history"]:
        st.markdown("---")

        # Mode badge next to question
        mode_badge = (
            '<span class="badge-direct">Direct Lookup</span>'
            if response.is_direct
            else '<span class="badge-semantic">Semantic Search</span>'
        )
        st.markdown(f"**🙋 {query_text}** {mode_badge}", unsafe_allow_html=True)

        # Answer
        st.markdown(
            f'<div class="answer-box">{response.answer}</div>',
            unsafe_allow_html=True,
        )

        # Sources
        if response.sources:
            label = "📚 Sources: " + ", ".join(response.context_used)
            with st.expander(label, expanded=response.is_direct):
                for result in response.sources:
                    render_source_card(result, show_purport, show_scores)

        render_contact_box()


if __name__ == "__main__":
    main()