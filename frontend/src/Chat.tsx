import { useEffect, useMemo, useState } from "react";
import {
  AssistantRuntimeProvider, AttachmentPrimitive, ComposerPrimitive,
  MessagePrimitive, ThreadPrimitive, useAuiState, useExternalStoreRuntime,
  type AppendMessage, type ImageMessagePartProps, type TextMessagePartProps,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import Markdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { request, toApiMessage, toThreadMessage, type Completion } from "./api";
import { createImageAttachments } from "./attachments";

function ImagePart({ image }: ImageMessagePartProps) {
  const [failed, setFailed] = useState(false);
  if (failed) return <p role="status">Image could not be loaded.</p>;
  if (!/^(https?:\/\/|data:image\/(png|jpe?g|gif|webp);base64,)/i.test(image)) {
    return <p>Unsupported image URL.</p>;
  }
  return <a href={image} target="_blank" rel="noreferrer"><img className="chat-image" src={image} alt="Chat image" onError={() => setFailed(true)} /></a>;
}

function TextPart({ text }: TextMessagePartProps) {
  return <Markdown remarkPlugins={[remarkGfm]} urlTransform={(url) =>
    /^data:image\/(png|jpe?g|gif|webp);base64,/i.test(url) ? url : defaultUrlTransform(url)
  } components={{
    a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
    img: ({ src, alt }) => <img src={src} alt={alt || "Chat image"} className="chat-image" loading="lazy" />,
  }}>{text}</Markdown>;
}

function UserMessage() {
  return <MessagePrimitive.Root className="message user-message">
    <span className="role">You</span>
    <MessagePrimitive.Parts components={{ Text: TextPart, Image: ImagePart }} />
  </MessagePrimitive.Root>;
}

function AssistantMessage() {
  return <MessagePrimitive.Root className="message">
    <span className="role">Assistant</span>
    <MessagePrimitive.Parts components={{ Text: TextPart, Image: ImagePart }} />
  </MessagePrimitive.Root>;
}

function Attachment() {
  const file = useAuiState((s) => s.attachment.file);
  const status = useAuiState((s) => s.attachment.status);
  const [preview, setPreview] = useState<string>();
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <AttachmentPrimitive.Root className="attachment">
    {preview && <img src={preview} alt="Attachment preview" />}
    <AttachmentPrimitive.Name />
    {status.type === "incomplete" && <span role="alert">Image failed to attach. Remove it and try again.</span>}
    <AttachmentPrimitive.Remove aria-label="Remove image">Remove</AttachmentPrimitive.Remove>
  </AttachmentPrimitive.Root>;
}

export function Chat({ convId, initialMessages, onBusy, onSaved }: {
  convId: number; initialMessages: ThreadMessageLike[];
  onBusy: (busy: boolean) => void; onSaved: () => void;
}) {
  const [messages, setMessages] = useState(initialMessages);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [failed, setFailed] = useState<{ input: AppendMessage; id: string } | null>(null);
  const attachments = useMemo(() => createImageAttachments(setError), []);

  async function send(input: AppendMessage, retryId?: string) {
    const id = retryId ?? crypto.randomUUID();
    const body = toApiMessage(input);
    if (!retryId) setMessages((previous) => [...previous, toThreadMessage(body, id)]);
    setRunning(true);
    onBusy(true);
    setError("");
    try {
      const response = await request<Completion>(`/api/send_chat?conv_id=${convId}`, body);
      if (!response.choices?.length) throw new Error("The model returned no reply.");
      setMessages((previous) => [...previous, toThreadMessage(response.choices[0].message, crypto.randomUUID())]);
      setFailed(null);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send the message.");
      setFailed({ input, id });
    } finally {
      setRunning(false);
      onBusy(false);
    }
  }

  const runtime = useExternalStoreRuntime({
    messages, isRunning: running, isDisabled: running || failed !== null,
    convertMessage: (message) => message,
    onNew: send,
    adapters: { attachments },
  });

  return <AssistantRuntimeProvider runtime={runtime}>
    <ThreadPrimitive.Root className="thread">
      <ThreadPrimitive.Viewport className="transcript" aria-label="Chat messages">
        {messages.length === 0 && <p className="empty">Send a message to start this chat.</p>}
        <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
        {running && <p className="waiting" role="status">Waiting for response…</p>}
        <ThreadPrimitive.ScrollToBottom className="scroll-bottom">Latest message</ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Viewport>
      {error && <div className="error" role="alert">
        <span>{error}</span>
        {failed && <div className="actions">
          <button disabled={running} onClick={() => void send(failed.input, failed.id)}>Retry</button>
          <button disabled={running} onClick={() => {
            setMessages((previous) => previous.filter((message) => message.id !== failed.id));
            setFailed(null); setError("");
          }}>Discard failed message</button>
        </div>}
      </div>}
      <ComposerPrimitive.Root className="composer">
        <ComposerPrimitive.Attachments components={{ Attachment }} />
        <ComposerPrimitive.Input aria-label="Message" placeholder="Write a message…" rows={3} />
        <div className="composer-actions">
          <ComposerPrimitive.AddAttachment>Attach image</ComposerPrimitive.AddAttachment>
          <span className="hint">PNG, JPEG, WebP, GIF · up to 10 MB</span>
          <ComposerPrimitive.Send>Send</ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  </AssistantRuntimeProvider>;
}
