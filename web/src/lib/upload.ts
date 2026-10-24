import { api, ApiError } from "./api";
import type { FileOwner } from "./types";

type Upload = { file_id: string; upload_url: string; method: string; headers: Record<string, string> };

/** Puts a file on a record (PRD F13): the API presigns, the browser sends the bytes straight to
 *  object storage, then the API confirms they arrived. Returns the new file's id. */
export async function uploadFile(table: FileOwner, recordId: string, file: File): Promise<string> {
  const start = await api<Upload>("/files/uploads", {
    method: "POST",
    body: JSON.stringify({
      table_name: table,
      record_id: recordId,
      file_name: file.name,
      content_type: file.type || "application/octet-stream",
      size_bytes: file.size,
    }),
  });
  let put: Response;
  try {
    put = await fetch(start.upload_url, { method: start.method, headers: start.headers, body: file });
  } catch {
    throw new ApiError(0, "storage_unreachable", "The file store could not be reached. Please try again.");
  }
  if (!put.ok) throw new ApiError(put.status, "storage_rejected", `The file store refused the upload (${put.status}).`);
  await api(`/files/${start.file_id}/complete`, { method: "POST" });
  return start.file_id;
}

/** Opens a stored file through a short-lived download link. */
export async function openFile(fileId: string): Promise<void> {
  const { url } = await api<{ url: string }>(`/files/${fileId}/download`);
  window.location.assign(url);
}
