# Angular + Backend PDF Question Answering NLP Project

## Project Idea

This project is a PDF Question Answering system.

The user can:

1. Upload a PDF file.
2. Ask a question.
3. Get an answer from the PDF content.

## Project Parts

```text
angular_pdf_qa_full_project/
│
├── frontend-angular/
│   └── Angular user interface
│
└── backend-fastapi/
    └── Python FastAPI NLP backend
```

## Why Angular + Backend?

Angular is used for the user interface only.

The backend is responsible for:

- Reading the PDF.
- Extracting text.
- Splitting text into chunks.
- Running NLP models.
- Returning answers.

This is better because NLP models are heavy and should not run inside the browser.

## How the System Works

### Step 1: Upload PDF

Angular sends the PDF file to:

```http
POST http://127.0.0.1:8000/api/pdf/upload
```

The backend extracts text from the PDF.

### Step 2: Chunking

The backend splits the text into small chunks.

Example:

```text
PDF text → chunk 1, chunk 2, chunk 3, ...
```

### Step 3: Embeddings

Each chunk is converted into a vector using SentenceTransformers.

A vector is a numeric representation of text meaning.

### Step 4: Ask Question

Angular sends the question to:

```http
POST http://127.0.0.1:8000/api/pdf/ask
```

### Step 5: Semantic Search

The backend converts the question into a vector and compares it with the PDF chunk vectors.

The most relevant chunks are selected.

### Step 6: Answer Extraction

A QA model reads the most relevant chunks and extracts the answer.

### Step 7: Response to Angular

The backend sends:

- Answer
- Page number
- Confidence
- Source context
- Relevant chunks

## Run Backend

```bash
cd backend-fastapi
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Check backend:

```text
http://127.0.0.1:8000/docs
```

## Run Frontend

Open another terminal:

```bash
cd frontend-angular
npm install
npm start
```

Open:

```text
http://localhost:4200
```

## Important Notes

- Use text-based PDFs.
- Scanned PDFs need OCR.
- First backend run may take time because NLP models are downloaded.
- Uploaded documents are stored in memory only.