import { describe, it, expect } from 'vitest';
import {
  BULLET_SHAPES,
  DEFAULT_BULLET_SHAPES,
  toggleShape,
  type BulletShape,
} from '../lib/bulletShapes';

describe('bulletShapes', () => {
  // --- catalog ---

  it('exports exactly four shapes in canonical order', () => {
    const names = BULLET_SHAPES.map((s) => s.name);
    expect(names).toEqual(['PAR', 'RESULT-FIRST', 'ACTION+STACK', 'CONTEXT-PAR']);
  });

  it('each shape has a name, label, and help field', () => {
    for (const shape of BULLET_SHAPES) {
      expect(shape.name).toBeTruthy();
      expect(shape.label).toBeTruthy();
      expect(shape.help).toBeTruthy();
    }
  });

  // --- DEFAULT_BULLET_SHAPES ---

  it('DEFAULT_BULLET_SHAPES is an empty array', () => {
    expect(DEFAULT_BULLET_SHAPES).toEqual([]);
  });

  // --- toggleShape: add ---

  it('adds a shape to an empty list', () => {
    expect(toggleShape([], 'PAR')).toEqual(['PAR']);
  });

  it('adds a shape to a non-empty list', () => {
    const result = toggleShape(['PAR'], 'RESULT-FIRST');
    expect(result).toContain('PAR');
    expect(result).toContain('RESULT-FIRST');
  });

  it('preserves canonical order when adding a shape that comes first', () => {
    // Adding PAR to a list that already has RESULT-FIRST → PAR comes first
    const result = toggleShape(['RESULT-FIRST'], 'PAR');
    expect(result).toEqual(['PAR', 'RESULT-FIRST']);
  });

  it('preserves canonical order when adding a shape that comes later', () => {
    const result = toggleShape(['PAR'], 'ACTION+STACK');
    expect(result).toEqual(['PAR', 'ACTION+STACK']);
  });

  it('preserves canonical order across all four positions', () => {
    const result = toggleShape(['CONTEXT-PAR', 'PAR'], 'RESULT-FIRST' as BulletShape);
    // canonical order: PAR, RESULT-FIRST, ACTION+STACK, CONTEXT-PAR
    expect(result).toEqual(['PAR', 'RESULT-FIRST', 'CONTEXT-PAR']);
  });

  // --- toggleShape: remove ---

  it('removes a shape from a single-item list', () => {
    expect(toggleShape(['PAR'], 'PAR')).toEqual([]);
  });

  it('removes a shape from a multi-item list', () => {
    const result = toggleShape(['PAR', 'RESULT-FIRST'], 'PAR');
    expect(result).toEqual(['RESULT-FIRST']);
  });

  it('removes the correct shape when multiple are present', () => {
    const result = toggleShape(
      ['PAR', 'ACTION+STACK', 'CONTEXT-PAR'],
      'ACTION+STACK',
    );
    expect(result).toEqual(['PAR', 'CONTEXT-PAR']);
  });

  // --- round-trip ---

  it('toggle add then toggle remove returns original list', () => {
    const original: BulletShape[] = ['PAR', 'RESULT-FIRST'];
    const added = toggleShape(original, 'ACTION+STACK');
    const removed = toggleShape(added, 'ACTION+STACK');
    expect(removed).toEqual(original);
  });
});
