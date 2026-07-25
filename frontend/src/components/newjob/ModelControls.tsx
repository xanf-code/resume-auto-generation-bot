import { useEffect, useId, useState } from 'react';
import { listModels } from '../../api/models';
import {
  MODEL_ROLES,
  ROLE_LABELS,
  effortOptionsFor,
  findCatalogModel,
  type CatalogModel,
  type ModelRoleKey,
  type ModelsConfig,
} from '../../lib/models';

interface Props {
  models: ModelsConfig;
  onChange: (models: ModelsConfig) => void;
}

const selectClass =
  'w-full bg-paper-raised border border-rule text-ink text-[13px] px-2.5 py-2 rounded-[3px] focus:outline-none focus:border-accent/60';

/**
 * Per-role OpenRouter model + conditional reasoning-effort pickers.
 * Fetches the slim catalog from GET /api/models on mount.
 */
export function ModelControls({ models, onChange }: Props) {
  const baseId = useId();
  const [catalog, setCatalog] = useState<CatalogModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listModels()
      .then((res) => {
        if (!cancelled) {
          setCatalog(res.models);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load models');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setRole = (role: ModelRoleKey, modelId: string) => {
    const entry = findCatalogModel(catalog, modelId);
    const options = effortOptionsFor(entry?.reasoning);
    let effort: string | null = null;
    if (options && options.length > 0) {
      const preferred = entry?.reasoning?.default_effort;
      effort =
        preferred && options.includes(preferred) ? preferred : options[0];
    }
    onChange({
      ...models,
      [role]: { model: modelId, effort },
    });
  };

  const setEffort = (role: ModelRoleKey, effort: string) => {
    onChange({
      ...models,
      [role]: { ...models[role], effort },
    });
  };

  return (
    <div className="flex flex-col gap-3">
      <span className="eyebrow">Models</span>
      {loading && (
        <p className="text-[12px] text-ink-faint font-mono">loading catalog…</p>
      )}
      {error && (
        <p className="text-[12px] text-fail border border-fail/30 bg-[#fbeeec] px-2.5 py-1.5 rounded-[3px]">
          {error}
        </p>
      )}
      {!loading && !error && (
        <div className="flex flex-col gap-3.5">
          {MODEL_ROLES.map((role) => {
            const cfg = models[role];
            const entry = findCatalogModel(catalog, cfg.model);
            const efforts = effortOptionsFor(entry?.reasoning);
            const modelId = `${baseId}-${role}-model`;
            const effortId = `${baseId}-${role}-effort`;
            const label = ROLE_LABELS[role];

            // Ensure the current selection appears even if missing from catalog
            // (e.g. defaults before catalog refresh, or stale slug).
            const options = catalog.some((m) => m.id === cfg.model)
              ? catalog
              : [{ id: cfg.model, name: cfg.model, structured_output: true, reasoning: null }, ...catalog];

            return (
              <div key={role} className="flex flex-col gap-1.5">
                <label className="text-[12px] text-ink-soft" htmlFor={modelId}>
                  {label} model
                </label>
                <select
                  id={modelId}
                  aria-label={`${label} model`}
                  className={selectClass}
                  value={cfg.model}
                  onChange={(e) => setRole(role, e.target.value)}
                >
                  {options.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
                {efforts && (
                  <>
                    <label
                      className="text-[12px] text-ink-soft mt-1"
                      htmlFor={effortId}
                    >
                      {label} reasoning
                    </label>
                    <select
                      id={effortId}
                      aria-label={`${label} reasoning`}
                      className={selectClass}
                      value={cfg.effort ?? efforts[0]}
                      onChange={(e) => setEffort(role, e.target.value)}
                    >
                      {efforts.map((e) => (
                        <option key={e} value={e}>
                          {e}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
