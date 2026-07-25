import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SkillCategory } from '../components/detail/skills/SkillCategory';

const writeText = vi.fn().mockResolvedValue(undefined);

describe('SkillCategory', () => {
  beforeEach(() => {
    writeText.mockClear();
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
  });

  it('renders all skills', () => {
    render(
      <SkillCategory
        name="Languages"
        skills={['Python', 'Go', 'TypeScript']}
      />,
    );
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('Go')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
  });

  it('calls clipboard.writeText with comma-joined skills on copy click', () => {
    render(
      <SkillCategory
        name="Languages"
        skills={['Python', 'Go', 'TypeScript']}
      />,
    );
    const copyBtn = screen.getByRole('button', { name: /copy/i });
    fireEvent.click(copyBtn);
    expect(writeText).toHaveBeenCalledWith('Python, Go, TypeScript');
  });

  it('renders the category name', () => {
    render(<SkillCategory name="Languages" skills={['Python']} />);
    expect(screen.getByText('Languages')).toBeInTheDocument();
  });
});
