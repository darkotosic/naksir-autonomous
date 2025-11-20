import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { EnrichedTicket, EnrichedLeg, STATUS_EMOJI } from "../types/tickets";
import { Colors, layout } from "../constants/theme";

type Props = {
  ticket: EnrichedTicket;
};

export function TicketCard({ ticket }: Props) {
  const ticketEmoji = STATUS_EMOJI[ticket.status];

  return (
    <View style={s.card}>
      <View style={s.badgeRow}>
        <View style={s.badge}>
          <Text style={s.badgeText}>#{ticket.ticket_id}</Text>
        </View>
        <Text style={s.pill}>{ticketEmoji} {ticket.status}</Text>
      </View>

      <View style={s.headerRow}>
        <Text style={s.title}>🎫 {ticket.label}</Text>
        <Text style={s.metaAccent}>AI {ticket.score.toFixed(1)}%</Text>
      </View>

      <View style={s.metaRow}>
        <Text style={s.meta}>Total odds: {ticket.total_odds.toFixed(2)}</Text>
        <Text style={s.meta}>Legs: {ticket.legs.length}</Text>
      </View>

      <View style={s.divider} />

      {ticket.legs.map((leg: EnrichedLeg) => {
        const legEmoji = STATUS_EMOJI[leg.status];

        return (
          <View key={leg.fixture_id} style={s.leg}>
            <View style={s.legHeader}>
              <Text style={s.league}>🏟 {leg.league_country} — {leg.league_name}</Text>
              <Text style={s.legStatus}>{legEmoji}</Text>
            </View>

            <Text style={s.match}>⚽️ {leg.home} vs {leg.away}</Text>
            <Text style={s.kickoff}>⏰ {leg.kickoff}</Text>
            <Text style={s.pick}>🎯 {leg.market} → {leg.pick} @ {leg.odds}</Text>
          </View>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: layout.radiusCard,
    padding: layout.paddingCard,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    ...layout.shadow,
  },
  badgeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    backgroundColor: Colors.accentSoft,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
  },
  badgeText: {
    color: Colors.accent,
    fontWeight: "800",
    fontSize: 12,
  },
  pill: {
    color: Colors.textPrimary,
    fontWeight: "700",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    color: Colors.textPrimary,
    fontWeight: "800",
    fontSize: 15,
    letterSpacing: 0.4,
  },
  metaAccent: {
    color: Colors.accent,
    fontWeight: "800",
    fontSize: 13,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    marginTop: 6,
    marginBottom: 10,
  },
  meta: {
    color: Colors.textSecondary,
    fontSize: 12,
  },
  divider: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
    marginVertical: 6,
  },
  leg: {
    marginBottom: 8,
    paddingVertical: 6,
    paddingHorizontal: 4,
    borderRadius: 10,
    backgroundColor: "rgba(255,255,255,0.02)",
  },
  legHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  league: {
    color: Colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
  },
  legStatus: {
    color: Colors.accent,
    fontWeight: "800",
    fontSize: 12,
  },
  match: {
    color: Colors.textPrimary,
    fontSize: 14,
    marginTop: 2,
    fontWeight: "700",
  },
  kickoff: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: 1,
  },
  pick: {
    color: Colors.accent,
    fontSize: 13,
    marginTop: 2,
    fontWeight: "700",
  },
});
