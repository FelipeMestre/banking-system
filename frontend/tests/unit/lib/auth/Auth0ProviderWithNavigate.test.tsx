import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import { Auth0ProviderWithNavigate } from "@/lib/auth/Auth0ProviderWithNavigate";

vi.mock("@auth0/auth0-react", () => ({
  Auth0Provider: vi.fn(({ children }: { children: React.ReactNode }) => <>{children}</>),
  useAuth0: vi.fn(() => ({ getAccessTokenSilently: vi.fn() })),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
}));

const mockedAuth0Provider = vi.mocked(Auth0Provider);
const mockedUseRouter = vi.mocked(useRouter);

describe("Auth0ProviderWithNavigate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseRouter.mockReturnValue({ push: vi.fn() } as unknown as ReturnType<typeof useRouter>);
  });

  it("passes the API audience through authorizationParams", () => {
    render(
      <Auth0ProviderWithNavigate>
        <p>child</p>
      </Auth0ProviderWithNavigate>,
    );

    const props = mockedAuth0Provider.mock.calls[0]![0] as unknown as { authorizationParams?: { audience?: string } };
    expect(props.authorizationParams?.audience).toBeTruthy();
    expect(typeof props.authorizationParams?.audience).toBe("string");
  });
});
