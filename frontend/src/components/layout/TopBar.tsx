import { Link, NavLink } from 'react-router-dom';
import { useStore } from '../../store';
import { DESKTOP_MQ, useMediaQuery } from '../../hooks/useMediaQuery';

interface Props {
  /** Show the applications menu (phone/tablet workspace). */
  showNavToggle?: boolean;
}

export function TopBar({ showNavToggle = false }: Props) {
  const openModal = useStore((s) => s.openNewJobModal);
  const toggleMobileNav = useStore((s) => s.toggleMobileNav);
  const mobileNavOpen = useStore((s) => s.mobileNavOpen);
  const isDesktop = useMediaQuery(DESKTOP_MQ);

  return (
    <header
      className="flex items-center justify-between gap-3 px-4 sm:px-6 h-14 sm:h-16 border-b border-rule bg-paper shrink-0"
      style={{
        paddingTop: 'max(0px, env(safe-area-inset-top))',
        paddingLeft: 'max(1rem, env(safe-area-inset-left))',
        paddingRight: 'max(1rem, env(safe-area-inset-right))',
      }}
    >
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {showNavToggle && !isDesktop && (
          <button
            type="button"
            onClick={toggleMobileNav}
            aria-expanded={mobileNavOpen}
            aria-controls="applications-drawer"
            aria-label={mobileNavOpen ? 'Close applications' : 'Open applications'}
            className="inline-flex items-center justify-center min-w-11 min-h-11 -ml-1 text-ink-soft hover:text-ink rounded-[2px] transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
              <path
                d="M3.5 5.5h13M3.5 10h13M3.5 14.5h13"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        )}
        <Link
          to="/"
          className="font-serif text-[20px] sm:text-[22px] font-semibold leading-none tracking-tight text-ink hover:text-accent-deep transition-colors truncate"
          aria-label="Back to home"
        >
          Resume Builder<span className="text-accent">.</span>
        </Link>
        <nav className="hidden sm:flex items-center gap-4 ml-2">
          <NavLink
            to="/ab-testing"
            className={({ isActive }) =>
              `eyebrow hover:text-ink transition-colors ${
                isActive ? 'text-ink border-b-2 border-accent pb-0.5' : ''
              }`
            }
          >
            A/B Testing
          </NavLink>
        </nav>
      </div>

      <div className="flex items-center gap-3 sm:gap-5 shrink-0">
        <NavLink
          to="/ab-testing"
          className={({ isActive }) =>
            `sm:hidden text-[13px] font-medium ${isActive ? 'text-ink' : 'text-ink-soft'}`
          }
        >
          A/B
        </NavLink>
        <button
          onClick={openModal}
          className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-3 sm:px-4 min-h-11 sm:min-h-9 h-11 sm:h-9 rounded-[3px] transition-colors"
        >
          <span className="sm:hidden">＋ New</span>
          <span className="hidden sm:inline">＋ New résumé</span>
        </button>
      </div>
    </header>
  );
}
