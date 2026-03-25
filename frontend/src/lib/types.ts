export interface SkillNode {
  id: string;
  name: string;
  category: string;
  is_core: boolean;
  status: string;
  use_count: number;
  created_at: string;
  val: number;
  color: string;
  glow?: boolean;
  description?: string;
  code_content?: string;
  evolution_trigger?: string;
}

export interface GraphData {
  nodes: SkillNode[];
  links: { source: string; target: string }[];
}

export interface AgentEvent {
  event: string;
  status?: AgentStatus;
  message?: string;
  skill_name?: string;
  timestamp?: string;
  passed?: boolean;
  details?: string;
  chunk?: string;
  response?: string;
  node?: SkillNode;
  edge?: { source: string; target: string };
}

export type AgentStatus =
  | 'idle'
  | 'planning'
  | 'executing'
  | 'evolving'
  | 'testing'
  | 'registering'
  | 'responding'
  | 'complete'
  | 'error';

export const STATUS_COLORS: Record<AgentStatus, string> = {
  idle: '#71717a',
  planning: '#f59e0b',
  executing: '#06b6d4',
  evolving: '#8b5cf6',
  testing: '#3b82f6',
  registering: '#10b981',
  responding: '#06b6d4',
  complete: '#10b981',
  error: '#ef4444',
};

export interface TestResult {
  name: string;
  passed: boolean;
  details?: string;
}

export type EvolutionPhase = 'analyzing' | 'writing' | 'testing' | 'registering';
export const EVOLUTION_PHASES: EvolutionPhase[] = ['analyzing', 'writing', 'testing', 'registering'];

export const CATEGORY_COLORS: Record<string, string> = {
  web: '#06b6d4',
  browser: '#8b5cf6',
  file: '#10b981',
  math: '#f59e0b',
  text: '#ec4899',
  data: '#3b82f6',
  api: '#f97316',
  default: '#71717a',
};

export const DEFAULT_GRAPH_DATA: GraphData = {
  nodes: [
    {
      id: 'web_search',
      name: 'Web Search',
      category: 'web',
      is_core: true,
      status: 'active',
      use_count: 0,
      created_at: new Date().toISOString(),
      val: 14,
      color: CATEGORY_COLORS.web,
    },
    {
      id: 'browser',
      name: 'Browser',
      category: 'browser',
      is_core: true,
      status: 'active',
      use_count: 0,
      created_at: new Date().toISOString(),
      val: 14,
      color: CATEGORY_COLORS.browser,
    },
    {
      id: 'file_io',
      name: 'File I/O',
      category: 'file',
      is_core: true,
      status: 'active',
      use_count: 0,
      created_at: new Date().toISOString(),
      val: 14,
      color: CATEGORY_COLORS.file,
    },
    {
      id: 'calculator',
      name: 'Calculator',
      category: 'math',
      is_core: true,
      status: 'active',
      use_count: 0,
      created_at: new Date().toISOString(),
      val: 14,
      color: CATEGORY_COLORS.math,
    },
    {
      id: 'text_analysis',
      name: 'Text Analysis',
      category: 'text',
      is_core: true,
      status: 'active',
      use_count: 0,
      created_at: new Date().toISOString(),
      val: 14,
      color: CATEGORY_COLORS.text,
    },
  ],
  links: [],
};
