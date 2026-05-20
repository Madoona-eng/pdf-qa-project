import { Component } from '@angular/core';
import { PdfQaComponent } from './pdf-qa/pdf-qa.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [PdfQaComponent],
  template: `
    <main class="app-shell">
      <app-pdf-qa></app-pdf-qa>
    </main>
  `
})
export class AppComponent {}