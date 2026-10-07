export type Run = { id: string; state: string; [key:string]: unknown };
export type ClientOptions = { baseUrl: string; apiKey: string; timeoutMs?: number };

export class JarvisClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  constructor(options: ClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? 30_000;
  }
  private async request<T>(path:string, init:RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(this.baseUrl + path, {
        ...init,
        signal: controller.signal,
        headers: {"Authorization": `Bearer ${this.apiKey}`, "Content-Type":"application/json", ...(init.headers ?? {})}
      });
      const text = await response.text();
      const body = text ? JSON.parse(text) : null;
      if (!response.ok) throw new Error(`Jarvis API ${response.status}: ${text}`);
      return body as T;
    } finally { clearTimeout(timer); }
  }
  health(): Promise<Record<string,unknown>> { return this.request("/health"); }
  capabilities(): Promise<Record<string,unknown>> { return this.request("/engineering/capabilities"); }
  run(task:string, options:Record<string,unknown> = {}): Promise<Run> {
    return this.request("/engineering/runs", {method:"POST", body:JSON.stringify({task,...options})});
  }
  cancel(id:string): Promise<Run> {
    return this.request(`/engineering/runs/${encodeURIComponent(id)}/cancel`, {method:"POST"});
  }
}
