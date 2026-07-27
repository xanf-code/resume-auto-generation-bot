/**
 * Normalize a user-entered base name into a safe `.pdf` filename: trim
 * surrounding whitespace and ensure exactly one `.pdf` extension (never
 * doubled, case-insensitive on an existing one).
 */
export function toPdfFileName(base: string): string {
  const trimmed = base.trim();
  const withoutExt = trimmed.replace(/\.pdf$/i, '');
  return `${withoutExt}.pdf`;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
