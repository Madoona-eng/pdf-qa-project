import re
import uuid
from functools import lru_cache
from typing import Any

import fitz  # PyMuPDF
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer, util


app = FastAPI(
    title="PDF Question Answering API",
    description="Upload PDF files and ask questions from their content.",
    version="1.0.0"
)

# Allow Angular during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
# Important: uploaded PDFs disappear when backend restarts.
DOCUMENT_STORE: dict[str, dict[str, Any]] = {}


class AskRequest(BaseModel):
    docId: str
    question: str
    topK: int = 5


class RelevantChunkResponse(BaseModel):
    page: int
    similarityScore: float
    text: str


class AskResponse(BaseModel):
    success: bool
    answer: str | None = None
    page: int | None = None
    confidence: float | None = None
    sourceContext: str | None = None
    relevantChunks: list[RelevantChunkResponse] = Field(default_factory=list)
    message: str | None = None


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Loads the embedding model once.
    This model converts PDF text and user questions into vectors.
    """
    return SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


def clean_text(text: str) -> str:
    """
    Cleans extracted PDF text.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"[_]{3,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_cv_text(text: str) -> str:
    """
    Extra normalization for CV-like PDFs.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"[_\-]{3,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_pages(file_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extracts readable text from PDF pages.
    This works with text-based PDFs.
    Scanned PDFs need OCR.
    """
    pages: list[dict[str, Any]] = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as ex:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid PDF file: {str(ex)}"
        )

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text")
        text = clean_text(text)

        if text:
            pages.append({
                "page": page_index,
                "text": text
            })

    doc.close()
    return pages


def split_pages_into_chunks(
    pages: list[dict[str, Any]],
    chunk_size: int = 180,
    overlap: int = 40
) -> list[dict[str, Any]]:
    """
    Splits PDF text into chunks.
    Each chunk keeps its page number.
    """
    chunks: list[dict[str, Any]] = []

    for page_item in pages:
        page_number = page_item["page"]
        words = page_item["text"].split()

        if len(words) <= chunk_size:
            chunks.append({
                "page": page_number,
                "text": page_item["text"]
            })
            continue

        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words).strip()

            if chunk_text:
                chunks.append({
                    "page": page_number,
                    "text": chunk_text
                })

            start += chunk_size - overlap

    return chunks


def split_text_into_sentences(text: str) -> list[str]:
    """
    Splits text into sentences.
    """
    sentences = re.split(r"(?<=[.!?؟])\s+", text)

    clean_sentences = []

    for sentence in sentences:
        sentence = sentence.strip()

        if len(sentence) >= 15:
            clean_sentences.append(sentence)

    if not clean_sentences and text.strip():
        clean_sentences.append(text.strip())

    return clean_sentences


def is_probably_heading(sentence: str) -> bool:
    """
    Detects short headings/questions like:
    What is Programming?
    Why Learn Programming?
    Introduction to Programming
    """
    sentence = sentence.strip()
    words = sentence.split()

    if len(sentence) <= 90 and sentence.endswith(("?", "؟")):
        return True

    if len(words) <= 7 and not sentence.endswith("."):
        return True

    return False


def get_important_words(text: str) -> set[str]:
    """
    Gets important words from the question or heading.
    Removes common English stop words.
    Also supports Arabic characters.
    """
    stop_words = {
        "what", "why", "how", "when", "where", "who",
        "is", "are", "am", "was", "were",
        "the", "a", "an", "of", "to", "in", "on", "for",
        "and", "or", "do", "does", "did",
        "with", "from", "by", "about"
    }

    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]", " ", text)

    words = []

    for word in text.split():
        word = word.strip()

        if len(word) <= 2:
            continue

        if word in stop_words:
            continue

        words.append(word)

    return set(words)


def heading_matches_question(question: str, heading: str) -> bool:
    """
    Checks whether a PDF heading matches the user question.

    Example:
    User question: Why learn programming?
    PDF heading: Why Learn Programming?
    """
    question_words = get_important_words(question)
    heading_words = get_important_words(heading)

    if not question_words or not heading_words:
        return False

    overlap = question_words.intersection(heading_words)
    overlap_ratio = len(overlap) / len(question_words)

    return overlap_ratio >= 0.70


