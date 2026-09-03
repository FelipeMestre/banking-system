import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTransferDraft } from "@/features/transfers/hooks/useTransferDraft";

describe("useTransferDraft selectors", () => {
  it("derived: EUR from, USD hit, amount 10.00 → hasRecipient true warning true canConfirm true", () => {
    const { result } = renderHook(() => useTransferDraft());
    act(() => {
      result.current.setFromId("acc-2");
      result.current.setToNumber("7723490011");
      result.current.setAmount("10.00");
    });
    expect(result.current.hasRecipient).toBe(true);
    expect(result.current.recipient?.account_number).toBe("7723490011");
    expect(result.current.recipientNotFound).toBe(false);
    expect(result.current.showExchangeWarning).toBe(true);
    expect(result.current.canConfirm).toBe(true);
  });

  it("empty amount blocks canConfirm", () => {
    const { result } = renderHook(() => useTransferDraft());
    act(() => {
      result.current.setFromId("acc-1");
      result.current.setToNumber("8800001122");
      result.current.setAmount(" ");
    });
    expect(result.current.hasRecipient).toBe(true);
    expect(result.current.canConfirm).toBe(false);
  });

  it("recipientNotFound when >=6 digits not in directory", () => {
    const { result } = renderHook(() => useTransferDraft());
    act(() => {
      result.current.setToNumber("123456");
    });
    expect(result.current.hasRecipient).toBe(false);
    expect(result.current.recipientNotFound).toBe(true);
    expect(result.current.showExchangeWarning).toBe(false);
  });

  it("no warning when same currency", () => {
    const { result } = renderHook(() => useTransferDraft());
    act(() => {
      result.current.setFromId("acc-1");
      result.current.setToNumber("7723490011");
      result.current.setAmount("5");
    });
    expect(result.current.showExchangeWarning).toBe(false);
  });

  it("hasRecipient false when fewer than 6 digits", () => {
    const { result } = renderHook(() => useTransferDraft());
    act(() => {
      result.current.setToNumber("123");
    });
    expect(result.current.hasRecipient).toBe(false);
    expect(result.current.recipientNotFound).toBe(false);
  });
});
