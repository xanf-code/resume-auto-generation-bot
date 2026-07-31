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
  /** null omits the parameter entirely (provider default). 0 is meaningful, not "unset". */
  temperature: number | null;
}

export type ModelsConfig = Record<ModelRoleKey, ModelRoleConfig>;

/**
 * Gateway effort values when OpenRouter returns supported_efforts: null.
 * Includes ``none`` (explicitly disables reasoning). Filtered out when
 * ``reasoning.mandatory`` is true — those models reject ``effort: "none"``.
 */
export const GATEWAY_EFFORTS = [
  'none',
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

// Frontend-owned defaults for the New Application UI. Not required to match
// config/settings.py's backend defaults - ModelsDTO is always explicit when sent.
export const DEFAULT_MODELS: ModelsConfig = {
  writer: { model: 'anthropic/claude-sonnet-5', effort: 'medium', temperature: 0.7 },
  parser: { model: 'google/gemini-2.5-flash-lite', effort: null, temperature: 0 },
  gap: { model: 'z-ai/glm-5.2', effort: 'high', temperature: 0.5 },
  skills: { model: 'qwen/qwen3-30b-a3b-instruct-2507', effort: null, temperature: 0.2 },
  scoring: { model: 'deepseek/deepseek-v4-flash', effort: 'xhigh', temperature: 0.2 },
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
      writer: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
      parser: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
      gap: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
      skills: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
      scoring: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
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
      writer: {
        model: 'anthropic/claude-opus-5',
        effort: 'high',
        temperature: DEFAULT_MODELS.writer.temperature,
      },
      parser: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        temperature: DEFAULT_MODELS.parser.temperature,
      },
      gap: {
        model: 'anthropic/claude-opus-5',
        effort: 'high',
        temperature: DEFAULT_MODELS.gap.temperature,
      },
      skills: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        temperature: DEFAULT_MODELS.skills.temperature,
      },
      scoring: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        temperature: DEFAULT_MODELS.scoring.temperature,
      },
    },
  },
];

function roleConfigsEqual(a: ModelRoleConfig, b: ModelRoleConfig): boolean {
  return a.model === b.model && a.effort === b.effort && a.temperature === b.temperature;
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
 * - supported_efforts: null → full gateway set (incl. ``none``)
 * - supported_efforts: list → that list (``none`` only if the catalog listed it)
 * - mandatory → strip ``none`` (model rejects disable)
 */
export function effortOptionsFor(
  reasoning: ModelReasoning | null | undefined,
): string[] | null {
  if (!reasoning) return null;
  if (!('supported_efforts' in reasoning)) return null;

  let options: string[] | null = null;
  if (reasoning.supported_efforts === null) {
    options = [...GATEWAY_EFFORTS];
  } else if (Array.isArray(reasoning.supported_efforts)) {
    options = [...reasoning.supported_efforts];
  }
  if (!options) return null;

  if (reasoning.mandatory) {
    options = options.filter((e) => e !== 'none');
  }
  return options.length > 0 ? options : null;
}

export function findCatalogModel(
  catalog: CatalogModel[],
  modelId: string,
): CatalogModel | undefined {
  return catalog.find((m) => m.id === modelId);
}
