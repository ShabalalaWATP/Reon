import { Component, type ErrorInfo, type ReactNode } from "react";

interface RouteErrorBoundaryProps {
  children: ReactNode;
  onReload: () => void;
}

interface RouteErrorBoundaryState {
  failed: boolean;
}

export class RouteErrorBoundary extends Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): RouteErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, information: ErrorInfo) {
    console.error("The active ISTARI view could not be rendered.", error, information);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="page-stack page-stack--narrow">
        <header className="page-heading">
          <div>
            <span>View unavailable</span>
            <h1>This page could not be displayed</h1>
            <p>Your session is still active. Reload the workspace to try the request again.</p>
          </div>
        </header>
        <button className="button button--primary" onClick={this.props.onReload} type="button">
          Reload workspace
        </button>
      </main>
    );
  }
}
