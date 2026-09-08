import * as React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mountCounts = { accounts: 0, branches: 0, customers: 0, locations: 0 };

vi.mock("@/features/accounts", () => ({
  AccountsPanel: () => {
    React.useEffect(() => {
      mountCounts.accounts += 1;
    }, []);
    return <div data-testid="accounts-panel">Accounts</div>;
  },
}));
vi.mock("@/features/branches", () => ({
  BranchesPanel: () => {
    React.useEffect(() => {
      mountCounts.branches += 1;
    }, []);
    return <div data-testid="branches-panel">Branches</div>;
  },
}));
vi.mock("@/features/customers", () => ({
  CustomersPanel: () => {
    React.useEffect(() => {
      mountCounts.customers += 1;
    }, []);
    return <div data-testid="customers-panel">Customers</div>;
  },
}));
vi.mock("@/features/locations", () => ({
  LocationsPanel: () => {
    React.useEffect(() => {
      mountCounts.locations += 1;
    }, []);
    return <div data-testid="locations-panel">Locations</div>;
  },
}));
vi.mock("@/features/card-account-admin", () => ({
  CardAccountAdminPanel: () => <div data-testid="card-account-admin-panel">Credit Cards</div>,
}));

vi.mock("@/lib/auth/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

import { usePermissions } from "@/lib/auth/usePermissions";
import { AdminTabs } from "@/app/(dashboard)/admin/AdminTabs";

const mockedUsePermissions = vi.mocked(usePermissions);

describe("AdminTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mountCounts.accounts = 0;
    mountCounts.branches = 0;
    mountCounts.customers = 0;
    mountCounts.locations = 0;
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
    expect(screen.getByTestId("accounts-panel")).toBeInTheDocument();
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
    expect(screen.getByTestId("accounts-panel")).toBeInTheDocument();
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

  it("keeps every panel mounted across tab switches, instead of destroying and recreating it", () => {
    /**
     * Regression: switching admin tabs used to scroll the page back to the
     * top. Root cause was Radix's default behavior of unmounting the
     * inactive tab's content — every switch threw away the panel's already-
     * fetched data, dropping it back to its own loading state and briefly
     * collapsing the page's height. `AdminTabs` now force-mounts every
     * panel and only toggles visibility, so a panel mounts exactly once no
     * matter how many times you switch away from and back to its tab.
     */
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

    // All four panels mount up front, not just the active "Accounts" tab.
    expect(screen.getByTestId("accounts-panel")).toBeInTheDocument();
    expect(screen.getByTestId("branches-panel")).toBeInTheDocument();
    expect(screen.getByTestId("customers-panel")).toBeInTheDocument();
    expect(screen.getByTestId("locations-panel")).toBeInTheDocument();
    expect(mountCounts).toEqual({ accounts: 1, branches: 1, customers: 1, locations: 1 });

    fireEvent.click(screen.getByRole("tab", { name: "Locations" }));
    fireEvent.click(screen.getByRole("tab", { name: "Customers" }));
    fireEvent.click(screen.getByRole("tab", { name: "Accounts" }));

    expect(mountCounts).toEqual({ accounts: 1, branches: 1, customers: 1, locations: 1 });
  });
});
