export type BugType = 'LINTING' | 'SYNTAX' | 'LOGIC' | 'TYPE_ERROR' | 'IMPORT' | 'INDENTATION';

export interface FixRecord {
  file: string;
  bug_type: BugType;
  line_number: number | null;
  commit_message: string;
  status: 'fixed' | 'failed';
}

export interface CIRun {
  iteration: number;
  status: string;
  timestamp: string;
  logs: string | null;
}

export interface ScoreBreakdown {
  base_score: number;
  speed_bonus: number;
  efficiency_penalty: number;
  final_score: number;
}

export interface JobProgress {
  current_iteration: number;
  total_iterations: number;
  tests_passing: number;
  tests_failing: number;
}

export interface JobStatus {
  status: 'running' | 'completed' | 'failed';
  progress: JobProgress;
  fixes: FixRecord[];
  ci_runs: CIRun[];
  score: ScoreBreakdown | null;
}

export interface AnalyzeRequest {
  repo_url: string;
  team_name: string;
  team_leader: string;
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
}
