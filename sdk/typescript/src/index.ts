export interface HwgErrorOptions {
  code?: string;
  status?: number;
}

export class HwgError extends Error {
  readonly code?: string;
  readonly status?: number;

  constructor(message: string, opts: HwgErrorOptions = {}) {
    super(message);
    this.name = "HwgError";
    this.code = opts.code;
    this.status = opts.status;
  }
}

export interface ErrorEnvelope {
  error?: { code?: string };
}

export interface HwgClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export class HwgClient {
  readonly baseUrl: string;
  readonly timeoutMs: number;
  private readonly apiKey?: string;

  constructor(options: HwgClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:5080").replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 240_000;
    this.apiKey = options.apiKey;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "content-type": "application/json" };
    if (this.apiKey) h.authorization = `Bearer ${this.apiKey}`;
    return h;
  }

  private async send(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      return await fetch(this.baseUrl + path, {
        method,
        headers: this.headers(),
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  }

  private async json<T>(method: string, path: string, body?: unknown): Promise<T> {
    const r = await this.send(method, path, body);
    if (!r.ok) {
      const code = ((await r.json().catch(() => ({}))) as ErrorEnvelope).error?.code;
      throw new HwgError(`${method} ${path} -> ${r.status}`, {
        code,
        status: r.status,
      });
    }
    return (await r.json()) as T;
  }

  async models(): Promise<unknown> {
    const data = await this.json<{ data: unknown }>("GET", "/v1/models");
    return data.data;
  }

  async providers(): Promise<unknown> {
    const data = await this.json<{ providers: unknown }>("GET", "/v1/providers");
    return data.providers;
  }

  async capabilities(): Promise<unknown> {
    return this.json("GET", "/v1/capabilities");
  }

  async chat(
    model: string,
    messages: Array<Record<string, unknown>>,
    extra: Record<string, unknown> = {},
  ): Promise<unknown> {
    return this.json("POST", "/v1/chat/completions", {
      model,
      messages,
      stream: false,
      ...extra,
    });
  }

  async *chatStream(
    model: string,
    messages: Array<Record<string, unknown>>,
    extra: Record<string, unknown> = {},
  ): AsyncGenerator<Record<string, unknown>> {
    const r = await this.send("POST", "/v1/chat/completions", {
      model,
      messages,
      stream: true,
      ...extra,
    });
    if (!r.ok || !r.body) {
      throw new HwgError(`stream -> ${r.status}`, { status: r.status });
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") return;
        yield JSON.parse(data) as Record<string, unknown>;
      }
    }
  }

  async respond(
    model: string,
    userInput: string,
    extra: Record<string, unknown> = {},
  ): Promise<unknown> {
    return this.json("POST", "/v1/responses", {
      model,
      input: userInput,
      ...extra,
    });
  }
}