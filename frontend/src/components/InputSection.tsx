import { useState, type FormEvent } from 'react';
import type { AnalyzeRequest } from '../types';

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  loading: boolean;
}

export default function InputSection({ onSubmit, loading }: Props) {
  const [repoUrl, setRepoUrl] = useState('');
  const [teamName, setTeamName] = useState('');
  const [teamLeader, setTeamLeader] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!repoUrl.trim()) errs.repoUrl = 'Repository URL is required';
    else {
      try {
        const parsed = new URL(repoUrl.trim());
        if (parsed.hostname !== 'github.com' && !parsed.hostname.endsWith('.github.com')) {
          errs.repoUrl = 'Must be a GitHub repository URL';
        }
      } catch {
        errs.repoUrl = 'Must be a valid URL';
      }
    }
    if (!teamName.trim()) errs.teamName = 'Team name is required';
    if (!teamLeader.trim()) errs.teamLeader = 'Team leader name is required';
    return errs;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setErrors({});
    onSubmit({ repo_url: repoUrl.trim(), team_name: teamName.trim(), team_leader: teamLeader.trim() });
  };

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <span className="text-2xl">🤖</span> Configure Analysis
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="repo-url">
            GitHub Repository URL
          </label>
          <input
            id="repo-url"
            type="url"
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            aria-label="GitHub Repository URL"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
          />
          {errors.repoUrl && <p className="text-red-400 text-xs mt-1" role="alert">{errors.repoUrl}</p>}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="team-name">
              Team Name
            </label>
            <input
              id="team-name"
              type="text"
              value={teamName}
              onChange={e => setTeamName(e.target.value)}
              placeholder="e.g. RIFT ORGANISERS"
              aria-label="Team Name"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
            {errors.teamName && <p className="text-red-400 text-xs mt-1" role="alert">{errors.teamName}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1" htmlFor="team-leader">
              Team Leader Name
            </label>
            <input
              id="team-leader"
              type="text"
              value={teamLeader}
              onChange={e => setTeamLeader(e.target.value)}
              placeholder="e.g. Saiyam Kumar"
              aria-label="Team Leader Name"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
            {errors.teamLeader && <p className="text-red-400 text-xs mt-1" role="alert">{errors.teamLeader}</p>}
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 flex items-center justify-center gap-2"
          aria-busy={loading}
        >
          {loading ? (
            <>
              <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Running Analysis...
            </>
          ) : '🚀 Run Agent'}
        </button>
      </form>
    </div>
  );
}
