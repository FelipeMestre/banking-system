import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { Topbar } from "@/components/home/Topbar";

vi.mock("@auth0/auth0-react", () => ({
  useAuth0: vi.fn(),
}));

const mockedUseAuth0 = vi.mocked(useAuth0);

function mockAuth0(overrides: Partial<ReturnType<typeof useAuth0>>) {
  const logout = vi.fn();
  mockedUseAuth0.mockReturnValue({
    isLoading: false,
    isAuthenticated: true,
    user: { email: "alex@example.com" },
    logout,
    ...overrides,
  } as unknown as ReturnType<typeof useAuth0>);
  return logout;
}

const originalLocation = window.location;

// Radix's DropdownMenu opens on pointerdown, not plain click.
function openAccountMenu() {
  const trigger = screen.getByRole("button", { name: "Account menu" });
  fireEvent.pointerDown(trigger, { button: 0, pointerId: 1 });
  fireEvent.click(trigger);
}

describe("Topbar", () => {
  // jsdom doesn't implement these, which Radix's DropdownMenu relies on for
  // pointer-based open/close and its option-scroll behavior.
  Element.prototype.hasPointerCapture = vi.fn().mockReturnValue(false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, origin: "https://app.openbank.test" },
    });
  });

  it("shows a user icon that opens a menu with the account email and a log out action", () => {
    mockAuth0({});

    render(<Topbar greeting="Good afternoon" lastSignIn="" />);

    openAccountMenu();

    expect(screen.getByText("alex@example.com")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /log out/i })).toBeInTheDocument();
  });

  it("calls Auth0's logout with a returnTo back to the app's own origin when Log out is clicked", () => {
    const logout = mockAuth0({});

    render(<Topbar greeting="Good afternoon" lastSignIn="" />);
    openAccountMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: /log out/i }));

    expect(logout).toHaveBeenCalledWith({
      logoutParams: { returnTo: "https://app.openbank.test" },
    });
  });

  it("renders Log out as a real <button>, not a plain div, so it activates like any other button", () => {
    mockAuth0({});

    render(<Topbar greeting="Good afternoon" lastSignIn="" />);
    openAccountMenu();

    expect(screen.getByRole("menuitem", { name: /log out/i }).tagName).toBe("BUTTON");
  });

  it("focuses the Log out button as soon as the menu opens, so Enter works immediately with no extra ArrowDown", async () => {
    mockAuth0({});

    render(<Topbar greeting="Good afternoon" lastSignIn="" />);
    openAccountMenu();

    await waitFor(() =>
      expect(screen.getByRole("menuitem", { name: /log out/i })).toHaveFocus(),
    );
  });

  it("renders a wider menu with the app's own lighter background, not the default popover surface", () => {
    mockAuth0({});

    render(<Topbar greeting="Good afternoon" lastSignIn="" />);
    openAccountMenu();

    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("w-56");
    expect(menu.className).toContain("bg-bg");
  });
});
