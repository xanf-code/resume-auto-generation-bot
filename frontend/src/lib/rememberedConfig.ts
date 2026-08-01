// "Remember for next run" persistence - New Application modal opt-in.
// Only models (writer/parser/gap/skills/scoring + effort + temperature) and
// tuning (rubric weights/thresholds/iterations) are remembered; bullet shapes
// and the scoring/Obsidian toggles reset to their defaults on every new job.
import { normalizeModelsConfig, type ModelsConfig } from './models';
import type { Tuning } from './tuning';

export const REMEMBERED_CONFIG_STORAGE_KEY = 'resume-desk:remembered-run-config';

export interface RememberedConfig {
  models: ModelsConfig;
  tuning: Tuning;
}

function isRememberedConfig(value: unknown): value is RememberedConfig {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return 'models' in v && 'tuning' in v;
}

/** Returns the last remembered config, or null if none was saved (or it's corrupt). */
export function loadRememberedConfig(): RememberedConfig | null {
  try {
    const raw = localStorage.getItem(REMEMBERED_CONFIG_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isRememberedConfig(parsed)) return null;
    return { ...parsed, models: normalizeModelsConfig(parsed.models) };
  } catch {
    return null;
  }
}

/** Persists the config for the next New Application modal to inherit. */
export function saveRememberedConfig(config: RememberedConfig): void {
  try {
    localStorage.setItem(REMEMBERED_CONFIG_STORAGE_KEY, JSON.stringify(config));
  } catch {
    /* private mode / quota - "remember next run" silently no-ops */
  }
}
