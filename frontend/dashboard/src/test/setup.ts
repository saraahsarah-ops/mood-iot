// Matchers jest-dom (toBeInTheDocument, toHaveTextContent, …) pour Vitest.
import "@testing-library/jest-dom";

// jsdom n'implémente pas ResizeObserver (requis par recharts/ResponsiveContainer).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as any).ResizeObserver = ResizeObserverStub;
