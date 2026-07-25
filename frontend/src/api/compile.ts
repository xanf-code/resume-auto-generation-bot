import type { CompileErrorResponse } from './types';

export type CompileResult =
  | { ok: true; blob: Blob }
  | { ok: false; errors: string[] };

export async function compileLatex(resumeTex: string): Promise<CompileResult> {
  const res = await fetch('/api/compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_tex: resumeTex }),
  });

  if (res.ok) {
    const blob = await res.blob();
    return { ok: true, blob };
  }

  if (res.status === 422) {
    const data = (await res.json()) as CompileErrorResponse;
    return { ok: false, errors: data.errors };
  }

  const text = await res.text();
  return { ok: false, errors: [`Server error ${res.status}: ${text}`] };
}