def extract_answer_after_matching_heading(
    question: str,
    relevant_chunks: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """
    If the PDF contains a heading similar to the question,
    return the first useful sentence after that heading.

    Example:
    Heading: Why Learn Programming?
    Answer: Learning to code enables individuals to build software...
    """
    for chunk in relevant_chunks:
        text = chunk["text"]

        heading_matches = list(
            re.finditer(r"[^.!?؟]{3,90}[?؟]", text)
        )

        for match in heading_matches:
            heading = match.group(0).strip()

            if not heading_matches_question(question, heading):
                continue

            after_heading = text[match.end():].strip()

            if not after_heading:
                continue

            sentences = split_text_into_sentences(after_heading)

            for sentence in sentences:
                if is_probably_heading(sentence):
                    continue

                return {
                    "answer": sentence,
                    "page": chunk["page"],
                    "confidence": chunk["similarityScore"],
                    "sourceContext": chunk["text"]
                }

    return None


def extract_direct_cv_answer(
    question: str,
    chunks: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """
    Direct extraction for CV questions.
    This runs before semantic search.

    It prevents answers like returning the whole CV summary
    when the user asks for one specific field such as faculty or university.
    """
    q = question.lower().strip()

    faculty_keywords = [
        "كلية", "الكليه", "الكلية", "كليه",
        "faculty", "college"
    ]

    university_keywords = [
        "جامعة", "الجامعة", "جامعه",
        "university"
    ]

    degree_keywords = [
        "مؤهل", "المؤهل", "درجة", "شهادة", "بكالوريوس",
        "degree", "bachelor"
    ]

    major_keywords = [
        "تخصص", "التخصص", "major"
    ]

    grade_keywords = [
        "تقدير", "التقدير", "grade", "gpa"
    ]

    for chunk in chunks:
        text = normalize_cv_text(chunk["text"])

        # Faculty / College
        if any(word in q for word in faculty_keywords):
            match = re.search(
                r"(Faculty of [A-Za-z\s&]+?)\s+(Minya University|[A-Za-z\s]+ University)",
                text,
                re.IGNORECASE
            )

            if match:
                faculty = match.group(1).strip()
                university = match.group(2).strip()

                return {
                    "answer": f"{faculty} - {university}",
                    "page": chunk["page"],
                    "confidence": 1.0,
                    "sourceContext": chunk["text"]
                }

        # University only
        if any(word in q for word in university_keywords):
            match = re.search(
                r"(Minya University|[A-Za-z\s]+ University)",
                text,
                re.IGNORECASE
            )

            if match:
                return {
                    "answer": match.group(1).strip(),
                    "page": chunk["page"],
                    "confidence": 1.0,
                    "sourceContext": chunk["text"]
                }

        # Degree / Qualification
        if any(word in q for word in degree_keywords):
            match = re.search(
                r"(Bachelor of [A-Za-z\s]+?)(?=\s+Faculty|\s+Minya|\s+Egypt|\s+\d{2}/\d{4}|$)",
                text,
                re.IGNORECASE
            )

            if match:
                return {
                    "answer": match.group(1).strip(),
                    "page": chunk["page"],
                    "confidence": 1.0,
                    "sourceContext": chunk["text"]
                }

        # Major
        if any(word in q for word in major_keywords):
            match = re.search(
                r"Major in ([A-Za-z\s]+?)(?:\s+[–-]\s+|\s+good grade|\s+\(|$)",
                text,
                re.IGNORECASE
            )

            if match:
                return {
                    "answer": match.group(1).strip(),
                    "page": chunk["page"],
                    "confidence": 1.0,
                    "sourceContext": chunk["text"]
                }

        # Grade
        if any(word in q for word in grade_keywords):
            match = re.search(
                r"(excellent grade\s*\([^)]+\)|very good grade\s*\([^)]+\)|good grade\s*\([^)]+\)|pass grade\s*\([^)]+\))",
                text,
                re.IGNORECASE
            )

            if match:
                return {
                    "answer": match.group(1).strip(),
                    "page": chunk["page"],
                    "confidence": 1.0,
                    "sourceContext": chunk["text"]
                }

    return None


def extract_best_answer(
    question: str,
    relevant_chunks: list[dict[str, Any]],
    embedding_model: SentenceTransformer
) -> dict[str, Any]:
    """
    Extracts the best answer from the retrieved chunks.

    Priority:
    1. If the question matches a heading in the PDF,
       return the sentence after that heading.
    2. Otherwise, use semantic similarity,
       while giving priority to higher-ranked PDF chunks.
    """

    # First: heading-based extraction
    heading_answer = extract_answer_after_matching_heading(
        question=question,
        relevant_chunks=relevant_chunks
    )

    if heading_answer:
        return heading_answer

    # Fallback: semantic sentence search
    candidate_sentences: list[dict[str, Any]] = []

    for chunk in relevant_chunks:
        sentences = split_text_into_sentences(chunk["text"])

        for sentence in sentences:
            if is_probably_heading(sentence):
                continue

            candidate_sentences.append({
                "text": sentence,
                "page": chunk["page"],
                "chunkScore": chunk["similarityScore"],
                "sourceContext": chunk["text"]
            })

    if not candidate_sentences:
        first_chunk = relevant_chunks[0]

        return {
            "answer": first_chunk["text"][:500],
            "page": first_chunk["page"],
            "confidence": first_chunk["similarityScore"],
            "sourceContext": first_chunk["text"]
        }

    sentence_texts = [item["text"] for item in candidate_sentences]

    question_embedding = embedding_model.encode(
        question,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    sentence_embeddings = embedding_model.encode(
        sentence_texts,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    hits = util.semantic_search(
        question_embedding,
        sentence_embeddings,
        top_k=len(candidate_sentences)
    )[0]

    best_item = None
    best_score = -1.0

    for hit in hits:
        sentence_index = hit["corpus_id"]
        sentence_score = float(hit["score"])

        item = candidate_sentences[sentence_index]

        # Combine sentence similarity with chunk similarity
        # This prevents weak chunks from winning too easily.
        final_score = (sentence_score * 0.65) + (item["chunkScore"] * 0.35)

        if final_score > best_score:
            best_score = final_score
            best_item = item

    return {
        "answer": best_item["text"],
        "page": best_item["page"],
        "confidence": best_score,
        "sourceContext": best_item["sourceContext"]
    }


@app.get("/api/health")
def health_check():
    return {
        "success": True,
        "message": "PDF QA backend is running."
    }


@app.post("/api/pdf/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload PDF, extract text, split into chunks, and create embeddings.
    """
    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed."
            )

        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Empty file uploaded."
            )

        pages = extract_pdf_pages(file_bytes)

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No readable text found. This PDF may be scanned and needs OCR."
            )

        chunks = split_pages_into_chunks(pages)

        embedding_model = get_embedding_model()
        chunk_texts = [chunk["text"] for chunk in chunks]

        embeddings = embedding_model.encode(
            chunk_texts,
            convert_to_tensor=True,
            normalize_embeddings=True
        )

        doc_id = str(uuid.uuid4())

        DOCUMENT_STORE[doc_id] = {
            "fileName": file.filename,
            "pagesCount": len(pages),
            "chunksCount": len(chunks),
            "chunks": chunks,
            "embeddings": embeddings
        }

        return {
            "success": True,
            "docId": doc_id,
            "fileName": file.filename,
            "pagesCount": len(pages),
            "chunksCount": len(chunks),
            "message": "PDF uploaded and indexed successfully."
        }

    except HTTPException:
        raise

    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(ex)}"
        )


@app.post("/api/pdf/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    """
    Receives a question and answers it using the uploaded PDF content.
    """
    try:
        if request.docId not in DOCUMENT_STORE:
            raise HTTPException(
                status_code=404,
                detail="Document not found. Please upload the PDF again."
            )

        question = request.question.strip()

        if not question:
            raise HTTPException(
                status_code=400,
                detail="Question is required."
            )

        document = DOCUMENT_STORE[request.docId]
        chunks = document["chunks"]
        embeddings = document["embeddings"]

        # 1. Direct CV extraction first
        # This returns short answers for questions like:
        # اي الكلية؟ الجامعة؟ المؤهل؟ التخصص؟ التقدير؟
        direct_answer = extract_direct_cv_answer(
            question=question,
            chunks=chunks
        )

        if direct_answer:
            return AskResponse(
                success=True,
                answer=direct_answer["answer"],
                page=direct_answer["page"],
                confidence=direct_answer["confidence"],
                sourceContext=direct_answer["sourceContext"],
                relevantChunks=[
                    RelevantChunkResponse(
                        page=direct_answer["page"],
                        similarityScore=direct_answer["confidence"],
                        text=direct_answer["sourceContext"]
                    )
                ]
            )

        # 2. Semantic search fallback for general questions
        embedding_model = get_embedding_model()

        question_embedding = embedding_model.encode(
            question,
            convert_to_tensor=True,
            normalize_embeddings=True
        )

        hits = util.semantic_search(
            question_embedding,
            embeddings,
            top_k=min(max(request.topK, 1), len(chunks))
        )[0]

        relevant_chunks: list[dict[str, Any]] = []

        for hit in hits:
            chunk_index = hit["corpus_id"]

            relevant_chunks.append({
                "page": chunks[chunk_index]["page"],
                "text": chunks[chunk_index]["text"],
                "similarityScore": float(hit["score"])
            })

        response_chunks = [
            RelevantChunkResponse(
                page=item["page"],
                similarityScore=item["similarityScore"],
                text=item["text"]
            )
            for item in relevant_chunks
        ]

        if not relevant_chunks:
            return AskResponse(
                success=False,
                message="No relevant text was found in the PDF.",
                relevantChunks=[]
            )

        best_answer = extract_best_answer(
            question=question,
            relevant_chunks=relevant_chunks,
            embedding_model=embedding_model
        )

        return AskResponse(
            success=True,
            answer=best_answer["answer"],
            page=best_answer["page"],
            confidence=best_answer["confidence"],
            sourceContext=best_answer["sourceContext"],
            relevantChunks=response_chunks
        )

    except HTTPException:
        raise

    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Ask failed: {str(ex)}"
        )