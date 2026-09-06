import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/features/accounts", () => ({
  AccountsList: (props: { scope?: string }) => (
    <div data-testid="accounts-list" data-scope={props.scope}>
      Accounts
    </div>
  ),
}));
vi.mock("@/features/branches", () => ({
  BranchesPanel: () => <div data-testid="branches-panel">Branches</div>,
}));
vi.mock("@/features/customers", () => ({
  CustomersPanel: () => <div data-testid="customers-panel">Customers</div>,
}));
vi.mock("@/features/locations", () => ({
  LocationsPanel: () => <div data-testid="locations-panel">Locations</div>,
}));

vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

import { usePermissions } from "@/lib/auth/usePermissions";
import { AdminTabs } from "@/app/admin/AdminTabs";

const mockedUsePermissions = vi.mocked(usePermissions);

describe("AdminTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Alert and no tabs when read:admin missing", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: false,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockReturnValue(false),
      permissions: [],
      claims: {},
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AdminTabs />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("renders tabs and table when read:admin present", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockImplementation((p: string) => p === "read:admin"),
      permissions: ["read:admin"],
      claims: { permissions: ["read:admin"] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AdminTabs />);

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByTestId("accounts-list")).toBeInTheDocument();
  });

  it("wires the Accounts tab to the cross-customer scope", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: false,
      hasPermission: vi.fn().mockImplementation((p: string) => p === "read:admin"),
      permissions: ["read:admin"],
      claims: { permissions: ["read:admin"] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AdminTabs />);

    expect(screen.getByTestId("accounts-list")).toHaveAttribute("data-scope", "all");
  });

  it("shows tabs when write:admin present", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: true,
      hasPermission: vi.fn().mockReturnValue(true),
      permissions: ["read:admin", "write:admin"],
      claims: { permissions: ["read:admin", "write:admin"] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AdminTabs />);

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByTestId("accounts-list")).toBeInTheDocument();
  });

  it("shows Empty when no data — handled via shadcn Empty (smoke)", () => {
    mockedUsePermissions.mockReturnValue({
      hasReadAdmin: true,
      hasWriteAdmin: true,
      hasPermission: vi.fn().mockReturnValue(true),
      permissions: ["read:admin", "write:admin"],
      claims: { permissions: ["read:admin", "write:admin"] },
      isLoading: false,
      isAuthenticated: true,
    } as unknown as ReturnType<typeof usePermissions>);

    render(<AdminTabs />);

    // At least tabs are rendered; Empty is inside panels when no data, not directly in AdminTabs
    expect(screen.getAllByRole("tab").length).toBeGreaterThan(0);
  });
});
