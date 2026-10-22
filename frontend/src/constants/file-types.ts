import i18n from '@/i18n';

export const ACCEPTED_EXTENSIONS = [
  'pdf',
  'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif',
  'doc', 'docx', 'odt',
  'xls', 'xlsx', 'ods', 'csv',
  'txt',
] as const;

export const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.oasis.opendocument.text',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.oasis.opendocument.spreadsheet',
  'text/csv',
  'text/plain',
] as const;

export const ACCEPT_ATTR = [
  ...ACCEPTED_EXTENSIONS.map((e) => `.${e}`),
  ...ACCEPTED_MIME_TYPES,
].join(',');

export const MAX_FILE_SIZE_MB = 25;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export function getFileExtension(filename: string): string {
  const idx = filename.lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx + 1).toLowerCase() : '';
}

/** Returns null if valid, or a localized error message. */
export function validateFile(file: File): string | null {
  const ext = getFileExtension(file.name);
  const extOk = (ACCEPTED_EXTENSIONS as readonly string[]).includes(ext);
  const mimeOk = !file.type || (ACCEPTED_MIME_TYPES as readonly string[]).includes(file.type);

  if (!extOk) {
    return i18n.t('constants:fileTypes.formatNonAutorise', {
      extension: ext || '?',
      formats: ACCEPTED_EXTENSIONS.join(', '),
    });
  }
  if (!mimeOk) {
    return i18n.t('constants:fileTypes.mimeNonAutorise', { type: file.type });
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return i18n.t('constants:fileTypes.tropVolumineux', { max: MAX_FILE_SIZE_MB });
  }
  return null;
}
