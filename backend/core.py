# from __future__ import annotations

# from dotenv import load_dotenv
# # load env variables
# load_dotenv()

# import os
# import re
# import json
# import logging
# import sys
# from dataclasses import dataclass, field
# from pathlib import Path

# import chromadb

# sys.path.insert(0, str(Path(__file__).parent.parent))

# from backend.config import (
#     CHROMA_DIR, ACTIVE_PROVIDER, ACTIVE_LLM, LLM_SPECS,
#     MAX_TOKENS, TEMPERATURE, RETRIEVAL_K, RERANK_TOP_N,
#     RERANKER_MODEL, BGE_QUERY_PREFIX,
# )

# logger = logging.getLogger("core")

# COLLECTION_NAME  = "prabhupada_rag"
# RERANK_THRESHOLD = -2.0   # drop candidates below this cross-encoder score

# BOOK_NAMES = {
#     "bg":  "Bhagavad Gita As It Is",
#     "iso": "Sri Isopanishad",
#     "noi": "Nectar of Instruction",
#     "bs":  "Brahma Samhita",
# }


# # =============================================================================
# # STARTUP
# # =============================================================================

# _chroma_collection = None
# _embedding_model   = None
# _reranker          = None


# def startup():
#     global _chroma_collection, _embedding_model, _reranker
#     logger.info("=== Backend startup ===")

#     client = chromadb.PersistentClient(path=CHROMA_DIR)
#     _chroma_collection = client.get_collection(name=COLLECTION_NAME)
#     logger.info(f"ChromaDB: {_chroma_collection.count()} vectors")

#     if ACTIVE_PROVIDER == "baai":
#         from sentence_transformers import SentenceTransformer
#         _embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
#         logger.info("Embedding: BAAI/bge-large-en-v1.5")

#     try:
#         from sentence_transformers import CrossEncoder
#         _reranker = CrossEncoder(RERANKER_MODEL)
#         logger.info(f"Reranker: {RERANKER_MODEL}")
#     except Exception as e:
#         logger.warning(f"Reranker unavailable: {e}")

#     logger.info("=== Startup complete ===")


# def get_db_count() -> int:
#     return _chroma_collection.count() if _chroma_collection else 0


# # =============================================================================
# # DATA STRUCTURES
# # =============================================================================

# @dataclass
# class RetrievalResult:
#     chunk_id:       str
#     reference:      str
#     book:           str
#     book_code:      str
#     translation:    str
#     purport:        str
#     verse_sanskrit: str
#     word_for_word:  str
#     part:           int
#     total_parts:    int
#     vector_score:   float
#     rerank_score:   float
#     chunk_text:     str
#     direct_lookup:  bool = False


# @dataclass
# class GeneratedResponse:
#     task:         str
#     query:        str
#     answer:       str
#     sources:      list[RetrievalResult]
#     llm_model:    str
#     context_used: list[str] = field(default_factory=list)
#     is_direct:    bool      = False
#     mode:         str       = ""
#     quiz_data:    list[dict] | None = None


# # =============================================================================
# # LLM CALL  (defined early — used by query expansion too)
# # =============================================================================

# def call_llm(system_prompt: str, user_prompt: str,
#              max_tokens: int = None, temperature: float = None) -> str:
#     mt   = max_tokens  or MAX_TOKENS
#     temp = temperature or TEMPERATURE
#     model = LLM_SPECS[ACTIVE_LLM]["model"]

#     if ACTIVE_LLM == "groq":
#         from groq import Groq
#         client = Groq(api_key=os.environ["GROQ_API_KEY"])
#         resp = client.chat.completions.create(
#             model=model,
#             messages=[{"role":"system","content":system_prompt},
#                       {"role":"user","content":user_prompt}],
#             max_tokens=mt, temperature=temp,
#         )
#         return resp.choices[0].message.content.strip()

#     if ACTIVE_LLM == "openai":
#         from openai import OpenAI
#         client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
#         resp = client.chat.completions.create(
#             model=model,
#             messages=[{"role":"system","content":system_prompt},
#                       {"role":"user","content":user_prompt}],
#             max_tokens=mt, temperature=temp,
#         )
#         return resp.choices[0].message.content.strip()

#     if ACTIVE_LLM == "gemini":
#         import google.generativeai as genai
#         genai.configure(api_key=os.environ["GEMINI_API_KEY"])
#         m = genai.GenerativeModel(
#             model_name=model,
#             system_instruction=system_prompt,
#             generation_config=genai.GenerationConfig(
#                 max_output_tokens=mt, temperature=temp),
#         )
#         return m.generate_content(user_prompt).text.strip()

#     if ACTIVE_LLM == "anthropic":
#         import anthropic
#         client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
#         resp = client.messages.create(
#             model=model, max_tokens=mt, system=system_prompt,
#             messages=[{"role":"user","content":user_prompt}],
#             temperature=temp,
#         )
#         return resp.content[0].text.strip()

#     raise ValueError(f"Unknown LLM: {ACTIVE_LLM}")


# # =============================================================================
# # EMBEDDING
# # =============================================================================

# def embed_texts(texts: list[str]) -> list[list[float]]:
#     if ACTIVE_PROVIDER == "baai":
#         vecs = _embedding_model.encode(
#             texts, normalize_embeddings=True, show_progress_bar=False)
#         return vecs.tolist()

#     if ACTIVE_PROVIDER == "gemini":
#         import google.generativeai as genai
#         genai.configure(api_key=os.environ["GEMINI_API_KEY"])
#         res  = genai.embed_content(model="models/text-embedding-004",
#                                    content=texts, task_type="retrieval_document")
#         vecs = res["embedding"]
#         return [vecs] if isinstance(vecs[0], float) else list(vecs)

#     if ACTIVE_PROVIDER == "openai":
#         from openai import OpenAI
#         client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
#         resp = client.embeddings.create(input=texts, model="text-embedding-3-small")
#         return [item.embedding for item in resp.data]

#     raise ValueError(f"Unknown provider: {ACTIVE_PROVIDER}")


# def embed_query(query: str) -> list[float]:
#     text = (BGE_QUERY_PREFIX + query) if ACTIVE_PROVIDER == "baai" else query
#     return embed_texts([text])[0]


# # =============================================================================
# # QUERY EXPANSION
# # =============================================================================

# def expand_query(query: str) -> list[str]:
#     """
#     Generates 2 alternative phrasings of the query including Sanskrit synonyms.
#     Falls back silently to [query] on any failure — never blocks retrieval.
#     """
#     if len(query.split()) <= 3:
#         return [query]

#     try:
#         prompt = (
#             "Rewrite this question about Vedic/Krishna consciousness into 2 alternative "
#             "phrasings. Include relevant Sanskrit terms (atma=soul, bhakti=devotion, "
#             "karma=action, jiva=living entity, maya=illusion, dharma=duty, etc.) "
#             "where natural. Return ONLY a JSON array of exactly 2 strings.\n\n"
#             f"Question: {query}\n\nOutput: [\"variant1\", \"variant2\"]"
#         )
#         raw      = call_llm("You are a helpful assistant.", prompt,
#                             max_tokens=120, temperature=0.3)
#         variants = json.loads(raw.strip())
#         if isinstance(variants, list) and len(variants) >= 2:
#             return [query] + [str(v) for v in variants[:2]]
#     except Exception as e:
#         logger.debug(f"Query expansion skipped: {e}")

#     return [query]


# # =============================================================================
# # DIRECT REFERENCE DETECTION
# # =============================================================================

# REFERENCE_PATTERNS = [
#     (r'\bbg\.?\s*(\d+)\.(\d+(?:-\d+)?)\b', "bg"),
#     (r'\bnoi\.?\s*(\d+)\b',                 "noi"),
#     (r'\biso\.?\s*(\d+)\b',                 "iso"),
#     (r'\bbs\.?\s*5\.(\d+)\b',              "bs"),
# ]


