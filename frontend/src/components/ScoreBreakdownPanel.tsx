import type { ScoreBreakdown } from '../types';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

interface Props {
  score: ScoreBreakdown | null;
}

export default function ScoreBreakdownPanel({ score }: Props) {
  if (!score) {
    return (
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl flex items-center justify-center min-h-48">
        <p className="text-gray-500">Score will appear after analysis completes</p>
      </div>
    );
  }

  const { base_score, speed_bonus, efficiency_penalty, final_score } = score;
  const pieData = [
    { name: 'Base Score', value: base_score, color: '#3b82f6' },
    ...(speed_bonus > 0 ? [{ name: 'Speed Bonus', value: speed_bonus, color: '#22c55e' }] : []),
    ...(efficiency_penalty > 0 ? [{ name: 'Penalty', value: efficiency_penalty, color: '#ef4444' }] : []),
  ];

  return (
    <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-xl">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <span>🏆</span> Score Breakdown
      </h2>
      <div className="text-center mb-4">
        <p className="text-6xl font-black text-blue-400">{final_score}</p>
        <p className="text-gray-400 text-sm mt-1">Final Score</p>
      </div>
      <div className="space-y-2 mb-4">
        <div className="flex justify-between items-center">
          <span className="text-gray-300">Base Score</span>
          <span className="text-blue-400 font-semibold">+{base_score}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-300">Speed Bonus {speed_bonus > 0 ? '⚡' : ''}</span>
          <span className={speed_bonus > 0 ? 'text-green-400 font-semibold' : 'text-gray-500'}>
            {speed_bonus > 0 ? `+${speed_bonus}` : '0'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-300">Efficiency Penalty</span>
          <span className={efficiency_penalty > 0 ? 'text-red-400 font-semibold' : 'text-gray-500'}>
            {efficiency_penalty > 0 ? `-${efficiency_penalty}` : '0'}
          </span>
        </div>
        <div className="border-t border-gray-700 pt-2 flex justify-between items-center font-bold">
          <span className="text-white">Total</span>
          <span className="text-blue-400 text-lg">{final_score}</span>
        </div>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={60} dataKey="value" aria-label="Score breakdown chart">
              {pieData.map((entry, idx) => (
                <Cell key={idx} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(value: number, name: string) => [value, name]} contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '8px', color: '#fff' }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
