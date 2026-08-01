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

/** A single row in the Postman-style dynamic parameter editor. */
export interface ExtraParamRow {
  key: string;
  value: string;
}

export type ExtraParamValue = string | number | boolean;

export interface ModelRoleConfig {
  model: string;
  effort: string | null;
  /**
   * Postman-style dynamic OpenRouter parameters (temperature, top_k, top_p, ...).
   * Rows may carry blank or duplicate keys mid-edit (e.g. a freshly added "+"
   * row) - serializeExtraParams() cleans them up into the API payload shape.
   */
  extraParams: ExtraParamRow[];
}

export type ModelsConfig = Record<ModelRoleKey, ModelRoleConfig>;

/** Wire-format role shape sent to POST /api/jobs (mirrors ModelRoleDTO). */
export interface ApiModelRole {
  model: string;
  effort: string | null;
  extra_params?: Record<string, ExtraParamValue>;
}

export type ApiModelsConfig = Record<ModelRoleKey, ApiModelRole>;

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

function temperatureRow(value: string): ExtraParamRow[] {
  return [{ key: 'temperature', value }];
}

// Frontend-owned defaults for the New Application UI. Not required to match
// config/settings.py's backend defaults - ModelsDTO is always explicit when sent.
export const DEFAULT_MODELS: ModelsConfig = {
  writer: {
    model: 'anthropic/claude-sonnet-5',
    effort: 'medium',
    extraParams: temperatureRow('0.7'),
  },
  parser: {
    model: 'google/gemini-2.5-flash-lite',
    effort: null,
    extraParams: temperatureRow('0'),
  },
  gap: {
    model: 'z-ai/glm-5.2',
    effort: 'high',
    extraParams: temperatureRow('0.5'),
  },
  skills: {
    model: 'qwen/qwen3-30b-a3b-instruct-2507',
    effort: null,
    extraParams: temperatureRow('0.2'),
  },
  scoring: {
    model: 'deepseek/deepseek-v4-flash',
    effort: 'xhigh',
    extraParams: temperatureRow('0.2'),
  },
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
      writer: { model: 'openai/gpt-4o-mini', effort: null, extraParams: temperatureRow('0') },
      parser: { model: 'openai/gpt-4o-mini', effort: null, extraParams: temperatureRow('0') },
      gap: { model: 'openai/gpt-4o-mini', effort: null, extraParams: temperatureRow('0') },
      skills: { model: 'openai/gpt-4o-mini', effort: null, extraParams: temperatureRow('0') },
      scoring: { model: 'openai/gpt-4o-mini', effort: null, extraParams: temperatureRow('0') },
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
        extraParams: DEFAULT_MODELS.writer.extraParams,
      },
      parser: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        extraParams: DEFAULT_MODELS.parser.extraParams,
      },
      gap: {
        model: 'anthropic/claude-opus-5',
        effort: 'high',
        extraParams: DEFAULT_MODELS.gap.extraParams,
      },
      skills: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        extraParams: DEFAULT_MODELS.skills.extraParams,
      },
      scoring: {
        model: 'openai/gpt-4o-mini',
        effort: null,
        extraParams: DEFAULT_MODELS.scoring.extraParams,
      },
    },
  },
];

/** Coerce a raw editor value into the type OpenRouter should receive. */
function coerceParamValue(raw: string): ExtraParamValue {
  const trimmed = raw.trim();
  if (trimmed === '') return raw;
  const lower = trimmed.toLowerCase();
  if (lower === 'true') return true;
  if (lower === 'false') return false;
  const num = Number(trimmed);
  if (!Number.isNaN(num)) return num;
  return raw;
}

/**
 * Clean a role's dynamic parameter rows into the API payload shape: trims
 * keys, drops blank-key rows, de-duplicates (last row wins), and coerces
 * values to number/boolean/string by content.
 */
export function serializeExtraParams(
  rows: ExtraParamRow[],
): Record<string, ExtraParamValue> {
  const result: Record<string, ExtraParamValue> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    result[key] = coerceParamValue(row.value);
  }
  return result;
}

/** Convert the UI's ModelsConfig into the wire shape POST /api/jobs expects. */
export function toApiModels(models: ModelsConfig): ApiModelsConfig {
  const result = {} as ApiModelsConfig;
  for (const role of MODEL_ROLES) {
    const cfg = models[role];
    const extraParams = serializeExtraParams(cfg.extraParams);
    result[role] = {
      model: cfg.model,
      effort: cfg.effort,
      ...(Object.keys(extraParams).length > 0 ? { extra_params: extraParams } : {}),
    };
  }
  return result;
}

function recordsEqual(
  a: Record<string, ExtraParamValue>,
  b: Record<string, ExtraParamValue>,
): boolean {
  const aKeys = Object.keys(a).sort();
  const bKeys = Object.keys(b).sort();
  if (aKeys.length !== bKeys.length) return false;
  return aKeys.every((k, i) => k === bKeys[i] && Object.is(a[k], b[k]));
}

function extraParamsEqual(a: ExtraParamRow[], b: ExtraParamRow[]): boolean {
  return recordsEqual(serializeExtraParams(a), serializeExtraParams(b));
}

function roleConfigsEqual(a: ModelRoleConfig, b: ModelRoleConfig): boolean {
  return (
    a.model === b.model &&
    a.effort === b.effort &&
    extraParamsEqual(a.extraParams, b.extraParams)
  );
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

/**
 * Defend against untrusted persisted data (localStorage) saved by an older
 * build: pre-extraParams records only had `temperature`, and any parse
 * failure could otherwise hand a role a non-array `extraParams`. Rather than
 * migrating the old `temperature` value, this simply drops it - the boundary
 * only needs to guarantee `extraParams` is always an array so downstream
 * code (serializeExtraParams et al.) never crashes on stale local data.
 */
export function normalizeModelsConfig(value: ModelsConfig): ModelsConfig {
  const result = {} as ModelsConfig;
  for (const role of MODEL_ROLES) {
    const cfg = value[role];
    result[role] = {
      model: cfg.model,
      effort: cfg.effort,
      extraParams: Array.isArray(cfg.extraParams) ? cfg.extraParams : [],
    };
  }
  return result;
}