# def detect_reference(query: str) -> list[dict] | None:
#     found = []
#     for pattern, book_code in REFERENCE_PATTERNS:
#         for match in re.finditer(pattern, query, re.IGNORECASE):
#             if book_code == "bg":
#                 found.append({"book_code": book_code,
#                                "d1": int(match.group(1)), "d2": match.group(2)})
#             elif book_code == "bs":
#                 found.append({"book_code": book_code,
#                                "d1": int(match.group(1)), "d2": None})
#             else:
#                 found.append({"book_code": book_code,
#                                "d1": int(match.group(1)), "d2": None})
#     return found or None


# def direct_lookup(refs: list[dict]) -> list[RetrievalResult]:
#     results = []
#     for ref in refs:
#         d2  = ref.get("d2")
#         cid = (f"{ref['book_code']}_{ref['d1']}_{d2}"
#                if d2 else f"{ref['book_code']}_{ref['d1']}")
#         try:
#             resp = _chroma_collection.get(ids=[cid], include=["metadatas","documents"])
#         except Exception:
#             continue
#         if not resp["ids"]:
#             continue
#         meta = resp["metadatas"][0]
#         results.append(RetrievalResult(
#             chunk_id=cid, reference=meta["reference"],
#             book=meta["book"], book_code=meta["book_code"],
#             translation=meta["translation"], purport=meta["purport"],
#             verse_sanskrit=meta.get("verse_sanskrit",""),
#             word_for_word=meta.get("word_for_word",""),
#             part=meta.get("part",1), total_parts=meta.get("total_parts",1),
#             vector_score=1.0, rerank_score=10.0,
#             chunk_text=resp["documents"][0], direct_lookup=True,
#         ))
#     return results


# # =============================================================================
# # VECTOR SEARCH + RERANKING
# # =============================================================================

# def vector_search(query_vector: list[float], k: int,
#                   book_filter: list[str]) -> list[dict]:
#     where = None
#     if book_filter and len(book_filter) == 1:
#         where = {"book_code": {"$eq": book_filter[0]}}
#     elif book_filter and len(book_filter) > 1:
#         where = {"book_code": {"$in": book_filter}}

#     kwargs = {
#         "query_embeddings": [query_vector],
#         "n_results": min(k, _chroma_collection.count()),
#         "include":   ["metadatas","documents","distances"],
#     }
#     if where:
#         kwargs["where"] = where

#     raw = _chroma_collection.query(**kwargs)
#     return [
#         {"metadata": m, "chunk_text": d, "vector_score": round(1 - dist, 4)}
#         for m, d, dist in zip(raw["metadatas"][0],
#                                raw["documents"][0],
#                                raw["distances"][0])
#     ]


# def rerank_candidates(query: str, candidates: list[dict],
#                       top_n: int) -> list[dict]:
#     if _reranker is None:
#         for c in candidates:
#             c["rerank_score"] = c["vector_score"]
#         return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_n]

#     pairs  = [(query, c["chunk_text"]) for c in candidates]
#     scores = _reranker.predict(pairs)
#     for c, s in zip(candidates, scores):
#         c["rerank_score"] = round(float(s), 4)

#     # Threshold filter
#     filtered = [c for c in candidates if c["rerank_score"] >= RERANK_THRESHOLD]
#     if not filtered:
#         filtered = [max(candidates, key=lambda x: x["rerank_score"])]

#     return sorted(filtered, key=lambda x: x["rerank_score"], reverse=True)[:top_n]


# def candidates_to_results(candidates: list[dict]) -> list[RetrievalResult]:
#     return [
#         RetrievalResult(
#             chunk_id=m.get("chunk_id",""), reference=m["reference"],
#             book=m["book"], book_code=m["book_code"],
#             translation=m["translation"], purport=m["purport"],
#             verse_sanskrit=m.get("verse_sanskrit",""),
#             word_for_word=m.get("word_for_word",""),
#             part=m.get("part",1), total_parts=m.get("total_parts",1),
#             vector_score=c["vector_score"], rerank_score=c["rerank_score"],
#             chunk_text=c["chunk_text"], direct_lookup=False,
#         )
#         for c in candidates
#         for m in [c["metadata"]]
#     ]


# # =============================================================================
# # QUIZ AUTO-PARSE
# # =============================================================================

# def parse_quiz_intent(query: str) -> tuple[int, str | None, int | None]:
#     """
#     Returns (num_questions, book_code, chapter_number).
    
#     Examples:
#       "Make 10 MCQs from Chapter 2 of Bhagavad Gita" → (10, "bg", 2)
#       "Quiz on BG Chapter 2"                          → (5,  "bg", 2)
#       "5 questions from NOI"                          → (5,  "noi", None)
#       "Make 5 MCQs from Nectar of Instruction"        → (5,  "noi", None)
#     """
#     q = query.lower()

#     # Extract chapter number first (before extracting general numbers)
#     chapter = None
#     chapter_match = re.search(r'chapter\s+(\d+)', q)
#     if chapter_match:
#         chapter = int(chapter_match.group(1))

#     # Extract question count — look for number NOT preceded by "chapter"
#     # Replace "chapter N" with placeholder so it doesn't interfere
#     q_no_chapter = re.sub(r'chapter\s+\d+', 'CHAPTER', q)
#     num = 5
#     num_match = re.search(r'\b(\d+)\b', q_no_chapter)
#     if num_match:
#         n = int(num_match.group(1))
#         if 1 <= n <= 30:
#             num = n

#     # Extract book
#     book_map = {
#         "noi": "noi", "nectar of instruction": "noi", "nectar": "noi",
#         "bg":  "bg",  "bhagavad gita": "bg", "gita": "bg", "bhagavad-gita": "bg",
#         "iso": "iso", "isopanishad": "iso", "iso panishad": "iso",
#         "bs":  "bs",  "brahma samhita": "bs", "brahmasamhita": "bs",
#     }
#     book_code = None
#     for keyword, code in book_map.items():
#         if keyword in q:
#             book_code = code
#             break

#     return num, book_code, chapter

# # =============================================================================
# # RETRIEVE — main public function
# # =============================================================================

# def retrieve(
#     query:          str,
#     top_n:          int        = RERANK_TOP_N,
#     k:              int        = RETRIEVAL_K,
#     book_filter:    list[str]  = None,
#     force_semantic: bool       = False,
#     use_expansion:  bool       = True,
# ) -> list[RetrievalResult]:
#     book_filter = book_filter or []

#     # Direct reference lookup
#     if not force_semantic:
#         refs = detect_reference(query)
#         if refs:
#             direct = direct_lookup(refs)
#             if direct:
#                 return direct

#     # Query expansion
#     queries = expand_query(query) if use_expansion else [query]

#     # Search all variants, deduplicate by reference+part
#     all_candidates: dict[str, dict] = {}
#     for q in queries:
#         qv = embed_query(q)
#         for c in vector_search(qv, k=k, book_filter=book_filter):
#             key = (c["metadata"].get("reference","")
#                    + str(c["metadata"].get("part", 1)))
#             if key not in all_candidates or \
#                c["vector_score"] > all_candidates[key]["vector_score"]:
#                 all_candidates[key] = c

#     if not all_candidates:
#         return []

#     reranked = rerank_candidates(query, list(all_candidates.values()), top_n=top_n)
#     return candidates_to_results(reranked)


# def retrieve_by_scope(book_code: str, top_n: int = 20) -> list[RetrievalResult]:
#     import random
#     resp = _chroma_collection.get(
#         where={"book_code": {"$eq": book_code}},
#         include=["metadatas","documents"],
#     )
#     results = [
#         RetrievalResult(
#             chunk_id=meta.get("chunk_id",""), reference=meta["reference"],
#             book=meta["book"], book_code=meta["book_code"],
#             translation=meta["translation"], purport=meta["purport"],
#             verse_sanskrit=meta.get("verse_sanskrit",""),
#             word_for_word=meta.get("word_for_word",""),
#             part=meta.get("part",1), total_parts=meta.get("total_parts",1),
#             vector_score=1.0, rerank_score=1.0, chunk_text=doc,
#             direct_lookup=False,
#         )
#         for meta, doc in zip(resp["metadatas"], resp["documents"])
#     ]
#     # Shuffle so whole-book quiz/summarise samples evenly across chapters,
#     # not just whatever chapter happens to be first in DB insertion order.
#     random.shuffle(results)
#     return results[:top_n]

