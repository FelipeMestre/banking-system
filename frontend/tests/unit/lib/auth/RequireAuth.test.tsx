import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/lib/auth/RequireAuth";

vi.mock("@auth0/auth0-react", () => ({
  useAuth0: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
}));

const mockedUseAuth0 = vi.mocked(useAuth0);
const mockedUseRouter = vi.mocked(useRouter);

function mockAuth0State(overrides: Partial<ReturnType<typeof useAuth0>>) {
  mockedUseAuth0.mockReturnValue({
    isLoading: false,
    isAuthenticated: false,
    error: undefined,
    ...overrides,
  } as ReturnType<typeof useAuth0>);
}

describe("RequireAuth", () => {
  const replace = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseRouter.mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
  });

  it("renders a loading message while Auth0 is resolving state", () => {
    mockAuth0State({ isLoading: true });

    render(
      <RequireAuth>
        <p>Protected content</p>
      </RequireAuth>,
    );

    expect(screen.getAllByText("Loading…").length).toBeGreaterThan(0);
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("redirects to /login when the visitor is not authenticated", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: false });

    render(
      <RequireAuth>
        <p>Protected content</p>
      </RequireAuth>,
    );

    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("redirects to /login when Auth0 reports an error, regardless of isAuthenticated", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: true, error: new Error("boom") });

    render(
      <RequireAuth>
        <p>Protected content</p>
      </RequireAuth>,
    );

    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("renders children when the visitor is authenticated and there is no error", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: true, error: undefined });

    render(
      <RequireAuth>
        <p>Protected content</p>
      </RequireAuth>,
    );

    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders nothing while a redirect to /login is in flight", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: false });

    const { container } = render(
      <RequireAuth>
        <p>Protected content</p>
      </RequireAuth>,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
