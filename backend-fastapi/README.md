# Backend - FastAPI PDF QA API

This is the backend for the Angular PDF Question Answering NLP project.

## What the backend does

1. Receives a PDF file from Angular.
2. Extracts text from the PDF.
3. Splits the text into chunks.
4. Converts chunks into embeddings.
5. Receives a question.
6. Finds the most relevant PDF chunks.
7. Extracts the answer from the relevant chunks.

## Requirements

- Python 3.10 or newer

## Run Backend

```bash
cd backend-fastapi
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open API Swagger:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### Health Check

```http
GET /api/health
```

### Upload PDF

```http
POST /api/pdf/upload
```

Form field:

```text
file
```

### Ask Question

```http
POST /api/pdf/ask
```

Body:

```json
{
  "docId": "uploaded-document-id",
  "question": "What is the conclusion?",
  "topK": 5
}
```

## Notes

- The first run can take time because models are downloaded.
- Uploaded PDFs are stored in memory only.
- If the PDF is scanned as images, this version needs OCR before it can read the text.