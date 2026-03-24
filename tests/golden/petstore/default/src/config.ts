export function getApiBaseUrl(): string {
  const value = process.env.API_BASE_URL;
  if (!value) {
    throw new Error("API_BASE_URL is required");
  }
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function getBearerToken(): string | undefined {
  return process.env.BEARER_TOKEN ?? process.env.API_TOKEN;
}