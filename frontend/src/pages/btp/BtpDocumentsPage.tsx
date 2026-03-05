import { DocumentsPage } from '@/pages/documents/DocumentsPage';

// For BTP users, the documents page is the same as for owners
// but scoped to their own documents (templates, devis, contrats)
export function BtpDocumentsPage() {
  return <DocumentsPage />;
}
