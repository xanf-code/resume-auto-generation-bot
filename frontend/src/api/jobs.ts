import { apiFetch, apiJson } from './client';
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

export async function getJobPdf(id: string): Promise<Blob> {
  const res = await fetch(`/api/jobs/${id}/pdf`);
  if (!res.ok) {
    // Without this guard a 404/500 resolves to an HTML error page that would be
    // downloaded (or rendered) as a corrupt "PDF".
    throw new Error(`API ${res.status}`);
  }
  return res.blob();
}

export function getJobReport(id: string): Promise<unknown> {
  return apiJson(`/api/jobs/${id}/report`);
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
