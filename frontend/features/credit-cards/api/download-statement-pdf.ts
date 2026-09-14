import { ApiError, authorizedFetch, describeFailure, gatewayOrigin } from "@/lib/api/client";

/** `GET /card-accounts/{id}/statements/{statementId}/pdf` — fetches the real
 * rendered PDF as a `Blob`. Kept separate from the browser-triggering side
 * effect (`triggerBrowserDownload`) so the fetch itself stays trivially
 * testable without a DOM. */
export async function fetchStatementPdf(cardAccountId: string, statementId: string): Promise<Blob> {
  const response = await authorizedFetch(
    `${gatewayOrigin()}/card-accounts/${encodeURIComponent(cardAccountId)}/statements/${encodeURIComponent(
      statementId,
    )}/pdf`,
  );
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return response.blob();
}

/** Saves a fetched blob to disk via a throwaway anchor click — the standard
 * browser-only pattern for a client-initiated file download from an
 * in-memory response (no server-rendered `<a href>` exists for this route). */
export function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Convenience wrapper combining the fetch and the save — what every "Download
 * statement" button in this feature actually calls. */
export async function downloadStatementPdf(
  cardAccountId: string,
  statementId: string,
  filename: string,
): Promise<void> {
  const blob = await fetchStatementPdf(cardAccountId, statementId);
  triggerBrowserDownload(blob, filename);
}
