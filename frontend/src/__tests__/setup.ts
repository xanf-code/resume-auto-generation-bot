import '@testing-library/jest-dom';
import { vi } from 'vitest';

// jsdom doesn't implement matchMedia; components that call useMediaQuery need a
// stub. Default to `matches: false` (mobile-first). Tests that care about the
// wide layout mock the useMediaQuery hook directly.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
