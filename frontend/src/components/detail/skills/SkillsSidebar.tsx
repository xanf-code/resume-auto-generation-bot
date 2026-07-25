import { useEffect, useState } from 'react';
import { SkillCategory } from './SkillCategory';
import { PanelCollapseButton } from '../../layout/PanelCollapseButton';
import { getJobSkills } from '../../../api/jobs';
import type { SkillsResponse } from '../../../api/types';
import { useStore } from '../../../store';
import { WIDE_MQ, useMediaQuery } from '../../../hooks/useMediaQuery';

interface Props {
  jobId: string;
  ready: boolean;
}

function Shell({ children }: { children: React.ReactNode }) {
  const toggleSkills = useStore((s) => s.toggleSkillsSidebar);
  const isWide = useMediaQuery(WIDE_MQ);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-3 py-2.5 border-b border-rule bg-paper shrink-0 flex items-center justify-between gap-2 min-h-11">
        <span className="eyebrow pl-1">Skills</span>
        {isWide && (
          <PanelCollapseButton
            direction="right"
            collapsed={false}
            onToggle={toggleSkills}
            label="Collapse skills"
          />
        )}
      </div>
      {children}
    </div>
  );
}

export function SkillsSidebar({ jobId, ready }: Props) {
  const [skills, setSkills] = useState<SkillsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    let active = true;
    getJobSkills(jobId)
      .then((s) => active && setSkills(s))
      .catch(() => active && setError('No skills were generated for this run.'));
    return () => {
      active = false;
    };
  }, [jobId, ready]);

  if (!ready) {
    return (
      <Shell>
        <div className="flex-1 flex items-center justify-center px-4 text-center">
          <p className="font-serif italic text-[14px] leading-relaxed text-ink-faint">
            Skills will appear here once the resume is ready.
          </p>
        </div>
      </Shell>
    );
  }

  if (error) {
    return (
      <Shell>
        <div className="flex-1 flex items-center justify-center px-4 text-center">
          <p className="font-serif italic text-[14px] leading-relaxed text-ink-faint">
            {error}
          </p>
        </div>
      </Shell>
    );
  }

  if (!skills) {
    return (
      <Shell>
        <div className="p-5 font-serif italic text-[14px] text-ink-faint">
          Loading skills…
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
        <p className="text-[12px] text-ink-soft mb-4 leading-relaxed">
          <span className="font-mono text-ink">{skills.total}</span> skills, ranked
          for this role. Copy each group into the application’s skills field.
        </p>
        <SkillCategory name="Languages & Frameworks" skills={skills.language_and_framework} />
        <SkillCategory name="Infrastructure" skills={skills.infrastructure} />
        <SkillCategory name="Databases" skills={skills.database} />
        <SkillCategory name="AI Tools" skills={skills.ai_tools} />
      </div>
    </Shell>
  );
}
