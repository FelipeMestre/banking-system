import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import LoginPage from "@/app/(auth)/login/page";

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
    loginWithRedirect: vi.fn(),
    logout: vi.fn(),
    user: undefined,
    ...overrides,
  } as ReturnType<typeof useAuth0>);
}

describe("LoginPage", () => {
  const replace = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseRouter.mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
  });

  it("does not redirect while Auth0 is still resolving state", () => {
    mockAuth0State({ isLoading: true });

    render(<LoginPage />);

    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to / when the visitor is already authenticated", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: true });

    render(<LoginPage />);

    expect(replace).toHaveBeenCalledWith("/");
  });

  it("renders the login UI without redirecting when unauthenticated", () => {
    mockAuth0State({ isLoading: false, isAuthenticated: false });

    render(<LoginPage />);

    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("Auth0 test")).toBeInTheDocument();
  });
});
