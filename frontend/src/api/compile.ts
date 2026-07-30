import { apiFetch } from './client';
import type { CompileErrorResponse } from './types';

export type CompileResult =
  | { ok: true; blob: Blob }
  | { ok: false; errors: string[] };

export async function compileLatex(resumeTex: string): Promise<CompileResult> {
  // Route through apiFetch (not bare fetch) so VITE_API_BASE_URL is honored on
  // split-host deploys. apiFetch already sets the JSON Content-Type header.
  const res = await apiFetch('/api/compile', {
    method: 'POST',
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
