// vitest setup: jest-dom matchers (toBeInTheDocument, toHaveTextContent, …)
// and a clean DOM between tests.
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom has no matchMedia; default to "not matching" (desktop). A test that
// exercises phone layout replaces window.matchMedia with its own stub.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  });
}

afterEach(cleanup);
