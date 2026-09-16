import { gatewayOrigin, toWebSocketUrl } from "@/lib/api/client";
import { parsePaymentStatus } from "./parse-payment-status";
import type { CardPaymentStatus } from "../types";

interface StatusWatcher {
  onStatus: (status: CardPaymentStatus) => void;
  /** The socket closed without ever delivering a verdict. */
  onUnavailable: () => void;
}

/**
 * Watches one card payment over a native WebSocket (`/ws/payments/{request_id}`,
 * Credit Cards Phase 3 — mirrors `watchTransferStatus`/`watchPurchaseStatus`,
 * extended for a two-stage verdict).
 *
 * The gateway can send up to TWO messages before closing: the authorization
 * verdict (`approved`/`declined`), then — only for an approved payment, and
 * only once `CardMovementConsumer` actually persists it — `settled`. A close
 * is only a problem if it happens before a TERMINAL status (`settled` or
 * `declined`) arrived; closing right after `approved` alone is the expected
 * shape while settlement is still in flight server-side, not a dropped
 * connection. Returns a cleanup function.
 */
export function watchPaymentStatus(requestId: string, watcher: StatusWatcher): () => void {
  const url = toWebSocketUrl(gatewayOrigin(), `/ws/payments/${encodeURIComponent(requestId)}`);
  let lastStatus: CardPaymentStatus["status"] | null = null;
  let disposed = false;

  const socket = new WebSocket(url);

  socket.onmessage = (event) => {
    const parsed = safeParse(event.data);
    const status = parsed === undefined ? null : parsePaymentStatus(parsed);
    if (status === null) return;
    lastStatus = status.status;
    if (!disposed) watcher.onStatus(status);
  };

  socket.onclose = () => {
    const isTerminal = lastStatus === "settled" || lastStatus === "declined";
    if (!isTerminal && !disposed) watcher.onUnavailable();
  };

  // An error is always followed by a close, so let onclose do the reporting.
  socket.onerror = () => {};

  return () => {
    disposed = true;
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      socket.close();
    }
  };
}

function safeParse(data: unknown): unknown {
  if (typeof data !== "string") return undefined;
  try {
    return JSON.parse(data);
  } catch {
    return undefined;
  }
}
