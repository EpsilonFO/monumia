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
    return `Format non autorisé (.${ext || '?'}). Formats acceptés : ${ACCEPTED_EXTENSIONS.join(', ')}.`;
  }
  if (!mimeOk) {
    return `Type MIME non autorisé (${file.type}).`;
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `Fichier trop volumineux (max ${MAX_FILE_SIZE_MB} Mo).`;
  }
  return null;
}