# def retrieve_by_chapter(book_code: str, chapter: int, top_n: int = 20) -> list[RetrievalResult]:
#     """
#     Retrieve all verses from a specific chapter of a book.
#     Used for chapter-specific quiz/summarise requests.
#     ChromaDB 'division_1' stores chapter number for BG.
#     Always fetches ALL verses in the chapter (ignoring top_n cap here)
#     so the LLM has complete material to generate questions from.
#     """
#     resp = _chroma_collection.get(
#         where={
#             "$and": [
#                 {"book_code":  {"$eq": book_code}},
#                 {"division_1": {"$eq": chapter}},
#             ]
#         },
#         include=["metadatas", "documents"],
#     )
#     results = [
#         RetrievalResult(
#             chunk_id=meta.get("chunk_id", ""), reference=meta["reference"],
#             book=meta["book"], book_code=meta["book_code"],
#             translation=meta["translation"], purport=meta["purport"],
#             verse_sanskrit=meta.get("verse_sanskrit", ""),
#             word_for_word=meta.get("word_for_word", ""),
#             part=meta.get("part", 1), total_parts=meta.get("total_parts", 1),
#             vector_score=1.0, rerank_score=1.0, chunk_text=doc,
#             direct_lookup=False,
#         )
#         for meta, doc in zip(resp["metadatas"], resp["documents"])
#     ]
#     logger.info(f"retrieve_by_chapter({book_code}, ch={chapter}): {len(results)} verses fetched")
#     # Return all chapter verses up to a hard cap of 60 so context isn't too large
#     return results[:60]


# # =============================================================================
# # DEDUPLICATION + CONTEXT
# # =============================================================================

# def deduplicate(results: list[RetrievalResult]) -> list[RetrievalResult]:
#     seen = {}
#     for r in results:
#         if r.reference not in seen or r.rerank_score > seen[r.reference].rerank_score:
#             seen[r.reference] = r
#     return sorted(seen.values(), key=lambda r: r.rerank_score, reverse=True)


# def build_context(results: list[RetrievalResult],
#                   include_wfw: bool = False) -> str:
#     blocks = []
#     for i, r in enumerate(results, 1):
#         lines = [f"[SOURCE {i}] {r.reference} — {r.book}"]
#         if r.verse_sanskrit.strip():
#             lines.append(f"Sanskrit: {r.verse_sanskrit}")
#         if include_wfw and r.word_for_word.strip():
#             lines.append(f"Word-for-Word: {r.word_for_word}")
#         lines.append(f"Translation: {r.translation}")
#         if r.purport.strip():
#             lines.append(f"Purport: {r.purport}")
#         blocks.append("\n".join(lines))
#     return "\n\n---\n\n".join(blocks)


# def build_conversation_context(history: list[dict]) -> str:
#     if not history:
#         return ""
#     recent = history[-4:]
#     lines  = ["Previous conversation:"]
#     for msg in recent:
#         prefix = "User" if msg["role"] == "user" else "Assistant"
#         lines.append(f"{prefix}: {msg['content'][:300]}")
#     return "\n".join(lines)


# # =============================================================================
# # SYSTEM PROMPTS
# # =============================================================================

# def get_system_prompt(task: str) -> str:
#     prompts = {

#         "ask": """You are a knowledgeable and respectful assistant for the teachings of His Divine Grace A.C. Bhaktivedanta Swami Prabhupada.

# ABSOLUTE RULES:
# 1. Answer ONLY from the [SOURCE] passages. NEVER use outside knowledge.
# 2. NEVER cite a verse not present in the [SOURCE] list.
# 3. Cite every claim with [REFERENCE], e.g. [BG 2.47].
# 4. Use **bold** for key spiritual terms.
# 5. If sources are insufficient: "The provided passages do not directly address this question."
# 6. Do not speculate. Maintain a respectful, devotional tone. Do not repeat points.""",

#         "reference": """You are displaying a verse from Srila Prabhupada's books.

# Present in this EXACT order using markdown:
# ## [Reference] — [Book Name]

# **Sanskrit Verse:**
# [exact transliteration]

# **Word-for-Word:**
# [exact synonyms]

# **Translation:**
# [exact translation]

# **From the Purport:**
# [2-3 sentences of the most essential teaching]

# Use ONLY the provided content. Do not modify the verse text.""",

#         "explain": """You are a Vaishnava teacher explaining Srila Prabhupada's teachings.

# Structure:
# 1. **Relevant Verse(s):** Quote the translation(s) verbatim with [REFERENCE].
# 2. **Explanation:** Clear, accessible language for a modern audience.
# 3. **Key Insight:** One-sentence synthesis of the core teaching.

# Rules: ONLY the provided sources. Cite every point. Bold key terms on first use.
# Tone: warm, clear, devotional — like a senior devotee explaining to a new student.""",

#         "quiz": """You generate multiple-choice quizzes from Srila Prabhupada's teachings.

# Each question must be directly based on the provided passages.
# Return ONLY valid JSON, no other text:
# {
#   "questions": [
#     {
#       "question": "...",
#       "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
#       "answer": "A. ...",
#       "reference": "BG 2.47",
#       "explanation": "One sentence why this is correct."
#     }
#   ]
# }""",

#         "summarise": """You summarise Srila Prabhupada's teachings.

# Structure:
# ## Summary: [Topic]

# ### Key Teachings
# [Numbered points, each cited with [REFERENCE]]

# ### Supporting Verses
# [Each key verse translation in > blockquote]

# ### Synthesis
# [One paragraph in Prabhupada's spirit]

# Rules: ONLY the provided sources. Cite every point. Bold key terms.""",
#     }
#     return prompts.get(task, prompts["ask"])


# # =============================================================================
# # USER PROMPTS
# # =============================================================================

# def build_user_prompt(task: str, query: str, context: str,
#                       top_n: int = 5, conversation_ctx: str = "") -> str:
#     prefix = f"{conversation_ctx}\n\n" if conversation_ctx else ""

#     if task == "reference":
#         return f"Display this verse:\n\n{context}"

#     if task == "quiz":
#         return (f"Generate {top_n} MCQ questions from ONLY these passages:\n\n"
#                 f"{context}\n\nScope: {query}")

#     if task == "summarise":
#         return (f"Summarise teachings on this topic from ONLY these passages.\n\n"
#                 f"Topic: {query}\n\nPassages:\n{context}")

#     if task == "explain":
#         return (f"{prefix}Explain using ONLY these passages:\n\n"
#                 f"Topic: {query}\n\nPassages:\n{context}")

#     return (f"{prefix}Use ONLY the passages below. Do NOT reference unlisted verses.\n\n"
#             f"===== SOURCE PASSAGES =====\n{context}\n===== END =====\n\n"
#             f"Question: {query}\n\nAnswer (cite ONLY listed sources with [REFERENCE]):")


# # =============================================================================
# # TASK AUTO-DETECTION
# # =============================================================================

# def detect_task(query: str) -> str:
#     """
#     Classify a free-form query into: ask | explain | summarise
#     Called only when the frontend sends task="ask" (the merged smart tab).
#     Uses a fast LLM call with strict output — falls back to "ask" on any error.
#     """
#     q = query.strip().lower()

#     # Fast keyword heuristics first (no LLM call needed)
#     if re.search(r'\b(summaris|summariz|summary|key teachings|overview|outline)\b', q):
#         return "summarise"
#     if re.search(r'\b(explain|what does .* mean|meaning of|elaborate|break down|definition of)\b', q):
#         return "explain"

