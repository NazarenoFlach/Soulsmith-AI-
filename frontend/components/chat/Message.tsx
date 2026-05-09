import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

type MessageProps = {
  message: ChatMessage;
};

export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <article
        className={cn(
          "max-w-[88%] rounded-md border px-4 py-3 text-sm leading-6 md:max-w-[74%]",
          isUser
            ? "border-accent/45 bg-accent/10 text-[#f6edda]"
            : "border-border bg-card/80 text-foreground"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </article>
    </div>
  );
}
