import { gatewayOrigin, toWebSocketUrl } from "@/lib/api/client";
import { parsePurchaseStatus } from "./parse-purchase-status";
import type { PurchaseStatus } from "../types";

interface StatusWatcher {
  onStatus: (status: PurchaseStatus) => void;
  /** The socket closed without ever delivering a verdict. */
  onUnavailable: () => void;
}

/**
 * Watches one purchase over a native WebSocket (`/ws/purchases/{request_id}`,
 * Credit Cards Phase 2 — mirrors `watchTransferStatus` exactly).
 *
 * The gateway sends a single message and closes, so a close is only a problem
 * when nothing arrived first. Returns a cleanup function.
 */
export function watchPurchaseStatus(requestId: string, watcher: StatusWatcher): () => void {
  const url = toWebSocketUrl(gatewayOrigin(), `/ws/purchases/${encodeURIComponent(requestId)}`);
  let delivered = false;
  let disposed = false;

  const socket = new WebSocket(url);

  socket.onmessage = (event) => {
    const parsed = safeParse(event.data);
    const status = parsed === undefined ? null : parsePurchaseStatus(parsed);
    if (status === null) return;
    delivered = true;
    if (!disposed) watcher.onStatus(status);
  };

  socket.onclose = () => {
    if (!delivered && !disposed) watcher.onUnavailable();
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