#     # For ambiguous queries, ask the LLM
#     try:
#         prompt = (
#             "Classify this question into exactly ONE of: ask | explain | summarise\n"
#             "- ask: direct question seeking an answer from the scriptures\n"
#             "- explain: wants a detailed breakdown/meaning of a concept or verse\n"
#             "- summarise: wants a structured overview of a topic or set of teachings\n\n"
#             f"Question: {query}\n\n"
#             "Reply with ONLY one word: ask OR explain OR summarise"
#         )
#         result = call_llm("You are a text classifier. Reply with one word only.",
#                           prompt, max_tokens=5, temperature=0.0)
#         result = result.strip().lower()
#         if result in ("ask", "explain", "summarise"):
#             return result
#     except Exception as e:
#         logger.debug(f"Task auto-detect failed: {e}")

#     return "ask"


# # =============================================================================
# # GENERATE
# # =============================================================================

# def generate(
#     task:     str,
#     query:    str,
#     results:  list[RetrievalResult],
#     top_n:    int        = 5,
#     history:  list[dict] = None,
# ) -> GeneratedResponse:

#     mode_labels = {
#         "ask": "Semantic Q&A", "reference": "Direct Verse Lookup",
#         "explain": "Explanation", "quiz": "Quiz", "summarise": "Summary",
#     }

#     # Auto-detect task for the merged "ask" tab
#     # (frontend sends task="ask" for all free-form queries)
#     if task == "ask":
#         task = detect_task(query)

#     if not results:
#         return GeneratedResponse(
#             task=task, query=query,
#             answer="No relevant passages found. Please try rephrasing your question.",
#             sources=[], llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
#             mode=mode_labels.get(task, task),
#         )

#     is_direct = any(r.direct_lookup for r in results)
#     deduped   = deduplicate(results)
#     context   = build_context(deduped, include_wfw=(task == "reference" or is_direct))
#     conv_ctx  = build_conversation_context(history or [])

#     # Quiz needs more tokens — 10 questions × ~150 tokens each ≈ 1500 minimum
#     # Add headroom for JSON structure and longer explanations
#     effective_max_tokens = (max(MAX_TOKENS, top_n * 200 + 500)
#                             if task == "quiz" else MAX_TOKENS)

#     raw = call_llm(
#         get_system_prompt(task),
#         build_user_prompt(task, query, context, top_n=top_n,
#                           conversation_ctx=conv_ctx),
#         max_tokens=effective_max_tokens,
#     )

#     # Parse quiz JSON — handle both {"questions":[...]} and [...] shapes
#     quiz_data = None
#     if task == "quiz":
#         try:
#             # Strip markdown fences
#             clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
#             clean = clean.strip()
#             parsed = json.loads(clean)
#             if isinstance(parsed, list):
#                 quiz_data = parsed
#             elif isinstance(parsed, dict):
#                 quiz_data = parsed.get("questions", parsed.get("mcqs", []))
#             logger.info(f"Quiz parsed: {len(quiz_data or [])} questions")
#         except Exception as e:
#             logger.warning(f"Quiz JSON parse failed: {e} | raw[:200]={raw[:200]!r}")
#             # Attempt partial recovery — find JSON array anywhere in output
#             try:
#                 arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
#                 if arr_match:
#                     quiz_data = json.loads(arr_match.group())
#                     logger.info(f"Quiz partial recovery: {len(quiz_data)} questions")
#             except Exception:
#                 pass

#     return GeneratedResponse(
#         task=task, query=query, answer=raw, sources=deduped,
#         llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
#         context_used=[r.reference for r in deduped],
#         is_direct=is_direct, mode=mode_labels.get(task, task),
#         quiz_data=quiz_data,
#     )

from __future__ import annotations

from dotenv import load_dotenv
# load env variables
load_dotenv()

import os
import re
import json
import math
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import (
    CHROMA_DIR, ACTIVE_PROVIDER, ACTIVE_LLM, LLM_SPECS,
    MAX_TOKENS, TEMPERATURE, RETRIEVAL_K, RERANK_TOP_N,
    RERANKER_MODEL, BGE_QUERY_PREFIX,
    HYBRID_VECTOR_WEIGHT, HYBRID_BM25_WEIGHT, MMR_LAMBDA,
)

logger = logging.getLogger("core")

COLLECTION_NAME  = "prabhupada_rag"
RERANK_THRESHOLD = -2.0   # drop candidates below this cross-encoder score

BOOK_NAMES = {
    "bg":  "Bhagavad Gita As It Is",
    "iso": "Sri Isopanishad",
    "noi": "Nectar of Instruction",
    "bs":  "Brahma Samhita",
}


# =============================================================================
# STARTUP
# =============================================================================

_chroma_collection = None
_embedding_model   = None
_reranker          = None


def startup():
    global _chroma_collection, _embedding_model, _reranker
    logger.info("=== Backend startup ===")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    _chroma_collection = client.get_collection(name=COLLECTION_NAME)
    logger.info(f"ChromaDB: {_chroma_collection.count()} vectors")

    if ACTIVE_PROVIDER == "baai":
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        logger.info("Embedding: BAAI/bge-large-en-v1.5")

    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANKER_MODEL)
        logger.info(f"Reranker: {RERANKER_MODEL}")
    except Exception as e:
        logger.warning(f"Reranker unavailable: {e}")

    logger.info("=== Startup complete ===")


def get_db_count() -> int:
    return _chroma_collection.count() if _chroma_collection else 0


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RetrievalResult:
    chunk_id:       str
    reference:      str
    book:           str
    book_code:      str
    translation:    str
    purport:        str
    verse_sanskrit: str
    word_for_word:  str
    part:           int
    total_parts:    int
    vector_score:   float
    rerank_score:   float
    chunk_text:     str
    direct_lookup:  bool = False


@dataclass
class GeneratedResponse:
    task:         str
    query:        str
    answer:       str
    sources:      list[RetrievalResult]
    llm_model:    str
    context_used: list[str] = field(default_factory=list)
    is_direct:    bool      = False
    mode:         str       = ""
    quiz_data:    list[dict] | None = None


# =============================================================================
# LLM CALL  (defined early — used by query expansion too)
# =============================================================================

def call_llm(system_prompt: str, user_prompt: str,
             max_tokens: int = None, temperature: float = None) -> str:
    mt   = max_tokens  or MAX_TOKENS
    temp = temperature or TEMPERATURE
    model = LLM_SPECS[ACTIVE_LLM]["model"]

    if ACTIVE_LLM == "groq":
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system_prompt},
                      {"role":"user","content":user_prompt}],
            max_tokens=mt, temperature=temp,
        )
        return resp.choices[0].message.content.strip()

    if ACTIVE_LLM == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system_prompt},
                      {"role":"user","content":user_prompt}],
            max_tokens=mt, temperature=temp,
        )
        return resp.choices[0].message.content.strip()

    if ACTIVE_LLM == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        m = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=mt, temperature=temp),
        )
        return m.generate_content(user_prompt).text.strip()

    if ACTIVE_LLM == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=model, max_tokens=mt, system=system_prompt,
            messages=[{"role":"user","content":user_prompt}],
            temperature=temp,
        )
        return resp.content[0].text.strip()

    raise ValueError(f"Unknown LLM: {ACTIVE_LLM}")


# =============================================================================
# EMBEDDING
# =============================================================================

def embed_texts(texts: list[str]) -> list[list[float]]:
    if ACTIVE_PROVIDER == "baai":
        vecs = _embedding_model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    if ACTIVE_PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        res  = genai.embed_content(model="models/text-embedding-004",
                                   content=texts, task_type="retrieval_document")
        vecs = res["embedding"]
        return [vecs] if isinstance(vecs[0], float) else list(vecs)

    if ACTIVE_PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.embeddings.create(input=texts, model="text-embedding-3-small")
        return [item.embedding for item in resp.data]

    raise ValueError(f"Unknown provider: {ACTIVE_PROVIDER}")


def embed_query(query: str) -> list[float]:
    text = (BGE_QUERY_PREFIX + query) if ACTIVE_PROVIDER == "baai" else query
    return embed_texts([text])[0]


# =============================================================================
# QUERY EXPANSION  (zero LLM tokens — pure synonym dictionary)
# =============================================================================

