// Per-application model selection - mirrors backend ModelsDTO / PipelineModels.
// Keys are snake_case to match the API wire format.

export const MODEL_ROLES = [
  'writer',
  'parser',
  'gap',
  'skills',
  'scoring',
] as const;

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
  writer: { model: 'z-ai/glm-5.2', effort: 'high' },
  parser: { model: 'openai/gpt-4o-mini', effort: null },
  gap: { model: 'anthropic/claude-opus-5', effort: 'medium' },
  skills: { model: 'openai/gpt-4o-mini', effort: null },
  scoring: { model: 'openai/gpt-4o-mini', effort: null },
};

export const ROLE_LABELS: Record<ModelRoleKey, string> = {
  writer: 'Writer',
  parser: 'Parser',
  gap: 'Gap analyzer',
  skills: 'Skills',
  scoring: 'Scoring',
};

/** Named bundles that set every role at once. Balanced mirrors DEFAULT_MODELS. */
export const MODEL_PRESET_IDS = ['fast', 'balanced', 'best'] as const;

export type ModelPresetId = (typeof MODEL_PRESET_IDS)[number];

export interface ModelPreset {
  id: ModelPresetId;
  label: string;
  models: ModelsConfig;
}

export const MODEL_PRESETS: readonly ModelPreset[] = [
  {
    id: 'fast',
    label: 'Fast',
    models: {
      writer: { model: 'openai/gpt-4o-mini', effort: null },
      parser: { model: 'openai/gpt-4o-mini', effort: null },
      gap: { model: 'openai/gpt-4o-mini', effort: null },
      skills: { model: 'openai/gpt-4o-mini', effort: null },
      scoring: { model: 'openai/gpt-4o-mini', effort: null },
    },
  },
  {
    id: 'balanced',
    label: 'Balanced',
    models: DEFAULT_MODELS,
  },
  {
    id: 'best',
    label: 'Best',
    models: {
      writer: { model: 'anthropic/claude-opus-5', effort: 'high' },
      parser: { model: 'openai/gpt-4o-mini', effort: null },
      gap: { model: 'anthropic/claude-opus-5', effort: 'high' },
      skills: { model: 'openai/gpt-4o-mini', effort: null },
      scoring: { model: 'openai/gpt-4o-mini', effort: null },
    },
  },
];

function roleConfigsEqual(a: ModelRoleConfig, b: ModelRoleConfig): boolean {
  return a.model === b.model && a.effort === b.effort;
}

export function modelsEqual(a: ModelsConfig, b: ModelsConfig): boolean {
  return MODEL_ROLES.every((role) => roleConfigsEqual(a[role], b[role]));
}

/** Which preset matches, or `'custom'` when any role differs. */
export function matchPreset(models: ModelsConfig): ModelPresetId | 'custom' {
  for (const preset of MODEL_PRESETS) {
    if (modelsEqual(models, preset.models)) return preset.id;
  }
  return 'custom';
}

export function presetLabel(id: ModelPresetId | 'custom'): string {
  if (id === 'custom') return 'Custom';
  return MODEL_PRESETS.find((p) => p.id === id)?.label ?? 'Custom';
}

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
