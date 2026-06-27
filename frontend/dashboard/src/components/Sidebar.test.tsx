import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("next-auth/react", () => ({
  useSession: () => ({
    data: { user: { name: "Dr Test", role: "psychiatre" } },
    status: "authenticated",
  }),
  signOut: vi.fn(),
  signIn: vi.fn(),
}));

import Sidebar from "@/components/Sidebar";

describe("Sidebar", () => {
  it("affiche les entrées de navigation", () => {
    render(<Sidebar />);
    expect(screen.getByText("Vue generale")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("Teleconsultation")).toBeInTheDocument();
  });
});