# Bidirectional Sanskrit ↔ English synonym map.
# Expanding both directions catches: "what is atma" → also searches "soul",
# and "what is the soul" → also searches "atma / self / jiva".
_SYNONYM_MAP: dict[str, list[str]] = {
    # Sanskrit → English
    "atma":       ["soul", "self", "spirit"],
    "jiva":       ["living entity", "soul", "individual soul"],
    "bhakti":     ["devotion", "devotional service", "love of God"],
    "karma":      ["action", "work", "fruitive activity", "duty"],
    "maya":       ["illusion", "material energy", "material world"],
    "dharma":     ["duty", "religion", "righteous path"],
    "moksha":     ["liberation", "freedom", "mukti"],
    "mukti":      ["liberation", "freedom", "moksha"],
    "guru":       ["spiritual master", "teacher"],
    "krishna":    ["God", "Supreme Lord", "Bhagavan"],
    "yoga":       ["spiritual practice", "union with God"],
    "gyana":      ["knowledge", "wisdom", "jnana"],
    "jnana":      ["knowledge", "wisdom", "gyana"],
    "vairagya":   ["renunciation", "detachment"],
    "tapasya":    ["austerity", "penance"],
    "samsara":    ["cycle of birth and death", "material existence"],
    "prakriti":   ["material nature", "nature"],
    "purusha":    ["spirit", "enjoyer", "person"],
    "ahamkara":   ["false ego", "ego"],
    "manas":      ["mind"],
    "buddhi":     ["intelligence", "intellect"],
    "indriya":    ["senses", "sense organs"],
    "varna":      ["social order", "caste"],
    "ashrama":    ["stage of life"],
    "sannyasa":   ["renounced order", "renunciation"],
    "grhastha":   ["householder"],
    "brahmachari":["celibate student", "celibacy"],
    "sadhu":      ["saint", "devotee", "holy person"],
    "shastra":    ["scripture", "sacred text"],
    "parampara":  ["disciplic succession", "lineage"],
    "prasad":     ["mercy", "blessed food"],
    # English → Sanskrit
    "soul":           ["atma", "jiva", "self"],
    "self":           ["atma", "soul"],
    "devotion":       ["bhakti", "devotional service"],
    "devotional service": ["bhakti"],
    "illusion":       ["maya", "material energy"],
    "liberation":     ["moksha", "mukti", "freedom"],
    "knowledge":      ["jnana", "gyana", "wisdom"],
    "duty":           ["dharma", "karma"],
    "mind":           ["manas"],
    "intelligence":   ["buddhi"],
    "senses":         ["indriya"],
    "renunciation":   ["vairagya", "sannyasa"],
    "false ego":      ["ahamkara"],
    "scripture":      ["shastra"],
    "spiritual master": ["guru", "acharya"],
    "living entity":  ["jiva", "atma"],
    "supreme lord":   ["krishna", "bhagavan", "vishnu"],
    "material nature":["prakriti"],
    # intent verbs / concept framing
    "purpose":        ["goal", "aim", "objective", "meaning"],
    "goal":           ["purpose", "aim", "objective"],
    "aim":            ["goal", "purpose", "objective"],
    "objective":      ["goal", "purpose", "aim"],
    "meaning":        ["purpose", "significance", "sense"],
}

def expand_query(query: str) -> list[str]:
    """
    Returns original query + up to 1 synonym-enriched variant.
    Zero LLM tokens — pure dictionary lookup.
    Searches for known terms in the query and appends their synonyms.
    """
    q_lower = query.lower()
    added_terms: list[str] = []

    for term, synonyms in _SYNONYM_MAP.items():
        # Match whole words only
        if re.search(rf'\b{re.escape(term)}\b', q_lower):
            for syn in synonyms[:2]:
                if syn.lower() not in q_lower:
                    added_terms.append(syn)
            if len(added_terms) >= 4:
                break

    if not added_terms:
        return [query]

    # Build one enriched variant by appending synonyms
    enriched = query + " " + " ".join(added_terms[:3])
    logger.debug(f"Query expansion: '{query}' → also searching '{enriched}'")
    return [query, enriched]


# =============================================================================
# DIRECT REFERENCE DETECTION
# =============================================================================

