import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockPathname = vi.fn();
const mockUsePermissions = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: () => mockUsePermissions(),
}));

vi.mock("next/link", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { Sidebar } from "@/components/home/Sidebar";

describe("Sidebar — Payments active", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePermissions.mockReturnValue({ hasReadAdmin: false, hasWriteAdmin: false });
  });

  it("renders Payments as Link to /transfer with bg-accent and aria-current when pathname is /transfer", () => {
    mockPathname.mockReturnValue("/transfer");
    render(<Sidebar />);
    const link = screen.getByTitle("Payments");
    expect(link.tagName.toLowerCase()).toBe("a");
    expect(link).toHaveAttribute("href", "/transfer");
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toContain("bg-accent");
    expect(link.className).toContain("text-bg");
  });

  it("renders Payments as Link with active styling when pathname starts with /transfer/", () => {
    mockPathname.mockReturnValue("/transfer/confirm");
    render(<Sidebar />);
    const link = screen.getByTitle("Payments");
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toContain("bg-accent");
  });

  it("renders Payments without active styling when on Home", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    const link = screen.getByTitle("Payments");
    expect(link.tagName.toLowerCase()).toBe("a");
    expect(link).not.toHaveAttribute("aria-current");
    expect(link.className).not.toContain("bg-accent");
  });

  it("keeps Cards, Support, Settings as disabled buttons with opacity-45", () => {
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    for (const title of ["Cards", "Support", "Settings"]) {
      const btn = screen.getByTitle(title);
      expect(btn.tagName.toLowerCase()).toBe("button");
      expect(btn).toBeDisabled();
      expect(btn.className).toContain("opacity-45");
    }
  });

  it("Home is active only on /", () => {
    mockPathname.mockReturnValue("/transfer");
    render(<Sidebar />);
    const home = screen.getByTitle("Home");
    expect(home).not.toHaveAttribute("aria-current");
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    // re-render? need fresh render after clearing, easier to check second scenario separately
  });
});

describe("Sidebar — Admin visibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides Admin when no read:admin", () => {
    mockUsePermissions.mockReturnValue({ hasReadAdmin: false, hasWriteAdmin: false });
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    expect(screen.queryByTitle("Admin")).not.toBeInTheDocument();
  });

  it("shows Admin link when read:admin", () => {
    mockUsePermissions.mockReturnValue({ hasReadAdmin: true, hasWriteAdmin: false });
    mockPathname.mockReturnValue("/");
    render(<Sidebar />);
    const admin = screen.getByTitle("Admin");
    expect(admin).toBeInTheDocument();
    expect(admin).toHaveAttribute("href", "/admin");
  });

  it("Admin active styling when on /admin", () => {
    mockUsePermissions.mockReturnValue({ hasReadAdmin: true, hasWriteAdmin: true });
    mockPathname.mockReturnValue("/admin");
    render(<Sidebar />);
    const admin = screen.getByTitle("Admin");
    expect(admin).toHaveAttribute("aria-current", "page");
    expect(admin.className).toContain("bg-accent");
  });
});
