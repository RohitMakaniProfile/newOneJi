import { useState, useMemo } from 'react';
import type { FixRecord, BugType } from '../types';

interface Props {
  fixes: FixRecord[];
  repoUrl: string;
}

const BUG_TYPE_COLORS: Record<BugType, string> = {
  LINTING: 'bg-yellow-900 text-yellow-300',
  SYNTAX: 'bg-red-900 text-red-300',
  LOGIC: 'bg-purple-900 text-purple-300',
  TYPE_ERROR: 'bg-orange-900 text-orange-300',
  IMPORT: 'bg-blue-900 text-blue-300',
  INDENTATION: 'bg-teal-900 text-teal-300',
};

export default function FixesAppliedTable({ fixes, repoUrl }: Props) {
  const [sortField, setSortField] = useState<keyof FixRecord>('file');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filter, setFilter] = useState('');

  const sorted = useMemo(() => {
    let data = fixes.filter(f =>
      f.file.toLowerCase().includes(filter.toLowerCase()) ||
      f.bug_type.toLowerCase().includes(filter.toLowerCase())
    );
    data = [...data].sort((a, b) => {
      const av = String(a[sortField] ?? '');
      const bv = String(b[sortField] ?? '');
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    return data;
  }, [fixes, sortField, sortDir, filter]);

  const toggleSort = (field: keyof FixRecord) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const SortIcon = ({ field }: { field: keyof FixRecord }) => (
    <span className="ml-1 text-gray-400">{sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span>
  );

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <span>🔧</span> Fixes Applied
          <span className="text-sm font-normal text-gray-400">({fixes.length})</span>
        </h2>
        <input
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter by file or bug type..."
          aria-label="Filter fixes"
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      {fixes.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No fixes applied yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" aria-label="Fixes applied table">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                <th className="text-left py-2 px-3 cursor-pointer hover:text-white" onClick={() => toggleSort('file')}>
                  File <SortIcon field="file" />
                </th>
                <th className="text-left py-2 px-3 cursor-pointer hover:text-white" onClick={() => toggleSort('bug_type')}>
                  Bug Type <SortIcon field="bug_type" />
                </th>
                <th className="text-left py-2 px-3 cursor-pointer hover:text-white" onClick={() => toggleSort('line_number')}>
                  Line <SortIcon field="line_number" />
                </th>
                <th className="text-left py-2 px-3">Commit Message</th>
                <th className="text-left py-2 px-3 cursor-pointer hover:text-white" onClick={() => toggleSort('status')}>
                  Status <SortIcon field="status" />
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((fix, idx) => {
                const lineUrl = fix.line_number && repoUrl
                  ? `${repoUrl}/blob/main/${fix.file}#L${fix.line_number}`
                  : null;
                return (
                  <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800 transition">
                    <td className="py-2 px-3 text-blue-300 font-mono text-xs break-all">{fix.file}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${BUG_TYPE_COLORS[fix.bug_type] || 'bg-gray-700 text-gray-300'}`}>
                        {fix.bug_type}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      {lineUrl ? (
                        <a href={lineUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                          {fix.line_number}
                        </a>
                      ) : <span className="text-gray-500">{fix.line_number ?? '—'}</span>}
                    </td>
                    <td className="py-2 px-3 text-gray-300 max-w-xs">
                      <span title={fix.commit_message} className="block truncate">{fix.commit_message}</span>
                    </td>
                    <td className="py-2 px-3">
                      {fix.status === 'fixed' ? (
                        <span className="text-green-400 font-semibold">✓ Fixed</span>
                      ) : (
                        <span className="text-red-400 font-semibold">✗ Failed</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