def normalize_reference_query(query: str) -> str:
    """
    Normalize common human variants so regex patterns can parse references.
    Examples:
      BG2.47, Bg 2:47, Bhagavad Gita 2.47 -> bg 2.47
      Brahma Samhita 5.29 -> bs 5.29
    """
    q = query
    q = re.sub(r'(?i)\bbhagavad[-\s]*gita\b', 'bg', q)
    q = re.sub(r'(?i)\bisopanishad\b', 'iso', q)
    q = re.sub(r'(?i)\bnectar\s+of\s+instruction\b', 'noi', q)
    q = re.sub(r'(?i)\bbrahma\s*samhita\b', 'bs', q)
    q = re.sub(r'(?i)\bbg\s*([0-9])', r'bg \1', q)      # BG2.47 -> BG 2.47
    q = re.sub(r'(?i)\b(noi|iso|bs)\s*([0-9])', r'\1 \2', q)
    q = re.sub(r'(?i)\bbg\s*(\d+)\s*:\s*(\d+(?:-\d+)?)\b', r'bg \1.\2', q)
    q = re.sub(r'(?i)\bbs\s*5\s*:\s*(\d+)\b', r'bs 5.\1', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q


REFERENCE_PATTERNS = [
    (r'\bbg\.?\s*(\d+)\.(\d+(?:-\d+)?)\b', "bg"),
    (r'\bnoi\.?\s*(\d+)\b',                 "noi"),
    (r'\biso\.?\s*(\d+)\b',                 "iso"),
    (r'\bbs\.?\s*5\.(\d+)\b',              "bs"),
]


def detect_reference(query: str) -> list[dict] | None:
    query = normalize_reference_query(query)
    found = []
    for pattern, book_code in REFERENCE_PATTERNS:
        for match in re.finditer(pattern, query, re.IGNORECASE):
            if book_code == "bg":
                found.append({"book_code": book_code,
                               "d1": int(match.group(1)), "d2": match.group(2)})
            elif book_code == "bs":
                found.append({"book_code": book_code,
                               "d1": int(match.group(1)), "d2": None})
            else:
                found.append({"book_code": book_code,
                               "d1": int(match.group(1)), "d2": None})
    return found or None


def direct_lookup(refs: list[dict]) -> list[RetrievalResult]:
    results = []
    for ref in refs:
        d2  = ref.get("d2")
        cid = (f"{ref['book_code']}_{ref['d1']}_{d2}"
               if d2 else f"{ref['book_code']}_{ref['d1']}")
        try:
            resp = _chroma_collection.get(ids=[cid], include=["metadatas","documents"])
        except Exception:
            continue
        if not resp["ids"]:
            continue
        meta = resp["metadatas"][0]
        results.append(RetrievalResult(
            chunk_id=cid, reference=meta["reference"],
            book=meta["book"], book_code=meta["book_code"],
            translation=meta["translation"], purport=meta["purport"],
            verse_sanskrit=meta.get("verse_sanskrit",""),
            word_for_word=meta.get("word_for_word",""),
            part=meta.get("part",1), total_parts=meta.get("total_parts",1),
            vector_score=1.0, rerank_score=10.0,
            chunk_text=resp["documents"][0], direct_lookup=True,
        ))
    return results


# =============================================================================
# VECTOR SEARCH + RERANKING
# =============================================================================

def _tokenize_for_lexical(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _is_direct_reference_query(query: str) -> bool:
    return detect_reference(query) is not None


def _is_conceptual_query(query: str) -> bool:
    q = query.lower()
    if len(q.split()) >= 8:
        return True
    return bool(re.search(
        r"\b(why|how|meaning|purpose|goal|aim|difference|compare|relationship|"
        r"principle|teachings|philosophy|consciousness|nature of)\b", q
    ))


def _adaptive_k(query: str, default_k: int) -> int:
    words = len(query.split())
    if _is_direct_reference_query(query):
        return min(default_k, 8)
    if words <= 4:
        return min(default_k, 10)
    if _is_conceptual_query(query):
        return max(default_k, 24)
    return default_k


def _content_for_task_policy(meta: dict, chunk_text: str, query: str) -> str:
    if _is_direct_reference_query(query):
        # direct verse requests should emphasize verse text/translation fidelity
        return " ".join([
            meta.get("verse_sanskrit", ""),
            meta.get("word_for_word", ""),
            meta.get("translation", ""),
        ]).strip() or chunk_text
    # concept queries should bias toward purport
    if _is_conceptual_query(query):
        purport = meta.get("purport", "")
        if purport.strip():
            return purport
    return chunk_text


def _cosine(a: list[float], b: list[float]) -> float:
    if a is None or b is None:
        return 0.0
    try:
        if len(a) == 0 or len(b) == 0:
            return 0.0
    except TypeError:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _add_bm25_scores(query: str, candidates: list[dict]) -> None:
    tokens_q = _tokenize_for_lexical(query)
    if not tokens_q or not candidates:
        for c in candidates:
            c["bm25_score"] = 0.0
        return

    docs_tokens = []
    doc_lens = []
    term_df = Counter()
    for c in candidates:
        txt = _content_for_task_policy(c["metadata"], c["chunk_text"], query)
        toks = _tokenize_for_lexical(txt)
        docs_tokens.append(toks)
        doc_lens.append(len(toks))
        for t in set(toks):
            term_df[t] += 1

    n_docs = len(candidates)
    avgdl = (sum(doc_lens) / n_docs) if n_docs else 1.0
    k1, b = 1.5, 0.75

    for c, toks in zip(candidates, docs_tokens):
        tf = Counter(toks)
        dl = max(len(toks), 1)
        score = 0.0
        for t in tokens_q:
            if t not in tf:
                continue
            df = term_df.get(t, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            freq = tf[t]
            denom = freq + k1 * (1 - b + b * dl / max(avgdl, 1e-9))
            score += idf * ((freq * (k1 + 1)) / max(denom, 1e-9))
        c["bm25_score"] = round(score, 4)


def _hybrid_fuse_scores(candidates: list[dict]) -> None:
    if not candidates:
        return
    v_max = max(c.get("vector_score", 0.0) for c in candidates) or 1.0
    b_max = max(c.get("bm25_score", 0.0) for c in candidates) or 1.0
    vector_w = max(HYBRID_VECTOR_WEIGHT, 0.0)
    bm25_w = max(HYBRID_BM25_WEIGHT, 0.0)
    total_w = vector_w + bm25_w
    if total_w == 0:
        vector_w, bm25_w, total_w = 1.0, 0.0, 1.0
    for c in candidates:
        v = c.get("vector_score", 0.0) / v_max
        b = c.get("bm25_score", 0.0) / b_max
        c["hybrid_score"] = round((vector_w * v + bm25_w * b) / total_w, 4)


def _mmr_diversify(candidates: list[dict], top_k: int, lambda_mult: float | None = None) -> list[dict]:
    """
    Diversify by MMR before reranking to reduce near-duplicate chunks.
    Uses candidate embedding cosine similarity when available.
    """
    if len(candidates) <= top_k:
        return candidates
    if lambda_mult is None:
        lambda_mult = MMR_LAMBDA
    lambda_mult = min(max(lambda_mult, 0.0), 1.0)
    pool = sorted(candidates, key=lambda x: x.get("hybrid_score", x.get("vector_score", 0.0)), reverse=True)
    selected = [pool.pop(0)]
    while pool and len(selected) < top_k:
        best_idx = 0
        best_val = -1e9
        for idx, cand in enumerate(pool):
            rel = cand.get("hybrid_score", cand.get("vector_score", 0.0))
            emb = cand.get("embedding")
            max_sim = 0.0
            if emb is not None:
                for s in selected:
                    max_sim = max(max_sim, _cosine(emb, s.get("embedding", [])))
            mmr = lambda_mult * rel - (1 - lambda_mult) * max_sim
            if mmr > best_val:
                best_val = mmr
                best_idx = idx
        selected.append(pool.pop(best_idx))
    return selected


def _consolidate_parent_reference(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """
    Parent-child retrieval consolidation:
    if chunked purports exist, merge all parts for selected references so LLM
    sees verse-level complete context, not fragmented child chunks.
    """
    if not results:
        return []
    merged: list[RetrievalResult] = []
    for r in results:
        if r.total_parts <= 1:
            merged.append(r)
            continue
        try:
            resp = _chroma_collection.get(
                where={
                    "$and": [
                        {"book_code": {"$eq": r.book_code}},
                        {"reference": {"$eq": r.reference}},
                    ]
                },
                include=["metadatas", "documents"],
            )
        except Exception:
            merged.append(r)
            continue

        rows = list(zip(resp.get("metadatas", []), resp.get("documents", [])))
        if not rows:
            merged.append(r)
            continue
        rows.sort(key=lambda item: item[0].get("part", 1))
        parts = [m.get("purport", "").strip() for m, _ in rows if m.get("purport", "").strip()]
        full_purport = "\n\n".join(parts) if parts else r.purport
        first_meta = rows[0][0]
        merged.append(RetrievalResult(
            chunk_id=r.chunk_id,
            reference=r.reference,
            book=r.book,
            book_code=r.book_code,
            translation=first_meta.get("translation", r.translation),
            purport=full_purport,
            verse_sanskrit=first_meta.get("verse_sanskrit", r.verse_sanskrit),
            word_for_word=first_meta.get("word_for_word", r.word_for_word),
            part=1,
            total_parts=1,
            vector_score=r.vector_score,
            rerank_score=r.rerank_score,
            chunk_text=r.chunk_text,
            direct_lookup=r.direct_lookup,
        ))
    # remove duplicate references after consolidation
    by_ref: dict[str, RetrievalResult] = {}
    for x in merged:
        if x.reference not in by_ref or x.rerank_score > by_ref[x.reference].rerank_score:
            by_ref[x.reference] = x
    return sorted(by_ref.values(), key=lambda x: x.rerank_score, reverse=True)


def vector_search(query_vector: list[float], k: int,
                  book_filter: list[str]) -> list[dict]:
    where = None
    if book_filter and len(book_filter) == 1:
        where = {"book_code": {"$eq": book_filter[0]}}
    elif book_filter and len(book_filter) > 1:
        where = {"book_code": {"$in": book_filter}}

    kwargs = {
        "query_embeddings": [query_vector],
        "n_results": min(k, _chroma_collection.count()),
        "include":   ["metadatas","documents","distances","embeddings"],
    }
    if where:
        kwargs["where"] = where

    raw = _chroma_collection.query(**kwargs)
    return [
        {
            "metadata": m,
            "chunk_text": d,
            "embedding": e,
            "vector_score": round(1 - dist, 4),
        }
        for m, d, dist, e in zip(raw["metadatas"][0],
                                 raw["documents"][0],
                                 raw["distances"][0],
                                 raw.get("embeddings", [[]])[0] if raw.get("embeddings") else [[]] * len(raw["documents"][0]))
    ]


def rerank_candidates(query: str, candidates: list[dict],
                      top_n: int) -> list[dict]:
    if _reranker is None:
        for c in candidates:
            c["rerank_score"] = c["vector_score"]
        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_n]

    pairs  = [(query, _content_for_task_policy(c["metadata"], c["chunk_text"], query)) for c in candidates]
    scores = _reranker.predict(pairs)
    for c, s in zip(candidates, scores):
        c["rerank_score"] = round(float(s), 4)

    # Threshold filter
    filtered = [c for c in candidates if c["rerank_score"] >= RERANK_THRESHOLD]
    if not filtered:
        filtered = [max(candidates, key=lambda x: x["rerank_score"])]

    return sorted(filtered, key=lambda x: x["rerank_score"], reverse=True)[:top_n]


def candidates_to_results(candidates: list[dict]) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id=m.get("chunk_id",""), reference=m["reference"],
            book=m["book"], book_code=m["book_code"],
            translation=m["translation"], purport=m["purport"],
            verse_sanskrit=m.get("verse_sanskrit",""),
            word_for_word=m.get("word_for_word",""),
            part=m.get("part",1), total_parts=m.get("total_parts",1),
            vector_score=c["vector_score"], rerank_score=c["rerank_score"],
            chunk_text=c["chunk_text"], direct_lookup=False,
        )
        for c in candidates
        for m in [c["metadata"]]
    ]


# =============================================================================
# QUIZ AUTO-PARSE
# =============================================================================

def parse_quiz_intent(query: str) -> tuple[int, str | None, int | None]:
    """
    Returns (num_questions, book_code, chapter_number).
    
    Examples:
      "Make 10 MCQs from Chapter 2 of Bhagavad Gita" → (10, "bg", 2)
      "Quiz on BG Chapter 2"                          → (5,  "bg", 2)
      "5 questions from NOI"                          → (5,  "noi", None)
      "Make 5 MCQs from Nectar of Instruction"        → (5,  "noi", None)
    """
    q = query.lower()

    # Extract chapter number first (before extracting general numbers)
    chapter = None
    chapter_match = re.search(r'chapter\s+(\d+)', q)
    if chapter_match:
        chapter = int(chapter_match.group(1))

    # Extract question count — look for number NOT preceded by "chapter"
    # Replace "chapter N" with placeholder so it doesn't interfere
    q_no_chapter = re.sub(r'chapter\s+\d+', 'CHAPTER', q)
    num = 5
    num_match = re.search(r'\b(\d+)\b', q_no_chapter)
    if num_match:
        n = int(num_match.group(1))
        if 1 <= n <= 30:
            num = n

    # Extract book
    book_map = {
        "noi": "noi", "nectar of instruction": "noi", "nectar": "noi",
        "bg":  "bg",  "bhagavad gita": "bg", "gita": "bg", "bhagavad-gita": "bg",
        "iso": "iso", "isopanishad": "iso", "iso panishad": "iso",
        "bs":  "bs",  "brahma samhita": "bs", "brahmasamhita": "bs",
    }
    book_code = None
    for keyword, code in book_map.items():
        if keyword in q:
            book_code = code
            break

    return num, book_code, chapter

# =============================================================================
# RETRIEVE — main public function
# =============================================================================

def retrieve(
    query:          str,
    top_n:          int        = RERANK_TOP_N,
    k:              int        = RETRIEVAL_K,
    book_filter:    list[str]  = None,
    force_semantic: bool       = False,
    use_expansion:  bool       = True,
) -> list[RetrievalResult]:
    query = normalize_reference_query(query)
    book_filter = book_filter or []
    effective_k = _adaptive_k(query, k)

    # Direct reference lookup
    if not force_semantic:
        refs = detect_reference(query)
        if refs:
            direct = direct_lookup(refs)
            if direct:
                return direct

    # Query expansion
    queries = expand_query(query) if use_expansion else [query]

    # Search all variants, deduplicate by reference+part
    all_candidates: dict[str, dict] = {}
    for q in queries:
        qv = embed_query(q)
        dense_candidates = vector_search(qv, k=effective_k, book_filter=book_filter)
        _add_bm25_scores(q, dense_candidates)
        _hybrid_fuse_scores(dense_candidates)
        mmr_candidates = _mmr_diversify(
            dense_candidates,
            top_k=min(max(top_n * 4, 12), len(dense_candidates)),
        )
        for c in mmr_candidates:
            key = (c["metadata"].get("reference","")
                   + str(c["metadata"].get("part", 1)))
            if key not in all_candidates or \
               c.get("hybrid_score", c["vector_score"]) > all_candidates[key].get("hybrid_score", all_candidates[key]["vector_score"]):
                all_candidates[key] = c

    if not all_candidates:
        return []

    reranked = rerank_candidates(query, list(all_candidates.values()), top_n=top_n)
    return _consolidate_parent_reference(candidates_to_results(reranked))


def retrieve_by_scope(book_code: str, top_n: int = 20) -> list[RetrievalResult]:
    import random
    resp = _chroma_collection.get(
        where={"book_code": {"$eq": book_code}},
        include=["metadatas","documents"],
    )
    results = [
        RetrievalResult(
            chunk_id=meta.get("chunk_id",""), reference=meta["reference"],
            book=meta["book"], book_code=meta["book_code"],
            translation=meta["translation"], purport=meta["purport"],
            verse_sanskrit=meta.get("verse_sanskrit",""),
            word_for_word=meta.get("word_for_word",""),
            part=meta.get("part",1), total_parts=meta.get("total_parts",1),
            vector_score=1.0, rerank_score=1.0, chunk_text=doc,
            direct_lookup=False,
        )
        for meta, doc in zip(resp["metadatas"], resp["documents"])
    ]
    # Shuffle so whole-book quiz/summarise samples evenly across chapters,
    # not just whatever chapter happens to be first in DB insertion order.
    random.shuffle(results)
    return results[:top_n]

def retrieve_by_chapter(book_code: str, chapter: int, top_n: int = 20) -> list[RetrievalResult]:
    """
    Retrieve all verses from a specific chapter of a book.
    Used for chapter-specific quiz/summarise requests.
    ChromaDB 'division_1' stores chapter number for BG.
    Always fetches ALL verses in the chapter (ignoring top_n cap here)
    so the LLM has complete material to generate questions from.
    """
    resp = _chroma_collection.get(
        where={
            "$and": [
                {"book_code":  {"$eq": book_code}},
                {"division_1": {"$eq": chapter}},
            ]
        },
        include=["metadatas", "documents"],
    )
    results = [
        RetrievalResult(
            chunk_id=meta.get("chunk_id", ""), reference=meta["reference"],
            book=meta["book"], book_code=meta["book_code"],
            translation=meta["translation"], purport=meta["purport"],
            verse_sanskrit=meta.get("verse_sanskrit", ""),
            word_for_word=meta.get("word_for_word", ""),
            part=meta.get("part", 1), total_parts=meta.get("total_parts", 1),
            vector_score=1.0, rerank_score=1.0, chunk_text=doc,
            direct_lookup=False,
        )
        for meta, doc in zip(resp["metadatas"], resp["documents"])
    ]
    logger.info(f"retrieve_by_chapter({book_code}, ch={chapter}): {len(results)} verses fetched")
    # Return all chapter verses up to a hard cap of 60 so context isn't too large
    return results[:60]


# =============================================================================
# DEDUPLICATION + CONTEXT
# =============================================================================

def deduplicate(results: list[RetrievalResult]) -> list[RetrievalResult]:
    seen = {}
    for r in results:
        if r.reference not in seen or r.rerank_score > seen[r.reference].rerank_score:
            seen[r.reference] = r
    return sorted(seen.values(), key=lambda r: r.rerank_score, reverse=True)


def build_context(results: list[RetrievalResult],
                  include_wfw: bool = False,
                  task: str = "ask") -> str:
    """
    Build the context string injected into the LLM prompt.

    Token budget per source (approximate):
      reference    : full purport (user wants the complete text)
      quiz/summarise: purport truncated to 800 chars (needs breadth, not depth)
      ask/explain  : purport truncated to 600 chars (answer quality fine with this)

    This is the single biggest lever for token reduction — BG purports can be
    5000+ chars each. With 5 sources that blows the 12k TPM limit alone.
    """
    # Per-task purport character budget
    purport_limit = {
        "reference": 99999,   # show full purport for verse lookup
        "quiz":      800,
        "summarise": 800,
        "explain":   700,
        "ask":       600,
    }.get(task, 600)

    wfw_limit = 200  # word-for-word is rarely needed in full

    blocks = []
    for i, r in enumerate(results, 1):
        lines = [f"[SOURCE {i}] {r.reference} — {r.book}"]
        if r.verse_sanskrit.strip():
            lines.append(f"Sanskrit: {r.verse_sanskrit}")
        if include_wfw and r.word_for_word.strip():
            wfw = r.word_for_word
            if len(wfw) > wfw_limit:
                wfw = wfw[:wfw_limit] + "…"
            lines.append(f"Word-for-Word: {wfw}")
        lines.append(f"Translation: {r.translation}")
        if r.purport.strip():
            purport = r.purport
            if len(purport) > purport_limit:
                purport = purport[:purport_limit] + "…"
            lines.append(f"Purport: {purport}")
        blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def build_conversation_context(history: list[dict]) -> str:
    """
    Summarise recent conversation for the LLM.
    Keep to 2 exchanges (4 messages) max, each truncated to 150 chars.
    This caps history at ~120 tokens regardless of answer length.
    """
    if not history:
        return ""
    recent = history[-4:]   # last 2 exchanges = 4 messages
    lines  = ["Prior context:"]
    for msg in recent:
        prefix  = "Q" if msg["role"] == "user" else "A"
        content = msg["content"][:150].replace("\n", " ")
        lines.append(f"{prefix}: {content}")
    return "\n".join(lines)


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

def get_system_prompt(task: str) -> str:
    # Kept deliberately terse — every word costs tokens on Groq free tier.
    prompts = {

        "ask": (
            "You are a respectful assistant for Srila Prabhupada's teachings. "
            "Rules: (1) Answer ONLY from [SOURCE] passages. "
            "(2) Never cite unlisted verses. "
            "(3) Cite every claim: [BG 2.47]. "
            "(4) Bold key spiritual terms. "
            "(5) If sources insufficient, say so. "
            "(6) No speculation. Devotional tone. No repetition."
        ),

        "reference": (
            "Display this verse in order: "
            "## [Ref] — [Book]\n**Sanskrit:** …\n**Word-for-Word:** …\n"
            "**Translation:** …\n**Purport (key teaching):** 2-3 sentences. "
            "Use ONLY provided content."
        ),

        "explain": (
            "You are a Vaishnava teacher. Structure: "
            "(1) Quote relevant translation(s) with [REF]. "
            "(2) Clear explanation for modern audience. "
            "(3) One-sentence Key Insight. "
            "Only use provided sources. Bold key terms first use."
        ),

        "quiz": (
            "Generate MCQs from the provided passages. "
            "Return ONLY valid JSON, no other text:\n"
            '{"questions":[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],'
            '"answer":"A. ...","reference":"BG 2.47","explanation":"One sentence."}]}'
        ),

        "summarise": (
            "Summarise Srila Prabhupada's teachings from the provided passages. "
            "Structure: ## Summary: [Topic] | ### Key Teachings (numbered, each cited) | "
            "### Synthesis (one paragraph). "
            "Only use provided sources. Bold key terms."
        ),
    }
    return prompts.get(task, prompts["ask"])


# =============================================================================
# USER PROMPTS
# =============================================================================

def build_user_prompt(task: str, query: str, context: str,
                      top_n: int = 5, conversation_ctx: str = "") -> str:
    prefix = f"{conversation_ctx}\n\n" if conversation_ctx else ""

    if task == "reference":
        return f"Display this verse:\n\n{context}"

    if task == "quiz":
        return (f"Generate {top_n} MCQ questions from ONLY these passages:\n\n"
                f"{context}\n\nScope: {query}")

    if task == "summarise":
        return (f"Summarise teachings on this topic from ONLY these passages.\n\n"
                f"Topic: {query}\n\nPassages:\n{context}")

    if task == "explain":
        return (f"{prefix}Explain using ONLY these passages:\n\n"
                f"Topic: {query}\n\nPassages:\n{context}")

    return (f"{prefix}Use ONLY the passages below. Do NOT reference unlisted verses.\n\n"
            f"===== SOURCE PASSAGES =====\n{context}\n===== END =====\n\n"
            f"Question: {query}\n\nAnswer (cite ONLY listed sources with [REFERENCE]):")


# =============================================================================
# TASK AUTO-DETECTION  (zero LLM tokens — keyword heuristics only)
# =============================================================================

def detect_task(query: str) -> str:
    """
    Classify a free-form query into: ask | explain | summarise.
    Pure regex/keyword — no LLM call, zero tokens consumed.
    Called when frontend sends task="ask" (smart merged tab).
    """
    q = query.strip().lower()

    # summarise signals
    if re.search(
        r'\b(summaris|summariz|summary|key teachings|key points|overview|'
        r'outline|what are the main|list the|enumerate)\b', q
    ):
        return "summarise"

    # explain signals
    if re.search(
        r'\b(explain|what (does|is|are)|meaning of|means?|elaborate|'
        r'break down|definition of|describe|tell me about|how does|'
        r'what do you mean|clarif)\b', q
    ):
        return "explain"

    # Default — direct question
    return "ask"


# =============================================================================
# GENERATE
# =============================================================================

# Per-task output token budgets — tuned for Groq free tier (12k TPM).
# These are MAX output tokens; the model stops earlier if the answer is complete.
_OUTPUT_TOKENS: dict[str, int] = {
    "ask":       700,   # Q&A: concise answer with citations
    "reference": 500,   # Verse display: structured but bounded
    "explain":   700,   # Explanation: verse + explanation + insight
    "summarise": 900,   # Summary: needs more structure
    "quiz":      0,     # Computed dynamically: top_n × 180 + 200
}

# Hard cap on sources fed to the LLM — prevents context explosion on free tier.
# User can request more via top_n but we silently cap here.
_MAX_SOURCES_FREE_TIER = 4


def generate(
    task:     str,
    query:    str,
    results:  list[RetrievalResult],
    top_n:    int        = 5,
    history:  list[dict] = None,
) -> GeneratedResponse:

    mode_labels = {
        "ask": "Semantic Q&A", "reference": "Direct Verse Lookup",
        "explain": "Explanation", "quiz": "Quiz", "summarise": "Summary",
    }

    # Auto-detect sub-task for the merged "ask" tab (zero tokens)
    if task == "ask":
        task = detect_task(query)

    if not results:
        return GeneratedResponse(
            task=task, query=query,
            answer="No relevant passages found. Please try rephrasing your question.",
            sources=[], llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
            mode=mode_labels.get(task, task),
        )

    is_direct = any(r.direct_lookup for r in results)
    deduped   = deduplicate(results)

    # Cap sources fed to LLM to stay within TPM budget
    capped = deduped[:_MAX_SOURCES_FREE_TIER]

    context  = build_context(
        capped,
        include_wfw=(task == "reference" or is_direct),
        task=task,
    )
    conv_ctx = build_conversation_context(history or [])

    # Dynamic token budget
    if task == "quiz":
        out_tokens = min(top_n * 180 + 200, 2500)
    else:
        out_tokens = _OUTPUT_TOKENS.get(task, 700)

    raw = call_llm(
        get_system_prompt(task),
        build_user_prompt(task, query, context, top_n=top_n,
                          conversation_ctx=conv_ctx),
        max_tokens=out_tokens,
    )

    # Parse quiz JSON — handle {"questions":[...]}, [...], {"mcqs":[...]}
    quiz_data = None
    if task == "quiz":
        try:
            clean  = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                quiz_data = parsed
            elif isinstance(parsed, dict):
                quiz_data = parsed.get("questions", parsed.get("mcqs", []))
            logger.info(f"Quiz parsed: {len(quiz_data or [])} questions")
        except Exception as e:
            logger.warning(f"Quiz JSON parse failed: {e} | raw[:200]={raw[:200]!r}")
            try:
                arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
                if arr_match:
                    quiz_data = json.loads(arr_match.group())
                    logger.info(f"Quiz partial recovery: {len(quiz_data)} questions")
            except Exception:
                pass

    return GeneratedResponse(
        task=task, query=query, answer=raw, sources=deduped,
        llm_model=LLM_SPECS[ACTIVE_LLM]["model"],
        context_used=[r.reference for r in deduped],
        is_direct=is_direct, mode=mode_labels.get(task, task),
        quiz_data=quiz_data,
    )