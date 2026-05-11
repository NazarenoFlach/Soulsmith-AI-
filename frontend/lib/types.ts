export type ItemCategory =
  | "weapon"
  | "shield"
  | "armor"
  | "ring"
  | "spell"
  | "tool"
  | "consumable"
  | "key_item"
  | "ember"
  | "upgrade_material"
  | "ammunition"
  | "soul"
  | "multiplayer";

export type ItemSummary = {
  id: string;
  name: string;
  category: ItemCategory;
  weight: number | null;
  image_url: string | null;
  location?: string | null;
  acquisition?: string | null;
  source_url?: string | null;
};

export type Stats = {
  vitality: number;
  attunement: number;
  endurance: number;
  strength: number;
  dexterity: number;
  resistance: number;
  intelligence: number;
  faith: number;
};

export type Equipment = {
  weapon: string;
  offhand: string;
  armor: string;
  rings: string[];
  spells: string[];
};

export type Build = {
  archetype: string;
  level: number;
  stats: Stats;
  equipment: Equipment;
  playstyle: string;
  upgrade_path: string;
  notes: string[];
  relevant_items: ItemSummary[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
