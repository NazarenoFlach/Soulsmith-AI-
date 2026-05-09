import type { ReactNode } from "react";
import { Shield, Sparkles, Sword, Weight } from "lucide-react";

import type { Build } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

type BuildPanelProps = {
  build: Build | null;
};

const statLabels: Array<[keyof Build["stats"], string]> = [
  ["vitality", "VIT"],
  ["attunement", "ATT"],
  ["endurance", "END"],
  ["strength", "STR"],
  ["dexterity", "DEX"],
  ["resistance", "RES"],
  ["intelligence", "INT"],
  ["faith", "FTH"]
];

export function BuildPanel({ build }: BuildPanelProps) {
  if (!build) {
    return (
      <aside className="flex h-full min-h-[320px] flex-col justify-center rounded-md border border-border bg-card/60 p-5 text-center shadow-inner-gold">
        <p className="menu-title text-2xl text-accent">No active build</p>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Ask for a build to start.</p>
      </aside>
    );
  }

  return (
    <aside className="h-full overflow-hidden rounded-md border border-border bg-card/70 shadow-inner-gold">
      <div className="border-b border-border p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase text-muted-foreground">Current Build</p>
            <h2 className="menu-title truncate text-2xl text-accent">{build.archetype}</h2>
          </div>
          <Badge>SL {build.level}</Badge>
        </div>
      </div>

      <div className="scrollbar-thin h-[calc(100%-88px)] overflow-y-auto p-5">
        <section>
          <h3 className="mb-3 text-xs uppercase text-muted-foreground">Stats</h3>
          <div className="grid grid-cols-4 gap-2">
            {statLabels.map(([key, label]) => (
              <div key={key} className="min-h-[58px] rounded-md border border-border bg-[#0d0a08] p-2 text-center">
                <p className="text-[11px] text-muted-foreground">{label}</p>
                <p className="mt-1 text-lg font-semibold text-foreground">{build.stats[key]}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 space-y-3">
          <h3 className="text-xs uppercase text-muted-foreground">Equipment</h3>
          <EquipmentRow icon={<Sword size={16} />} label="Weapon" value={build.equipment.weapon} />
          <EquipmentRow icon={<Shield size={16} />} label="Offhand" value={build.equipment.offhand} />
          <EquipmentRow icon={<Weight size={16} />} label="Armor" value={build.equipment.armor} />
          <EquipmentRow icon={<Sparkles size={16} />} label="Rings" value={build.equipment.rings.join(", ")} />
          {build.equipment.spells.length > 0 ? (
            <EquipmentRow icon={<Sparkles size={16} />} label="Spells" value={build.equipment.spells.join(", ")} />
          ) : null}
        </section>

        <section className="mt-6">
          <h3 className="mb-2 text-xs uppercase text-muted-foreground">Playstyle</h3>
          <p className="text-sm leading-6 text-foreground">{build.playstyle}</p>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{build.upgrade_path}</p>
        </section>

        {build.notes.length > 0 ? (
          <section className="mt-6">
            <h3 className="mb-2 text-xs uppercase text-muted-foreground">Notes</h3>
            <ul className="space-y-2">
              {build.notes.map((note) => (
                <li key={note} className="rounded-md border border-border bg-[#0d0a08] p-3 text-sm leading-6">
                  {note}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </aside>
  );
}

function EquipmentRow({
  icon,
  label,
  value
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="grid min-h-[48px] grid-cols-[24px_76px_1fr] items-center gap-2 rounded-md border border-border bg-[#0d0a08] px-3">
      <span className="text-accent">{icon}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="truncate text-sm text-foreground">{value}</span>
    </div>
  );
}
