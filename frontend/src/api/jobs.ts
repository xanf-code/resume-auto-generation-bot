import { apiFetch, apiJson } from './client';
import type { CompileResult } from './compile';
import type {
  CreateJobRequest,
  CreateJobResponse,
  JobDetail,
  JobSummary,
  SkillsResponse,
} from './types';

export function createJob(req: CreateJobRequest): Promise<CreateJobResponse> {
  return apiJson<CreateJobResponse>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function listJobs(): Promise<JobSummary[]> {
  const data = await apiJson<{ jobs: JobSummary[] }>('/api/jobs');
  return data.jobs;
}

export function getJob(id: string): Promise<JobDetail> {
  return apiJson<JobDetail>(`/api/jobs/${id}`);
}

export async function getJobLatex(id: string): Promise<string> {
  const data = await apiJson<{ latex: string }>(`/api/jobs/${id}/latex`);
  return data.latex;
}

export function getJobSkills(id: string): Promise<SkillsResponse> {
  return apiJson<SkillsResponse>(`/api/jobs/${id}/skills`);
}

/**
 * Fetch the original job description this run was tailored against. The JD is a
 * pipeline INPUT persisted at submit time, so it resolves for any job status
 * (queued, running, done, failed) - unlike the artifact endpoints.
 */
export function getJobJd(
  id: string,
): Promise<{ jd_name: string; jd_text: string }> {
  return apiJson<{ jd_name: string; jd_text: string }>(`/api/jobs/${id}/jd`);
}

/**
 * Persist edited LaTeX as the job's source of truth: the server recompiles,
 * overwrites the stored PDF, and saves the new LaTeX so the edit survives a
 * reload. Returns the recompiled PDF blob (for the preview) or compile errors.
 * Mirrors {@link compileLatex}'s result shape.
 */
export async function saveJobLatex(
  id: string,
  resumeTex: string,
): Promise<CompileResult> {
  const res = await apiFetch(`/api/jobs/${id}/latex`, {
    method: 'PUT',
    body: JSON.stringify({ resume_tex: resumeTex }),
  });

  if (res.ok) {
    const blob = await res.blob();
    return { ok: true, blob };
  }

  if (res.status === 422) {
    // FastAPI wraps HTTPException detail as { detail: { ok, errors } }; tolerate
    // both the wrapped and bare shapes so error marks always surface.
    const body = (await res.json()) as {
      errors?: string[];
      detail?: { errors?: string[] };
    };
    const errors = body.detail?.errors ?? body.errors ?? ['Compile failed'];
    return { ok: false, errors };
  }

  const text = await res.text();
  return { ok: false, errors: [`Server error ${res.status}: ${text}`] };
}

export async function getJobPdf(id: string): Promise<Blob> {
  // Route through apiFetch (not bare fetch) so VITE_API_BASE_URL is honored on
  // split-host deploys, exactly like every other call in this module.
  const res = await apiFetch(`/api/jobs/${id}/pdf`);
  if (!res.ok) {
    // Without this guard a 404/500 resolves to an HTML error page that would be
    // downloaded (or rendered) as a corrupt "PDF".
    throw new Error(`API ${res.status}`);
  }
  return res.blob();
}

export function renameJob(id: string, label: string): Promise<JobSummary> {
  return apiJson<JobSummary>(`/api/jobs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ label }),
  });
}

export async function deleteJob(id: string): Promise<void> {
  const res = await apiFetch(`/api/jobs/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
}

export async function cancelJob(id: string): Promise<void> {
  const res = await apiFetch(`/api/jobs/${id}/cancel`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
}
