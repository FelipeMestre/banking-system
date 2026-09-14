import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

import { usePermissions } from "@/lib/auth/usePermissions";
import { CurrentUserPanel } from "@/app/(dashboard)/admin/CurrentUserPanel";

const mockedUsePermissions = vi.mocked(usePermissions);

function mockPermissions(overrides: Partial<ReturnType<typeof usePermissions>>) {
  mockedUsePermissions.mockReturnValue({
    hasReadAdmin: false,
    hasWriteAdmin: false,
    hasPermission: vi.fn().mockReturnValue(false),
    permissions: [],
    claims: {},
    isLoading: false,
    isAuthenticated: true,
    ...overrides,
  } as unknown as ReturnType<typeof usePermissions>);
}

describe("CurrentUserPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading message while claims resolve", () => {
    mockPermissions({ isLoading: true });

    render(<CurrentUserPanel />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("lists every effective permission as a badge", () => {
    mockPermissions({
      permissions: ["read:admin", "write:admin"],
      claims: { permissions: ["read:admin", "write:admin"], sub: "auth0|abc123" },
    });

    render(<CurrentUserPanel />);

    expect(screen.getByText("read:admin")).toBeInTheDocument();
    expect(screen.getByText("write:admin")).toBeInTheDocument();
    expect(screen.getByText("auth0|abc123")).toBeInTheDocument();
  });

  it("shows a fallback message when the token carries no permissions", () => {
    mockPermissions({ permissions: [], claims: { sub: "auth0|abc123" } });

    render(<CurrentUserPanel />);

    expect(screen.getByText("No permissions on this token.")).toBeInTheDocument();
  });

  it("never renders a roles section — this app has no roles concept", () => {
    mockPermissions({ permissions: ["read:admin"], claims: { permissions: ["read:admin"] } });

    render(<CurrentUserPanel />);

    expect(screen.queryByText(/role/i)).not.toBeInTheDocument();
  });
});
