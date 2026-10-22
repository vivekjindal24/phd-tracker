export type Save = (path: string, method: "PUT" | "PATCH", body: unknown) => Promise<void>;
