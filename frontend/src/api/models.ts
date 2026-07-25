import { apiJson } from './client';
import type { CatalogModel } from '../lib/models';

export interface ModelsCatalogResponse {
  models: CatalogModel[];
}

export function listModels(): Promise<ModelsCatalogResponse> {
  return apiJson<ModelsCatalogResponse>('/api/models');
}
