// Per-application model selection - mirrors backend ModelsDTO / PipelineModels.
// Keys are snake_case to match the API wire format.

export const MODEL_ROLES = ['writer', 'parser', 'gap', 'scoring'] as const;

export type ModelRoleKey = (typeof MODEL_ROLES)[number];

export interface ModelRoleConfig {
  model: string;
  effort: string | null;
}

export type ModelsConfig = Record<ModelRoleKey, ModelRoleConfig>;

/** Gateway effort values when OpenRouter returns supported_efforts: null. */
export const GATEWAY_EFFORTS = [
  'minimal',
  'low',
  'medium',
  'high',
  'xhigh',
  'max',
] as const;

export interface ModelReasoning {
  mandatory?: boolean;
  default_effort?: string | null;
  /** list = those values; null = all gateway efforts; omitted = no effort UI */
  supported_efforts?: string[] | null;
}

export interface CatalogModel {
  id: string;
  name: string;
  structured_output: boolean;
  reasoning: ModelReasoning | null;
}

// Defaults sourced from config/settings.py - keep in lockstep with the backend.
export const DEFAULT_MODELS: ModelsConfig = {
  writer: { model: 'anthropic/claude-sonnet-5', effort: 'medium' },
  parser: { model: 'openai/gpt-4o-mini', effort: null },
  gap: { model: 'anthropic/claude-opus-5', effort: 'medium' },
  scoring: { model: 'openai/gpt-4o-mini', effort: null },
};

export const ROLE_LABELS: Record<ModelRoleKey, string> = {
  writer: 'Writer',
  parser: 'Parser',
  gap: 'Gap analyzer',
  scoring: 'Scoring',
};

/**
 * Effort options for a catalog entry, or null when the effort dropdown should hide.
 * - no reasoning → hide
 * - supported_efforts key omitted → hide (reasoning without effort selector)
 * - supported_efforts: null → full gateway set
 * - supported_efforts: list → that list
 */
export function effortOptionsFor(
  reasoning: ModelReasoning | null | undefined,
): string[] | null {
  if (!reasoning) return null;
  if (!('supported_efforts' in reasoning)) return null;
  if (reasoning.supported_efforts === null) return [...GATEWAY_EFFORTS];
  if (Array.isArray(reasoning.supported_efforts)) {
    return reasoning.supported_efforts;
  }
  return null;
}

export function findCatalogModel(
  catalog: CatalogModel[],
  modelId: string,
): CatalogModel | undefined {
  return catalog.find((m) => m.id === modelId);
}
