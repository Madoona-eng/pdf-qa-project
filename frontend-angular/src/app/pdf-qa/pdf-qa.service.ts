import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AskPdfRequest, AskPdfResponse, UploadPdfResponse } from './pdf-qa.models';

@Injectable({
  providedIn: 'root'
})
export class PdfQaService {
 private readonly apiUrl = 'https://madoona-eng-pdf-qa-backend.hf.space/api/pdf';

  constructor(private http: HttpClient) {}

  uploadPdf(file: File): Observable<UploadPdfResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<UploadPdfResponse>(
      `${this.apiUrl}/upload`,
      formData
    );
  }

  askQuestion(request: AskPdfRequest): Observable<AskPdfResponse> {
    return this.http.post<AskPdfResponse>(
      `${this.apiUrl}/ask`,
      request
    );
  }
}