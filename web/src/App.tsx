import { FormEvent, useEffect, useRef, useState } from "react";
import type { ChatMessage, ChatResponse, ReviewResult, ThesisCard } from "./types";

async function postChat(message: string, history: ChatMessage[]): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function VerdictBadge({ verdict }: { verdict: string }) {
  return <span className={`verdict verdict-${verdict}`}>{verdict}</span>;
}

function ReviewPanel({ review }: { review: ReviewResult }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>原则审查</h2>
        <VerdictBadge verdict={review.overall} />
      </header>
      <p className="muted">
        {review.name || review.symbol} · {review.symbol}
      </p>
      <p className="summary">{review.summary}</p>
      <ul className="review-list">
        {review.items.map((item) => (
          <li key={item.principle_id}>
            <div className="review-item-head">
              <strong>{item.principle_id}</strong>
              <VerdictBadge verdict={item.verdict} />
            </div>
            <p>{item.rationale}</p>
            {item.missing_info.length > 0 && (
              <p className="missing">缺：{item.missing_info.join("、")}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ThesisPanel({ thesis }: { thesis: ThesisCard }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>论点卡</h2>
        <span className="tag">{thesis.symbol}</span>
      </header>
      <p className="thesis-body">{thesis.thesis}</p>
      {thesis.open_questions.length > 0 && (
        <>
          <h3>待澄清</h3>
          <ul>
            {thesis.open_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </>
      )}
      {thesis.todos.length > 0 && (
        <>
          <h3>待办</h3>
          <ul>
            {thesis.todos.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "我是你的价值投资导师空壳。可以聊仓位与原则，或说「看看茅台」走证据审查。人做决策。",
      mode: "broad",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [thesis, setThesis] = useState<ThesisCard | null>(null);
  const [lastMode, setLastMode] = useState<"broad" | "company">("broad");
  const [toolCalls, setToolCalls] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    const nextHistory = [...messages, { role: "user" as const, content: text }];
    setMessages(nextHistory);
    setBusy(true);
    try {
      const resp = await postChat(text, messages);
      setLastMode(resp.mode);
      setToolCalls(resp.tool_calls);
      if (resp.review) setReview(resp.review);
      if (resp.thesis) setThesis(resp.thesis);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: resp.reply, mode: resp.mode },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <header className="top">
        <div>
          <p className="brand">my_buffett</p>
          <p className="tagline">原则导师 · 证据审查</p>
        </div>
        <div className="meta">
          <span className={`mode mode-${lastMode}`}>{lastMode}</span>
          {toolCalls.length > 0 && (
            <span className="tools">tools: {toolCalls.join(", ")}</span>
          )}
        </div>
      </header>

      <main className="workbench">
        <section className="chat">
          <div className="transcript">
            {messages.map((m, i) => (
              <article key={i} className={`bubble ${m.role}`}>
                <header>
                  {m.role === "user" ? "你" : "导师"}
                  {m.mode && <span className="mode-inline">{m.mode}</span>}
                </header>
                <pre>{m.content}</pre>
              </article>
            ))}
            {busy && <p className="muted thinking">思考中…</p>}
            <div ref={bottomRef} />
          </div>
          <form className="composer" onSubmit={onSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="例如：我该怎么看仓位？ / 看看茅台"
              disabled={busy}
              autoFocus
            />
            <button type="submit" disabled={busy || !input.trim()}>
              发送
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>

        <aside className="side">
          {review ? <ReviewPanel review={review} /> : (
            <section className="panel empty">
              <h2>原则审查</h2>
              <p className="muted">具体公司路径才会出现结构化审查。</p>
            </section>
          )}
          {thesis ? <ThesisPanel thesis={thesis} /> : (
            <section className="panel empty">
              <h2>论点卡</h2>
              <p className="muted">审查后在此沉淀，不是流水账笔记。</p>
            </section>
          )}
        </aside>
      </main>
    </div>
  );
}
