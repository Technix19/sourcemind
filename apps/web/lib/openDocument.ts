import { ApiError, getViewLink } from "./api";

/**
 * Open the original file (at a page, for PDFs) in a new tab.
 *
 * The tab is opened synchronously inside the click, because browsers allow pop-ups only
 * for the click itself; it is pointed at the link once the API has issued it. The link is a
 * short-lived bearer credential, so it is used immediately and never stored or shown.
 */
export async function openDocumentPage(documentId: string, page?: number): Promise<void> {
  const tab = window.open("about:blank", "_blank");
  if (!tab) throw new ApiError(0, "Your browser blocked the new tab. Allow pop-ups for this site and try again.");
  tab.opener = null; // the opened page must not be able to reach back into this one
  try {
    const link = await getViewLink(documentId, page);
    const isPdf = link.filename.toLowerCase().endsWith(".pdf");
    // "#page=N" is read by the browser's PDF viewer only and is never sent to any server.
    tab.location.replace(page && isPdf ? `${link.url}#page=${page}` : link.url);
  } catch (err) {
    tab.close();
    throw err;
  }
}

export function openErrorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Could not open the file.";
}
