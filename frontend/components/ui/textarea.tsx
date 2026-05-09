import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        "min-h-12 w-full resize-none rounded-md border border-border bg-[#0f0c09] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-accent/70 focus:ring-2 focus:ring-accent/20 placeholder:text-muted-foreground",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";

export { Textarea };
