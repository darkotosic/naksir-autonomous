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
      {/* Header */}
      <View style={s.headerRow}>
        <Text style={s.title}>
          🎫 {ticket.label} — Ticket {ticket.ticket_id} {ticketEmoji}
        </Text>
      </View>

      {/* Meta info */}
      <View style={s.metaRow}>
        <Text style={s.meta}>
          📈 Total odds: {ticket.total_odds.toFixed(2)} {ticketEmoji}
        </Text>
        <Text style={s.meta}>🤖 AI score: {ticket.score.toFixed(1)}%</Text>
      </View>

      <View style={s.divider} />

      {/* Legs */}
      {ticket.legs.map((leg: EnrichedLeg) => {
        const legEmoji = STATUS_EMOJI[leg.status];

        return (
          <View key={leg.fixture_id} style={s.leg}>
            <Text style={s.league}>
              🏟 {leg.league_country} — {leg.league_name}
            </Text>

            <Text style={s.match}>
              ⚽️ {leg.home} vs {leg.away}
            </Text>

            <Text style={s.kickoff}>⏰ {leg.kickoff}</Text>

            <Text style={s.pick}>
              🎯 {leg.market} → {leg.pick} @ {leg.odds} {legEmoji}
            </Text>
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
  headerRow: {
    marginBottom: 6,
  },
  title: {
    color: Colors.textPrimary,
    fontWeight: "700",
    fontSize: 15,
    letterSpacing: 0.4,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 6,
  },
  meta: {
    color: Colors.textSecondary,
    fontSize: 12,
  },
  divider: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
    marginVertical: 8,
  },
  leg: {
    marginBottom: 8,
    paddingVertical: 4,
  },
  league: {
    color: Colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
  },
  match: {
    color: Colors.textPrimary,
    fontSize: 14,
    marginTop: 2,
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
    fontWeight: "600",
  },
});
