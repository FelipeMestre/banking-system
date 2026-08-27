import { gatewayOrigin, toWebSocketUrl } from "@/lib/api/client";
import { parseTransferStatus } from "./parse-transfer-status";
import type { TransferStatus } from "../types";

interface StatusWatcher {
  onStatus: (status: TransferStatus) => void;
  /** The socket closed without ever delivering a verdict. */
  onUnavailable: () => void;
}

/**
 * Watches one transfer over a native WebSocket (spec §7).
 *
 * The gateway sends a single message and closes, so a close is only a problem
 * when nothing arrived first. Returns a cleanup function.
 */
export function watchTransferStatus(requestId: string, watcher: StatusWatcher): () => void {
  const url = toWebSocketUrl(gatewayOrigin(), `/ws/transfer/${encodeURIComponent(requestId)}`);
  let delivered = false;
  let disposed = false;

  const socket = new WebSocket(url);

  socket.onmessage = (event) => {
    const parsed = safeParse(event.data);
    const status = parsed === undefined ? null : parseTransferStatus(parsed);
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
