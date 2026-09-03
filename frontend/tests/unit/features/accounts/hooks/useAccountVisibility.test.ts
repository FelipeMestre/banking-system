import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useAccountVisibility } from "@/features/accounts/hooks/useAccountVisibility";

const STORAGE_KEY = "openbank:accounts-visible";

describe("useAccountVisibility", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("defaults to hidden when nothing is stored", async () => {
    const { result } = renderHook(() => useAccountVisibility());
    await waitFor(() => expect(result.current.visible).toBe(false));
  });

  it("toggle reveals and persists true to localStorage", async () => {
    const { result } = renderHook(() => useAccountVisibility());
    await waitFor(() => expect(result.current.visible).toBe(false));

    act(() => {
      result.current.toggle();
    });

    expect(result.current.visible).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("true");
  });

  it("toggling twice hides again and persists false", async () => {
    const { result } = renderHook(() => useAccountVisibility());
    await waitFor(() => expect(result.current.visible).toBe(false));

    act(() => result.current.toggle());
    act(() => result.current.toggle());

    expect(result.current.visible).toBe(false);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("false");
  });

  it("a fresh mount loads the previously persisted value — surviving a logout/login remount", async () => {
    window.localStorage.setItem(STORAGE_KEY, "true");

    const { result } = renderHook(() => useAccountVisibility());

    await waitFor(() => expect(result.current.visible).toBe(true));
  });

  it("survives a full unmount and remount of the hook's consumer", async () => {
    const first = renderHook(() => useAccountVisibility());
    await waitFor(() => expect(first.result.current.visible).toBe(false));
    act(() => first.result.current.toggle());
    expect(first.result.current.visible).toBe(true);
    first.unmount();

    const second = renderHook(() => useAccountVisibility());
    await waitFor(() => expect(second.result.current.visible).toBe(true));
  });
});
