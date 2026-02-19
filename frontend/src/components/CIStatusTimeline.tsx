import { useState } from 'react';
import type { CIRun } from '../types';

interface Props {
  ciRuns: CIRun[];
  currentIteration: number;
  totalIterations: number;
}

export default function CIStatusTimeline({ ciRuns, currentIteration, totalIterations }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span>🔄</span> CI/CD Timeline
        </h2>
        <span className="text-sm text-gray-400">
          Iteration {currentIteration}/{totalIterations}
        </span>
      </div>
      {/* Progress bar */}
      <div className="mb-6">
        <div className="w-full bg-gray-800 rounded-full h-2">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, (currentIteration / totalIterations) * 100)}%` }}
            role="progressbar"
            aria-valuenow={currentIteration}
            aria-valuemin={0}
            aria-valuemax={totalIterations}
          />
        </div>
      </div>
      {ciRuns.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No CI/CD runs yet</p>
      ) : (
        <div className="relative">
          {/* Horizontal line */}
          <div className="absolute top-5 left-0 right-0 h-0.5 bg-gray-700" aria-hidden="true" />
          <div className="flex gap-4 overflow-x-auto pb-2">
            {ciRuns.map((run, idx) => (
              <div key={idx} className="flex-shrink-0 flex flex-col items-center w-28">
                <button
                  onClick={() => setExpanded(expanded === idx ? null : idx)}
                  className={`z-10 w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 transition-all ${
                    run.status === 'success' ? 'bg-green-900 border-green-500 hover:bg-green-800' :
                    run.status === 'failure' ? 'bg-red-900 border-red-500 hover:bg-red-800' :
                    'bg-yellow-900 border-yellow-500 hover:bg-yellow-800'
                  }`}
                  aria-label={`CI Run ${run.iteration}: ${run.status}`}
                  aria-expanded={expanded === idx}
                >
                  {run.status === 'success' ? '✅' : run.status === 'failure' ? '❌' : '⏳'}
                </button>
                <p className="text-xs text-gray-400 mt-2">Iter {run.iteration}</p>
                <p className="text-xs text-gray-500">{new Date(run.timestamp).toLocaleTimeString()}</p>
              </div>
            ))}
          </div>
          {/* Expanded log */}
          {expanded !== null && ciRuns[expanded]?.logs && (
            <div className="mt-4 bg-gray-800 rounded-lg p-4 max-h-48 overflow-y-auto">
              <h3 className="text-sm font-semibold text-gray-300 mb-2">
                Iteration {ciRuns[expanded].iteration} Logs
              </h3>
              <pre className="text-xs text-gray-400 whitespace-pre-wrap">{ciRuns[expanded].logs}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
