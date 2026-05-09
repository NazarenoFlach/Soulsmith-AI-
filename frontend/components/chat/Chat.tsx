"use client";

import { FormEvent, useMemo, useState } from "react";
import { Flame, RefreshCcw, Send, Square } from "lucide-react";

import { streamChat } from "@/lib/api";
import type { Build, ChatMessage, ItemSummary } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BuildPanel } from "@/components/chat/BuildPanel";
import { ItemCard } from "@/components/chat/ItemCard";
import { Message } from "@/components/chat/Message";

const starters = ["I want a strength build", "Make it fast roll", "Recommend a lighter weapon"];

export function Chat() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "opening",
      role: "assistant",
      content: "Tell me what kind of build you want to explore."
    }
  ]);
  const [input, setInput] = useState("");
  const [build, setBuild] = useState<Build | null>(null);
  const [items, setItems] = useState<ItemSummary[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const canSubmit = input.trim().length > 0 && !isStreaming;
  const visibleItems = useMemo(() => items.slice(0, 6), [items]);

  async function submitMessage(nextMessage?: string) {
    const content = (nextMessage ?? input).trim();
    if (!content || isStreaming) {
      return;
    }

    const assistantId = crypto.randomUUID();
    setInput("");
    setIsStreaming(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content },
      { id: assistantId, role: "assistant", content: "" }
    ]);

    try {
      await streamChat({
        conversationId,
        message: content,
        onBuild: setBuild,
        onItems: setItems,
        onDone: setConversationId,
        onToken: (token) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, content: `${message.content}${token}` }
                : message
            )
          );
        }
      });
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content:
                  error instanceof Error
                    ? error.message
                    : "SoulSmith could not process the request."
              }
            : message
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage();
  }

  function resetLocalState() {
    setConversationId(null);
    setBuild(null);
    setItems([]);
    setMessages([{ id: crypto.randomUUID(), role: "assistant", content: "Conversation reset. What are we building?" }]);
  }

  return (
    <main className="min-h-screen px-4 py-4 md:px-6 md:py-6">
      <div className="mx-auto grid h-[calc(100vh-2rem)] max-w-7xl grid-cols-1 gap-4 md:h-[calc(100vh-3rem)] lg:grid-cols-[minmax(0,1fr)_390px]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-md border border-border bg-[#0b0907]/86 shadow-inner-gold">
          <header className="flex min-h-[72px] items-center justify-between gap-3 border-b border-border px-4 md:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-accent/40 bg-accent/10 text-accent">
                <Flame size={20} />
              </div>
              <div className="min-w-0">
                <h1 className="menu-title truncate text-2xl text-accent">SoulSmith AI</h1>
                <p className="truncate text-xs text-muted-foreground">Dark Souls 1 Build Generator</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" type="button" onClick={resetLocalState} title="Reset">
              <RefreshCcw size={18} />
            </Button>
          </header>

          <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-5">
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
          </div>

          {visibleItems.length > 0 ? (
            <div className="border-t border-border px-4 py-3 md:px-5">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {visibleItems.map((item) => (
                  <ItemCard key={item.id} item={item} />
                ))}
              </div>
            </div>
          ) : null}

          <form onSubmit={onSubmit} className="border-t border-border p-4 md:p-5">
            <div className="mb-3 flex flex-wrap gap-2">
              {starters.map((starter) => (
                <Button
                  key={starter}
                  variant="outline"
                  size="sm"
                  type="button"
                  disabled={isStreaming}
                  onClick={() => void submitMessage(starter)}
                >
                  {starter}
                </Button>
              ))}
            </div>
            <div className="grid grid-cols-[1fr_44px] gap-3">
              <Textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Strength, dexterity, quality, pyromancy..."
                rows={1}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submitMessage();
                  }
                }}
              />
              <Button size="icon" type="submit" disabled={!canSubmit} title={isStreaming ? "Streaming" : "Send"}>
                {isStreaming ? <Square size={16} /> : <Send size={18} />}
              </Button>
            </div>
          </form>
        </section>

        <BuildPanel build={build} />
      </div>
    </main>
  );
}
