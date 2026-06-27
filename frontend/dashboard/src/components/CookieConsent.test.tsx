import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import CookieConsent from "@/components/CookieConsent";

describe("CookieConsent", () => {
  beforeEach(() => localStorage.clear());

  it("s'affiche si le consentement n'est pas encore donné", () => {
    render(<CookieConsent />);
    expect(screen.getByText(/Accepter/i)).toBeInTheDocument();
  });

  it("ne s'affiche pas si déjà accepté", () => {
    localStorage.setItem("mood_cookie_consent", "true");
    const { container } = render(<CookieConsent />);
    expect(container.querySelector("button")).toBeNull();
  });
});
