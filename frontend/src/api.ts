import type { AppendMessage, ThreadMessageLike } from "@assistant-ui/react";

export type ContentPart =
  | { type: "text"; text: string }
  | { type: "image_url"; image_url: { url: string } };
export type ApiMessage = {
  role: string;
  content: string | ContentPart[] | null;
  images?: { type: "image_url"; image_url: { url: string } }[] | null;
};
export type Completion = { choices: { message: ApiMessage }[] };
export type Conversation = { conv_id: number; title: string };

export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `Request failed (${response.status}).`);
  }
  return response.json();
}

// Both legacy completion records and current message records can occur in history.
export function toThreadMessage(message: ApiMessage, id: string): ThreadMessageLike {
  const content: ({ type: "text"; text: string } | { type: "image"; image: string })[] = [];
  if (typeof message.content === "string" && message.content) {
    content.push({ type: "text", text: message.content });
  } else if (Array.isArray(message.content)) {
    for (const part of message.content) {
      if (part.type === "text") content.push(part);
      if (part.type === "image_url") content.push({ type: "image", image: part.image_url.url });
    }
  }
  for (const image of message.images ?? []) {
    if (!content.some((part) => part.type === "image" && part.image === image.image_url.url)) {
      content.push({ type: "image", image: image.image_url.url });
    }
  }
  return { id, role: message.role === "user" ? "user" : "assistant", content };
}

export function toApiMessage(message: AppendMessage): ApiMessage {
  const parts = [...message.content, ...(message.attachments ?? []).flatMap((attachment) => attachment.content)];
  const content: ContentPart[] = [];
  for (const part of parts) {
    if (part.type === "text" && part.text.trim()) content.push({ type: "text", text: part.text });
    if (part.type === "image") content.push({ type: "image_url", image_url: { url: part.image } });
  }
  return {
    role: "user",
    content: content.some((part) => part.type === "image_url")
      ? content
      : content.filter((part) => part.type === "text").map((part) => part.text).join("\n"),
  };
}
