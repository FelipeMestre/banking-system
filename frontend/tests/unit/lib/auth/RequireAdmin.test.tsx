import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { RequireAdmin } from "@/lib/auth/RequireAdmin";

vi.mock("@auth0/auth0-react", () => ({
  useAuth0: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
}));

// Mock usePermissions to control read:admin
vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

import { usePermissions } from "@/lib/auth/usePermissions";

const mockedUseAuth0 = vi.mocked(useAuth0);
const mockedUseRouter = vi.mocked(useRouter);
const mockedUsePermissions = vi.mocked(usePermissions);

function mockAuth0(overrides: Partial<ReturnType<typeof useAuth0>>) {
  mockedUseAuth0.mockReturnValue({
    isLoading: false,
    isAuthenticated: false,
    error: undefined,
    getAccessTokenSilently: vi.fn().mockResolvedValue("token"),
    ...overrides,
  } as unknown as ReturnType<typeof useAuth0>);
}

describe("RequireAdmin", () => {
  const replace = vi.fn();
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseRouter.mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: false,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockReturnValue(false),
      permissions: [],
      claims: {},
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);
  });

  it("redirects to /login when not authenticated", () => {
    mockAuth0({ isLoading: false, isAuthenticated: false });
    render(
      <RequireAdmin>
        <p>Admin content</p>
      </RequireAdmin>,
    );
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("renders Alert when authenticated without read:admin", () => {
    mockAuth0({ isLoading: false, isAuthenticated: true });
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: false,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockReturnValue(false),
      permissions: [],
      claims: { permissions: [] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(
      <RequireAdmin>
        <p>Admin content</p>
      </RequireAdmin>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders children when authenticated with read:admin", () => {
    mockAuth0({ isLoading: false, isAuthenticated: true });
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockImplementation((p: string) => p === "read:admin"),
      permissions: ["read:admin"],
      claims: { permissions: ["read:admin"] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(
      <RequireAdmin>
        <p>Admin content</p>
      </RequireAdmin>,
    );

    expect(screen.getByText("Admin content")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows loading while Auth0 is resolving", () => {
    mockAuth0({ isLoading: true });
    render(
      <RequireAdmin>
        <p>Admin content</p>
      </RequireAdmin>,
    );
    expect(screen.getAllByText(/Loading/).length).toBeGreaterThan(0);
  });
});
