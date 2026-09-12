from typing import Any
from neo4j import Driver


def _extract_function_text(fn: dict) -> str:
    """Builds a rich text feature representation of a function for vector indexing."""
    parts = []
    name = fn.get("name") or ""
    parts.append(name)
    parts.append(name.replace("_", " "))

    args = fn.get("args") or []
    if isinstance(args, list):
        parts.append(" ".join(args))

    docstring = fn.get("docstring") or ""
    if docstring:
        parts.append(docstring)

    snippet = fn.get("code_snippet") or ""
    if snippet:
        parts.append(snippet)

    return " ".join(parts)


def find_similar_functions(
    driver: Driver,
    name: str,
    file: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Finds functions semantically and structurally similar to the target function using TF-IDF feature vectors and Cosine Similarity.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return [{"error": "scikit-learn is required for similarity search. Run pip install scikit-learn"}]

    query = """
    MATCH (fn:Function)
    RETURN fn.name AS name,
           fn.file AS file,
           fn.docstring AS docstring,
           fn.code_snippet AS code_snippet,
           fn.args AS args,
           fn.line_count AS line_count
    """
    with driver.session() as session:
        records = [dict(r) for r in session.run(query)]

    if not records:
        return []

    target_idx = None
    corpus = []
    for idx, item in enumerate(records):
        text = _extract_function_text(item)
        corpus.append(text)
        if item["name"].lower() == name.lower():
            if file is None or item["file"] == file:
                target_idx = idx

    if target_idx is None:
        # Fallback to case-insensitive partial match if exact name not found
        for idx, item in enumerate(records):
            if name.lower() in item["name"].lower():
                target_idx = idx
                break

    if target_idx is None:
        return []

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b")
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    target_vector = tfidf_matrix[target_idx]
    similarities = cosine_similarity(target_vector, tfidf_matrix).flatten()

    results = []
    for idx, score in enumerate(similarities):
        if idx == target_idx:
            continue
        item = records[idx]
        results.append(
            {
                "name": item["name"],
                "file": item["file"],
                "similarity_score": round(float(score), 4),
                "docstring": item.get("docstring") or "",
                "snippet": item.get("code_snippet") or "",
                "line_count": item.get("line_count") or 0,
            }
        )

    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:top_k]
