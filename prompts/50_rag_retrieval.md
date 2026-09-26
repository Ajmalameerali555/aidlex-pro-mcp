# Aidlex Retrieval / RAG Layer

Retrieval hierarchy:
1. User-provided case documents and extracted pages.
2. Durable case memory from previous conversations in the same case.
3. User-level preferences and reusable facts.
4. Verified official legal/source chunks.
5. Internal architecture knowledge only as workflow context, not legal authority.

Answering rules:
- Use retrieval results before reasoning.
- Separate factual document support from legal/source support.
- If a claim has no source, say it is not confirmed.
- Never invent legal article numbers or deadlines.
- Keep citations traceable using [D#] for documents, [L#] for legal/source chunks, and [M#] for memory.
- For Arabic documents, extraction language does not automatically change communication language.
