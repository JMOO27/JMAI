import { useCallback, useEffect, useState } from "react";
import type { ThreadMessageLike } from "@assistant-ui/react";
import { Chat } from "./Chat";
import { request, toThreadMessage, type ApiMessage, type Completion, type Conversation } from "./api";

function rememberedChat(): number | null {
  try { return Number(localStorage.getItem("active-chat")) || null; } catch { return null; }
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<number | null>(rememberedChat);
  const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [listError, setListError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [reload, setReload] = useState(0);

  const refreshList = useCallback(async () => {
    try {
      const items = await request<Conversation[]>("/api/conversations");
      setConversations(items); setListError("");
    } catch (cause) { setListError(cause instanceof Error ? cause.message : "Could not load chats."); }
  }, []);
  useEffect(() => { void refreshList(); }, [refreshList]);

  useEffect(() => {
    if (selected === null) { setLoading(false); setMessages([]); setHistoryError(""); return; }
    const controller = new AbortController();
    setLoading(true); setHistoryError("");
    request<(ApiMessage | Completion)[]>(`/api/get_conversation?conv_id=${selected}`, undefined, controller.signal)
      .then((history) => {
        const records = history.flatMap((record) => "choices" in record ? record.choices.map((choice) => choice.message) : [record]);
        setMessages(records.filter((message) => message.role === "user" || message.role === "assistant")
          .map((message, index) => toThreadMessage(message, `${selected}-${index}`)));
        try { localStorage.setItem("active-chat", String(selected)); } catch { /* Storage may be disabled. */ }
      })
      .catch((cause) => { if (!controller.signal.aborted) setHistoryError(cause instanceof Error ? cause.message : "Could not load chat."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selected, reload]);

  async function newChat() {
    setBusy(true); setListError("");
    try {
      const chat = await request<{ conv_id: number }>("/api/create_conversation", {});
      setLoading(true);
      setSelected(chat.conv_id);
      await refreshList();
    } catch (cause) { setListError(cause instanceof Error ? cause.message : "Could not create chat."); }
    finally { setBusy(false); }
  }

  return <main className="app">
    <aside className="sidebar" aria-label="Chat histories">
      <button disabled={busy || loading} onClick={() => void newChat()}>New chat</button>
      <h1>Chat history</h1>
      {listError && <div role="alert" className="error">{listError}<button onClick={() => void refreshList()}>Reload chats</button></div>}
      <nav aria-label="Saved chats">
        {conversations.map((chat) => <button key={chat.conv_id}
          disabled={busy || loading} aria-current={selected === chat.conv_id ? "page" : undefined}
          title={chat.title} onClick={() => {
            if (selected !== chat.conv_id) { setLoading(true); setSelected(chat.conv_id); }
          }}>{chat.title}</button>)}
      </nav>
      {!listError && conversations.length === 0 && <p className="hint">No saved chats.</p>}
    </aside>
    <section className="chat-panel" aria-label="Chat">
      {loading ? <p role="status" className="empty">Loading chat…</p>
        : historyError ? <div className="empty error" role="alert">{historyError}<button onClick={() => setReload((value) => value + 1)}>Retry loading</button></div>
        : selected === null ? <div className="empty"><p>Create a new chat or select one from history.</p><button disabled={busy} onClick={() => void newChat()}>Start a chat</button></div>
        : <Chat key={`${selected}-${reload}`} convId={selected} initialMessages={messages} onBusy={setBusy} onSaved={() => void refreshList()} />}
    </section>
  </main>;
}
