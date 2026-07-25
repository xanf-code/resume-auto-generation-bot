import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  title?: string;
  message?: string;
}

interface State {
  error: Error | null;
}

// A crash in one component should never take down the whole desk. This catches
// render-time throws and offers a way back, styled in the Manuscript system.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Single-user local tool — surface the stack for the owner to debug.
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[240px] text-center px-8 py-12 bg-paper">
        <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
          {this.props.title ?? 'Press jam'}
        </span>
        <h2 className="font-serif text-[26px] leading-tight text-ink mt-2 mb-3">
          {this.props.message ?? 'Something in the workshop broke.'}
        </h2>
        <p className="font-mono text-[12.5px] leading-relaxed text-ink-soft max-w-md break-words">
          {error.message}
        </p>
        <button
          type="button"
          onClick={this.reset}
          className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 h-9 rounded-[3px] transition-colors"
        >
          Try again
        </button>
      </div>
    );
  }
}
