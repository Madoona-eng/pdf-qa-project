import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AskPdfResponse, UploadPdfResponse } from './pdf-qa.models';
import { PdfQaService } from './pdf-qa.service';

@Component({
  selector: 'app-pdf-qa',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pdf-qa.component.html',
  styleUrl: './pdf-qa.component.css'
})
export class PdfQaComponent {
  selectedFile: File | null = null;

  uploadedPdf: UploadPdfResponse | null = null;
  answerResult: AskPdfResponse | null = null;

  question = '';
  topK = 5;

  loadingUpload = false;
  loadingAnswer = false;

  errorMessage = '';

  constructor(private pdfQaService: PdfQaService) {}

  onFileSelected(event: Event): void {
    this.errorMessage = '';
    this.uploadedPdf = null;
    this.answerResult = null;
    this.question = '';

    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) {
      this.selectedFile = null;
      return;
    }

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      this.errorMessage = 'Please select a PDF file only.';
      this.selectedFile = null;
      input.value = '';
      return;
    }

    this.selectedFile = file;
  }

  uploadPdf(): void {
    if (!this.selectedFile) {
      this.errorMessage = 'Please select a PDF file first.';
      return;
    }

    this.errorMessage = '';
    this.loadingUpload = true;
    this.uploadedPdf = null;
    this.answerResult = null;

    this.pdfQaService.uploadPdf(this.selectedFile)
      .pipe(finalize(() => this.loadingUpload = false))
      .subscribe({
        next: (response) => {
          this.uploadedPdf = response;
        },
        error: (error) => {
          this.errorMessage = this.getApiError(error);
        }
      });
  }

  askQuestion(): void {
    if (!this.uploadedPdf?.docId) {
      this.errorMessage = 'Please upload the PDF first.';
      return;
    }

    if (!this.question.trim()) {
      this.errorMessage = 'Please write a question.';
      return;
    }

    this.errorMessage = '';
    this.loadingAnswer = true;
    this.answerResult = null;

    this.pdfQaService.askQuestion({
      docId: this.uploadedPdf.docId,
      question: this.question.trim(),
      topK: this.topK
    })
      .pipe(finalize(() => this.loadingAnswer = false))
      .subscribe({
        next: (response) => {
          this.answerResult = response;
        },
        error: (error) => {
          this.errorMessage = this.getApiError(error);
        }
      });
  }

  private getApiError(error: any): string {
    if (error?.error?.detail) {
      return error.error.detail;
    }

    if (error?.message) {
      return error.message;
    }

    return 'Unexpected error occurred.';
  }
}