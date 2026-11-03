// Client-side pre-checks for instant feedback only. The API is the authority
// and enforces the real limits again, so these never replace server checks.
export const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;
export const MAX_DOCUMENTS = 12;
export const ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md"];
