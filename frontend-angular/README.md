# Frontend - Angular PDF QA

This Angular app allows the user to:

1. Select a PDF file.
2. Upload it to the backend.
3. Ask a question about the uploaded PDF.
4. Display the answer and source context.

## Requirements

- Node.js
- Angular CLI

Install Angular CLI if needed:

```bash
npm install -g @angular/cli
```

## Run Frontend

```bash
cd frontend-angular
npm install
npm start
```

Open:

```text
http://localhost:4200
```

## Backend URL

The API URL is inside:

```text
src/app/pdf-qa/pdf-qa.service.ts
```

Current value:

```ts
private readonly apiUrl = 'http://127.0.0.1:8000/api/pdf';
```