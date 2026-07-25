import { CopyButton } from './CopyButton';

interface Props {
  name: string;
  skills: string[];
}

export function SkillCategory({ name, skills }: Props) {
  const joined = skills.join(', ');

  if (skills.length === 0) return null;

  return (
    <div className="mb-4 pb-4 border-b border-rule last:border-b-0">
      <div className="flex items-center justify-between mb-2">
        <span className="font-serif text-[14px] text-ink">{name}</span>
        <CopyButton text={joined} />
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <li
            key={skill}
            className="text-[11px] font-mono text-ink-soft bg-paper-raised border border-rule px-2 py-0.5 rounded-[2px]"
          >
            {skill}
          </li>
        ))}
      </ul>
    </div>
  );
}
