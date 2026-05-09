import * as React from "react";

import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-md border border-border bg-muted px-2 text-xs text-muted-foreground",
        className
      )}
      {...props}
    />
  );
}
