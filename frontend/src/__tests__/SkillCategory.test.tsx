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

  it('calls clipboard.writeText with comma-joined skills on copy click', async () => {
    render(
      <SkillCategory
        name="Languages"
        skills={['Python', 'Go', 'TypeScript']}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /copy/i }));
    expect(await screen.findByText('Copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith('Python, Go, TypeScript');
  });

  it('dedupes repeated skills in both the list and the copied string', async () => {
    render(<SkillCategory name="Languages" skills={['Go', 'Go', 'Python']} />);
    expect(screen.getAllByText('Go')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: /copy/i }));
    expect(await screen.findByText('Copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith('Go, Python');
  });

  it('renders nothing when there are no skills', () => {
    const { container } = render(<SkillCategory name="Languages" skills={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the category name', () => {
    render(<SkillCategory name="Languages" skills={['Python']} />);
    expect(screen.getByText('Languages')).toBeInTheDocument();
  });
});
