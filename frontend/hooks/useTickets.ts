// hooks/useTickets.ts
import { useCallback, useEffect, useState } from "react";
import {
  TicketsFeed,
  EvaluationFeed,
  EnrichedSet,
  EnrichedTicket,
  EnrichedLeg,
  Ticket,
  LegStatus,
  TicketStatus,
  EvaluatedTicket,
} from "../types/tickets";

// GitHub Pages base URL (Naksir Autonomous)
const FEED_BASE = "https://darkotosic.github.io/naksir-autonomous";

// Direktni URL-ovi
const TICKETS_URL = `${FEED_BASE}/tickets.json`;
const EVAL_URL = `${FEED_BASE}/evaluation.json`;

export type UseTicketsResult = {
  loading: boolean;
  error: string;
  date: string;
  sets: EnrichedSet[];
  reload: () => void;
};

export function useTickets(): UseTicketsResult {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [date, setDate] = useState<string>("");
  const [sets, setSets] = useState<EnrichedSet[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      //
      // 1. Povuci tickets.json
      //
      const ticketsRes = await fetch(TICKETS_URL, { cache: "no-store" });

      if (!ticketsRes.ok) {
        throw new Error(`Tickets HTTP ${ticketsRes.status}`);
      }

      const ticketsJson = (await ticketsRes.json()) as TicketsFeed;

      //
      // 2. Povuci evaluation.json (ako postoji)
      //
      let evalJson: EvaluationFeed | null = null;
      try {
        const evalRes = await fetch(EVAL_URL, { cache: "no-store" });
        if (evalRes.ok) {
          evalJson = (await evalRes.json()) as EvaluationFeed;
        }
      } catch {
        evalJson = null;
      }

      //
      // 3. Mapiraj evaluation u mapu
      //
      const evalMap = new Map<string, EvaluatedTicket>();
      if (evalJson?.tickets) {
        for (const t of evalJson.tickets) {
          if (t.ticket_id) {
            evalMap.set(t.ticket_id, t);
          }
        }
      }

      //
      // 4. Enrichment funkcija za jedan tiket
      //
      const enrichTicket = (ticket: Ticket): EnrichedTicket => {
        const evaluation = evalMap.get(ticket.ticket_id);

        // Ako nema evaluation → sve pending
        if (!evaluation) {
          const legsPending: EnrichedLeg[] = ticket.legs.map((leg) => ({
            ...leg,
            status: "PENDING",
          }));
          return { ...ticket, status: "PENDING", legs: legsPending };
        }

        const legStatusMap = new Map<number, LegStatus>();
        if (evaluation.legs) {
          for (const l of evaluation.legs) {
            legStatusMap.set(l.fixture_id, l.status);
          }
        }

        const legs: EnrichedLeg[] = ticket.legs.map((leg) => ({
          ...leg,
          status: legStatusMap.get(leg.fixture_id) ?? "PENDING",
        }));

        let status: TicketStatus =
          evaluation.status ??
          (legs.every((l) => l.status === "WIN")
            ? "WIN"
            : legs.some((l) => l.status === "LOSE")
            ? "LOSE"
            : "PENDING");

        return { ...ticket, status, legs };
      };

      //
      // 5. Enrich celih setova
      //
      const enrichedSets: EnrichedSet[] =
        ticketsJson.sets?.map((s) => ({
          code: s.code,
          label: s.label || s.code,
          tickets: s.tickets.map(enrichTicket),
        })) || [];

      //
      // 6. Snimi state
      //
      setDate(ticketsJson.date || "");
      setSets(enrichedSets);
    } catch (e: any) {
      setError(e?.message || "Failed to load tickets");
      setSets([]);
      setDate("");
    } finally {
      setLoading(false);
    }
  }, []);

  //
  // Auto-load kada se mountuje komponenta
  //
  useEffect(() => {
    load();
  }, [load]);

  return { loading, error, date, sets, reload: load };
}
