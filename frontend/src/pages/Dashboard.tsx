import { useState, useEffect, useRef, useCallback } from 'react';
import InputSection from '../components/InputSection';
import RunSummaryCard from '../components/RunSummaryCard';
import ScoreBreakdownPanel from '../components/ScoreBreakdownPanel';
import FixesAppliedTable from '../components/FixesAppliedTable';
import { CIStatusTimeline } from '../components/CIStatusTimeline';
import { startAnalysis, getJobStatus, createSSEStream } from '../services/api';
import type { AnalyzeRequest, JobStatus } from '../types';

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repoUrl, setRepoUrl] = useState('');
  const [teamName, setTeamName] = useState('');
  const [teamLeader, setTeamLeader] = useState('');
  const [startTime, setStartTime] = useState<number | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  const connectSSE = useCallback((id: string) => {
    if (sseRef.current) sseRef.current.close();
    const es = createSSEStream(id);
    es.onmessage = (e) => {
      try {
        const data: JobStatus = JSON.parse(e.data);
        setJobStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          es.close();
          setLoading(false);
        }
      } catch (parseErr) {
        console.error('SSE data parse error:', parseErr);
      }
    };
    let pollErrors = 0;
    es.onerror = () => {
      es.close();
      // Fallback to polling with exponential backoff on repeated errors
      const poll = setInterval(async () => {
        try {
          const status = await getJobStatus(id);
          pollErrors = 0;
          setJobStatus(status);
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(poll);
            setLoading(false);
          }
        } catch (pollErr) {
          pollErrors++;
          console.error(`Polling error (attempt ${pollErrors}):`, pollErr);
          if (pollErrors >= 5) {
            clearInterval(poll);
            setError('Lost connection to server. Please refresh and try again.');
            setLoading(false);
          }
        }
      }, 3000);
    };
    sseRef.current = es;
  }, []);

  useEffect(() => () => { sseRef.current?.close(); }, []);

  const handleSubmit = async (req: AnalyzeRequest) => {
    setLoading(true);
    setError(null);
    setJobStatus(null);
    setJobId(null);
    setRepoUrl(req.repo_url);
    setTeamName(req.team_name);
    setTeamLeader(req.team_leader);
    setStartTime(Date.now());
    try {
      const resp = await startAnalysis(req);
      setJobId(resp.job_id);
      connectSSE(resp.job_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start analysis';
      setError(msg);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🤖</span>
            <div>
              <h1 className="text-xl font-bold text-white">Autonomous DevOps Agent</h1>
              <p className="text-xs text-gray-400">AI-powered test failure detection &amp; fixing</p>
            </div>
          </div>
          {jobId && (
            <span className="text-xs text-gray-500 font-mono">Job: {jobId.slice(0, 8)}…</span>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Error */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 text-red-300" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Input */}
        <InputSection onSubmit={handleSubmit} loading={loading} />

        {/* Loading indicator */}
        {loading && (
          <div className="bg-blue-900/20 border border-blue-700 rounded-xl p-4 text-blue-300 flex items-center gap-3">
            <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span>Agent is running… {jobStatus?.progress.current_iteration ? `Iteration ${jobStatus.progress.current_iteration}/${jobStatus.progress.total_iterations}` : 'Starting up…'}</span>
          </div>
        )}

        {/* Summary */}
        {(repoUrl || jobStatus) && (
          <RunSummaryCard
            repoUrl={repoUrl}
            teamName={teamName}
            teamLeader={teamLeader}
            jobStatus={jobStatus}
            startTime={startTime}
          />
        )}

        {/* Score + Fixes */}
        {(jobStatus?.fixes.length || jobStatus?.score) && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <ScoreBreakdownPanel score={jobStatus?.score ?? null} />
            </div>
            <div className="lg:col-span-2">
              <FixesAppliedTable fixes={jobStatus?.fixes ?? []} repoUrl={repoUrl} />
            </div>
          </div>
        )}

        {/* CI Timeline */}
        {jobStatus && (
          <CIStatusTimeline
            runs={jobStatus.ci_runs.map((r, i) => ({
              id: String(i),
              iteration: r.iteration,
              status: (r.status === 'failure' ? 'failed' : r.status) as 'success' | 'failed' | 'running' | 'pending',
              timestamp: new Date(r.timestamp).getTime(),
              logs: r.logs ?? undefined,
            }))}
            currentIteration={jobStatus.progress.current_iteration}
            maxIterations={jobStatus.progress.total_iterations}
          />
        )}
      </main>

      <footer className="text-center text-gray-600 text-xs py-6 mt-8 border-t border-gray-800">
        Autonomous DevOps Agent — AI-powered CI/CD repair system
      </footer>
    </div>
  );
}
