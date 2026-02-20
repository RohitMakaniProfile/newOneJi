import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, Loader, ExternalLink } from 'lucide-react';
import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface CIRun {
  id: string;
  iteration: number;
  status: 'success' | 'failed' | 'running' | 'pending';
  timestamp: number;
  duration?: number;
  url?: string;
  logs?: string;
}

interface CIStatusTimelineProps {
  runs?: CIRun[];
  currentIteration?: number;
  maxIterations?: number;
}

export const CIStatusTimeline = ({ runs = [], currentIteration = 1, maxIterations = 5 }: CIStatusTimelineProps) => {
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  return (
    <motion.div className="mt-8 rounded-3xl bg-white shadow-2xl p-8" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">CI/CD Pipeline Timeline</h3>
          <p className="text-gray-600 mt-1">Iteration {currentIteration} of {maxIterations}</p>
        </div>
        <div className="px-4 py-2 bg-blue-50 rounded-full">
          <span className="text-sm font-semibold text-blue-700">{Math.round((currentIteration / maxIterations) * 100)}% Complete</span>
        </div>
      </div>
      <div className="relative py-12">
        <div className="absolute top-1/2 left-0 right-0 h-1 bg-gray-200 transform -translate-y-1/2" />
        <motion.div className="absolute top-1/2 left-0 h-1 bg-gradient-to-r from-blue-500 to-green-500 transform -translate-y-1/2" initial={{ width: '0%' }} animate={{ width: `${(currentIteration / maxIterations) * 100}%` }} />
        <div className="relative flex justify-between">
          {Array.from({ length: maxIterations }).map((_, i) => {
            const run = runs.find(r => r.iteration === i + 1);
            return <TimelineNode key={i} iteration={i + 1} status={run?.status || 'pending'} run={run} onToggle={() => run && setExpandedRun(expandedRun === run.id ? null : run.id)} />;
          })}
        </div>
      </div>
      <AnimatePresence>{expandedRun && <ExpandedRunDetails run={runs.find(r => r.id === expandedRun)!} onClose={() => setExpandedRun(null)} />}</AnimatePresence>
    </motion.div>
  );
};

const TimelineNode = ({ iteration, status, run, onToggle }: any) => (
  <div className="flex flex-col items-center">
    <motion.button className={`w-14 h-14 rounded-full flex items-center justify-center shadow-lg ${status === 'success' ? 'bg-green-500' : status === 'failed' ? 'bg-red-500' : status === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} initial={{ scale: 0 }} animate={{ scale: 1 }} whileHover={run ? { scale: 1.1 } : {}} onClick={run ? onToggle : undefined}>
      {status === 'success' ? <CheckCircle className="w-6 h-6 text-white" /> : status === 'failed' ? <XCircle className="w-6 h-6 text-white" /> : status === 'running' ? <Loader className="w-6 h-6 text-white animate-spin" /> : <span className="text-white font-bold">{iteration}</span>}
    </motion.button>
    <p className="mt-4 text-sm font-semibold">Run {iteration}</p>
    {run && <p className="text-xs text-gray-500">{formatDistanceToNow(run.timestamp, { addSuffix: true })}</p>}
  </div>
);

const StatusBadge = ({ status }: { status: string }) => {
  const styles: any = { success: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700', running: 'bg-blue-100 text-blue-700' };
  return <span className={`px-2 py-1 rounded-full text-xs font-semibold ${styles[status]}`}>{status === 'success' ? 'Passed' : status === 'failed' ? 'Failed' : 'Running'}</span>;
};

const ExpandedRunDetails = ({ run, onClose }: any) => (
  <motion.div className="mt-6 rounded-2xl bg-gray-50 p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <div className="flex justify-between mb-4">
      <h4 className="text-lg font-bold">Run {run.iteration} Details</h4>
      <button onClick={onClose}>✕</button>
    </div>
    <div className="space-y-3">
      <div className="flex gap-2"><span className="text-sm font-medium">Status:</span><StatusBadge status={run.status} /></div>
      {run.url && <a href={run.url} target="_blank" className="text-blue-600 text-sm flex items-center gap-2">View on GitHub <ExternalLink className="w-4 h-4" /></a>}
      {run.logs && <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-xs overflow-auto max-h-64">{run.logs}</pre>}
    </div>
  </motion.div>
);
