/**
 * Client for the FastAPI gateway.
 *
 * The browser talks to the gateway directly (spec §7): it is already the HTTP
 * boundary, so there is no Route Handler or Server Action in between.
 */
import type { TransferAccepted, TransferRequestBody, TransferStatus } from "./types";

const DEFAULT_GATEWAY = "http://localhost:8000";

export function gatewayOrigin(): string {
  return (process.env.NEXT_PUBLIC_GATEWAY_URL ?? DEFAULT_GATEWAY).replace(/\/+$/, "");
}

/** Turns the gateway's http(s) origin into the matching ws(s) origin. */
export function toWebSocketUrl(origin: string, path: string): string {
  const scheme = origin.startsWith("https://") ? "wss://" : "ws://";
  return `${scheme}${origin.replace(/^https?:\/\//, "")}${path}`;
}

/** Narrows an unknown JSON payload to a status event, since it came off the wire. */
export function parseTransferStatus(payload: unknown): TransferStatus | null {
  if (typeof payload !== "object" || payload === null) return null;
  const candidate = payload as Record<string, unknown>;
  const { request_id: requestId, status } = candidate;
  if (typeof requestId !== "string") return null;
  if (status !== "pending" && status !== "approved" && status !== "declined") return null;
  return {
    request_id: requestId,
    status,
    account_id: typeof candidate.account_id === "string" ? candidate.account_id : undefined,
    reason: typeof candidate.reason === "string" ? candidate.reason : undefined,
    ts: typeof candidate.ts === "string" ? candidate.ts : undefined,
  };
}

export async function requestTransfer(body: TransferRequestBody): Promise<TransferAccepted> {
  const response = await fetch(`${gatewayOrigin()}/transfer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  return (await response.json()) as TransferAccepted;
}

export async function fetchTransferStatus(requestId: string): Promise<TransferStatus> {
  const response = await fetch(
    `${gatewayOrigin()}/transfer/${encodeURIComponent(requestId)}/status`,
  );
  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }
  const parsed = parseTransferStatus(await response.json());
  if (parsed === null) {
    throw new Error("The gateway returned a status this client does not understand.");
  }
  return parsed;
}

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

async function describeFailure(response: Response): Promise<string> {
  if (response.status === 422) {
    return "The gateway rejected those values. Check the accounts and amount.";
  }
  return `The gateway answered ${response.status}. Is it running on ${gatewayOrigin()}?`;
}
