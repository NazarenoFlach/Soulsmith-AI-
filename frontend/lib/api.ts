import type { Build, ItemSummary } from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api";

type StreamChatOptions = {
  conversationId: string | null;
  message: string;
  onToken: (token: string) => void;
  onBuild: (build: Build | null) => void;
  onItems: (items: ItemSummary[]) => void;
  onDone: (conversationId: string | null) => void;
};

type ServerEvent = {
  event: string;
  data: unknown;
};

export async function streamChat(options: StreamChatOptions) {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      conversation_id: options.conversationId,
      message: options.message
    })
  });

  if (!response.ok || !response.body) {
    throw new Error("SoulSmith could not reach the backend.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const parsed = parseServerEvent(part);
      if (!parsed) {
        continue;
      }
      handleServerEvent(parsed, options);
    }
  }

  if (buffer.trim()) {
    const parsed = parseServerEvent(buffer);
    if (parsed) {
      handleServerEvent(parsed, options);
    }
  }
}

function parseServerEvent(block: string): ServerEvent | null {
  const lines = block.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));

  if (!eventLine || dataLines.length === 0) {
    return null;
  }

  const event = eventLine.replace("event:", "").trim();
  const data = dataLines.map((line) => line.replace("data:", "").trim()).join("");
  return { event, data: JSON.parse(data) };
}

function handleServerEvent(event: ServerEvent, options: StreamChatOptions) {
  if (event.event === "message.delta") {
    const data = event.data as { token?: string };
    if (data.token) {
      options.onToken(data.token);
    }
    return;
  }

  if (event.event === "build") {
    options.onBuild(event.data as Build | null);
    return;
  }

  if (event.event === "items") {
    options.onItems(event.data as ItemSummary[]);
    return;
  }

  if (event.event === "done") {
    const data = event.data as { conversation_id?: string };
    options.onDone(data.conversation_id ?? null);
  }
}
