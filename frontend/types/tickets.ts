// types/tickets.ts

// Osnovni tipovi iz tickets.json feed-a
export type Leg = {
  fixture_id: number;
  league_id: number;
  league_name: string;
  league_country: string;
  home: string;
  away: string;
  kickoff: string;       // ISO datetime string
  market: string;        // "O25", "U35", ...
  market_family: string; // "GOALS", "HT", ...
  pick: string;          // "Over 2.5 Goals"
  odds: number;
};

export type Ticket = {
  ticket_id: string;     // npr. "SET_GOALS_MIX-1"
  label: string;         // "[GOALS MIX]"
  total_odds: number;
  legs: Leg[];
  score: number;         // AI score 0–100
};

export type TicketSet = {
  code: string;          // "SET_GOALS_MIX"
  label: string;         // "[GOALS MIX]"
  status: string;
  requested_max_tickets: number;
  effective_max_tickets: number;
  tickets: Ticket[];
};

export type TicketsFeed = {
  date: string;
  sets: TicketSet[];
};

// Evaluation tipovi

export type LegStatus = "PENDING" | "WIN" | "LOSE";
export type TicketStatus = "PENDING" | "WIN" | "LOSE" | "PARTIAL";

export type EvaluatedLeg = {
  fixture_id: number;
  status: LegStatus;
};

export type EvaluatedTicket = {
  ticket_id: string;
  status?: TicketStatus;
  legs?: EvaluatedLeg[];
};

export type EvaluationFeed = {
  date: string;
  tickets: EvaluatedTicket[];
};

// Enriched tipovi koje app koristi (tickets + evaluation spojeni)

export type EnrichedLeg = Leg & { status: LegStatus };

export type EnrichedTicket = Ticket & {
  status: TicketStatus;
  legs: EnrichedLeg[];
};

export type EnrichedSet = {
  code: string;
  label: string;
  tickets: EnrichedTicket[];
};

// Emoji mapa za status

export const STATUS_EMOJI: Record<LegStatus | TicketStatus, string> = {
  PENDING: "⏳",
  WIN: "✅",
  LOSE: "❌",
  PARTIAL: "⚠️",
};
