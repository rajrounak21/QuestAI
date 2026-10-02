import { Component } from "react";

// Catches render crashes and shows a themed error instead of a blank page.
// Usage: <ErrorBoundary key={resetKey} onReset={...}><PageContent /></ErrorBoundary>
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("UI crashed:", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      const { fallbackTitle, onReset } = this.props;
      return (
        <div className="app qshop">
          <main className="app-main">
            <div className="no-results premium">
              <p>
                <strong>{fallbackTitle || "Something went wrong showing this page."}</strong>
              </p>
              <p className="ext-text">
                {String(this.state.error?.message || this.state.error).slice(0, 300)}
              </p>
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                {onReset && (
                  <button className="btn-again" onClick={() => { this.setState({ error: null }); onReset(); }}>
                    ↻ Try again
                  </button>
                )}
                <button className="btn-ghost" onClick={() => window.location.reload()}>
                  Reload page
                </button>
              </div>
            </div>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}
