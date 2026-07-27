import { describe, it, expect } from 'vitest';
import { toPdfFileName } from '../lib/download';

describe('toPdfFileName', () => {
  it('appends a .pdf extension to a bare base name', () => {
    expect(toPdfFileName('darshan_aswathappa_backend')).toBe(
      'darshan_aswathappa_backend.pdf',
    );
  });

  it('does not double the extension when the base already ends in .pdf', () => {
    expect(toPdfFileName('resume.pdf')).toBe('resume.pdf');
  });

  it('is case-insensitive about an existing extension', () => {
    expect(toPdfFileName('resume.PDF')).toBe('resume.pdf');
  });

  it('trims surrounding whitespace before building the name', () => {
    expect(toPdfFileName('  darshan_aswathappa_  ')).toBe(
      'darshan_aswathappa_.pdf',
    );
  });

  it('leaves the default prefix intact', () => {
    expect(toPdfFileName('darshan_aswathappa_')).toBe('darshan_aswathappa_.pdf');
  });
});
