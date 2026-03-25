import type { GraphData, SkillNode } from './types';
import { DEFAULT_GRAPH_DATA } from './types';

const BASE_URL = 'http://localhost:8000';

export const api = {
  async getSkillTree(): Promise<GraphData> {
    return fetch(`${BASE_URL}/api/skill-tree`)
      .then((res) => res.json() as Promise<GraphData>)
      .catch(() => DEFAULT_GRAPH_DATA);
  },

  async getSkills(): Promise<SkillNode[]> {
    return fetch(`${BASE_URL}/api/skills`)
      .then((res) => res.json() as Promise<SkillNode[]>)
      .catch(() => []);
  },

  async getSkill(id: string): Promise<SkillNode | null> {
    return fetch(`${BASE_URL}/api/skills/${id}`)
      .then((res) => res.json() as Promise<SkillNode>)
      .catch(() => null);
  },

  async getHistory(): Promise<unknown[]> {
    return fetch(`${BASE_URL}/api/history`)
      .then((res) => res.json() as Promise<unknown[]>)
      .catch(() => []);
  },

  async deleteSkill(id: string): Promise<boolean> {
    return fetch(`${BASE_URL}/api/skills/${id}`, { method: 'DELETE' })
      .then((res) => res.ok)
      .catch(() => false);
  },
};
