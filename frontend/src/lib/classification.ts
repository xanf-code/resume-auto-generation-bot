/** Human-readable label for the JD role/domain tag (e.g. "Backend · Fintech, Healthcare"). */
export function formatClassification(
  role: string | null | undefined,
  domains: string[] | undefined,
): string | null {
  if (!role) return null;
  const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const roleLabel = capitalize(role);
  if (!domains || domains.length === 0) return roleLabel;
  return `${roleLabel} · ${domains.map(capitalize).join(', ')}`;
}
