import axios from 'axios';
import type { AnalyzeRequest, AnalyzeResponse, JobStatus } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

export async function startAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const { data } = await api.post<AnalyzeResponse>('/api/devops/analyze', req);
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await api.get<JobStatus>(`/api/devops/status/${jobId}`);
  return data;
}

export function createSSEStream(jobId: string): EventSource {
  return new EventSource(`${BASE_URL}/api/devops/stream/${jobId}`);
}
