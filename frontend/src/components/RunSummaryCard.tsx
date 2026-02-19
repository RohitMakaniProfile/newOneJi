import type { JobStatus } from '../types';

interface Props {
  repoUrl: string;
  teamName: string;
  teamLeader: string;
  jobStatus: JobStatus | null;
  startTime: number | null;
}

function formatDuration(ms: number): string {
  const totalSecs = Math.floor(ms / 1000);
  const mins = Math.floor(totalSecs / 60);
  const secs = totalSecs % 60;
  return `${mins}m ${secs}s`;
}

export default function RunSummaryCard({ repoUrl, teamName, teamLeader, jobStatus, startTime }: Props) {
  const branchName = `${teamName}_${teamLeader}_AI_Fix`.replace(/\s+/g, '_');
  const duration = startTime ? formatDuration(Date.now() - startTime) : null;
  const ciStatus = jobStatus?.status;
  const branchUrl = repoUrl ? `${repoUrl}/tree/${branchName}` : null;

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <span>📊</span> Run Summary
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-gray-400">Repository</p>
          <a href={repoUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline break-all">{repoUrl || '—'}</a>
        </div>
        <div>
          <p className="text-gray-400">Branch Created</p>
          {branchUrl ? (
            <a href={branchUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline break-all">{branchName}</a>
          ) : <span className="text-white">{branchName || '—'}</span>}
        </div>
        <div>
          <p className="text-gray-400">Team</p>
          <p className="text-white">{teamName || '—'}</p>
        </div>
        <div>
          <p className="text-gray-400">Team Leader</p>
          <p className="text-white">{teamLeader || '—'}</p>
        </div>
        <div>
          <p className="text-gray-400">Failures Detected</p>
          <p className="text-white">{jobStatus?.progress.tests_failing ?? '—'}</p>
        </div>
        <div>
          <p className="text-gray-400">Fixes Applied</p>
          <p className="text-white">{jobStatus?.fixes.filter(f => f.status === 'fixed').length ?? '—'}</p>
        </div>
        <div>
          <p className="text-gray-400">CI/CD Status</p>
          {ciStatus === 'completed' ? (
            <span className="text-green-400 font-semibold">✅ PASSED</span>
          ) : ciStatus === 'failed' ? (
            <span className="text-red-400 font-semibold">❌ FAILED</span>
          ) : ciStatus === 'running' ? (
            <span className="text-yellow-400 font-semibold">⏳ RUNNING</span>
          ) : <span className="text-gray-500">—</span>}
        </div>
        <div>
          <p className="text-gray-400">Time Taken</p>
          <p className="text-white">{duration || '—'}</p>
        </div>
      </div>
    </div>
  );
}
