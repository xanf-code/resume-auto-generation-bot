export type BulletShape = 'PAR' | 'RESULT-FIRST' | 'ACTION+STACK' | 'CONTEXT-PAR';

export interface BulletShapeMeta {
  name: BulletShape;
  label: string;
  help: string;
}

export const BULLET_SHAPES: BulletShapeMeta[] = [
  {
    name: 'PAR',
    label: 'PAR',
    help: 'Problem → Action → Result. The workhorse shape.',
  },
  {
    name: 'RESULT-FIRST',
    label: 'Result-first',
    help: "Lead with the number when it's strong enough to open cold.",
  },
  {
    name: 'ACTION+STACK',
    label: 'Action + stack',
    help: 'Verb + tools + outcome. Use when the stack is the point.',
  },
  {
    name: 'CONTEXT-PAR',
    label: 'Context-PAR',
    help: 'Add situation/scope when the scenario needs framing.',
  },
];

export const DEFAULT_BULLET_SHAPES: BulletShape[] = [];

/** Add or remove `name` while preserving canonical order. */
export function toggleShape(list: BulletShape[], name: BulletShape): BulletShape[] {
  if (list.includes(name)) {
    return list.filter((n) => n !== name);
  }
  const canonicalOrder = BULLET_SHAPES.map((s) => s.name);
  return canonicalOrder.filter((n) => list.includes(n) || n === name);
}
