import Image from "next/image";

import { API_BASE_URL } from "@/lib/api";
import type { ItemSummary } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

type ItemCardProps = {
  item: ItemSummary;
};

export function ItemCard({ item }: ItemCardProps) {
  const detail = item.acquisition ?? item.location;

  return (
    <Card className="grid min-h-[92px] grid-cols-[72px_1fr] overflow-hidden">
      <Image
        unoptimized
        src={`${API_BASE_URL}/items/${item.id}/image`}
        alt={item.name}
        width={72}
        height={92}
        className="h-full min-h-[92px] w-[72px] object-cover"
      />
      <div className="min-w-0 p-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="truncate text-sm font-medium text-foreground">{item.name}</h3>
          <Badge className="shrink-0 capitalize">{item.category}</Badge>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {item.weight === null ? "No equip load" : `${item.weight.toFixed(1)} weight`}
        </p>
        {detail ? (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{detail}</p>
        ) : null}
      </div>
    </Card>
  );
}
