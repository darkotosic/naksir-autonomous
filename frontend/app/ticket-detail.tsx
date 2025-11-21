// app/ticket-detail.tsx
import React, { useMemo } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import type { EnrichedTicket, Leg } from "../types/tickets";
import { Colors, layout } from "../constants/theme";

function formatKickoff(iso: string | undefined) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`);
    return `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}. ${d.getUTCHours()}:${pad(d.getUTCMinutes())} UTC`;
  } catch {
    return iso;
  }
}

export default function TicketDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ ticket?: string; setLabel?: string }>();

  const ticket: EnrichedTicket | null = useMemo(() => {
    if (!params.ticket) return null;
    try {
      return JSON.parse(params.ticket as string) as EnrichedTicket;
    } catch {
      return null;
    }
  }, [params.ticket]);

  if (!ticket) {
    return (
      <View style={[s.screen, { justifyContent: "center", alignItems: "center" }]}>
        <Text style={s.error}>Ticket data is missing.</Text>
      </View>
    );
  }

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        {/* Header */}
        <View style={s.headerCard}>
          <Text style={s.setLabel}>{params.setLabel || "[TICKET]"}</Text>
          <Text style={s.ticketTitle}>{ticket.code || ticket.id || "[GOALS MIX]"}</Text>

          <View style={s.headerRow}>
            <Text style={s.headerMeta}>
              Total odds: <Text style={s.highlight}>{ticket.total_odds?.toFixed?.(2) ?? ticket.total_odds}</Text>
            </Text>
            {typeof ticket.ai_score === "number" && (
              <Text style={s.headerMeta}>
                AI score: <Text style={s.highlight}>{ticket.ai_score.toFixed(1)}%</Text>
              </Text>
            )}
          </View>

          <Text style={s.subtitle}>Detaljna analiza za svaki meč u tiketu.</Text>
        </View>

        {/* Legs */}
        {ticket.legs.map((leg: Leg, idx: number) => (
          <View key={`${leg.fixture_id}-${leg.market}-${idx}`} style={s.legCard}>
            <Text style={s.league}>
              {leg.league_country} — {leg.league_name}
            </Text>
            <Text style={s.match}>
              {leg.home} <Text style={s.vs}>vs</Text> {leg.away}
            </Text>
            <Text style={s.kickoff}>⏰ {formatKickoff(leg.kickoff)}</Text>

            <View style={s.pickRow}>
              <Text style={s.pickLabel}>Tip:</Text>
              <Text style={s.pickValue}>
                {leg.pick} @ {leg.odds.toFixed(2)}
              </Text>
            </View>

            {Array.isArray(leg.analysis) && leg.analysis.length > 0 ? (
              <View style={s.analysisBlock}>
                {leg.analysis.map((sentence, i) => (
                  <Text key={i} style={s.analysisText}>
                    • {sentence}
                  </Text>
                ))}
              </View>
            ) : (
              <Text style={s.analysisFallback}>
                Nema generisane detaljne analize za ovaj meč.
              </Text>
            )}
          </View>
        ))}

        <View style={{ height: 24 }} />
      </ScrollView>

      <View style={s.backBar}>
        <TouchableOpacity onPress={() => router.back()} style={s.backButton}>
          <Text style={s.backText}>← Back to tickets</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scroll: {
    padding: layout.paddingScreen,
    paddingBottom: 80,
  },
  headerCard: {
    backgroundColor: Colors.card,
    borderRadius: layout.radiusCard,
    padding: layout.paddingCard,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    ...layout.shadow,
  },
  setLabel: {
    color: Colors.accent,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 4,
  },
  ticketTitle: {
    color: Colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 8,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  headerMeta: {
    color: Colors.textSecondary,
    fontSize: 13,
  },
  highlight: {
    color: Colors.accent,
    fontWeight: "600",
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: 4,
  },
  legCard: {
    backgroundColor: Colors.card,
    borderRadius: layout.radiusCard,
    padding: layout.paddingCard,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: Colors.divider,
  },
  league: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginBottom: 4,
  },
  match: {
    color: Colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
  },
  vs: {
    color: Colors.textSecondary,
    fontSize: 14,
  },
  kickoff: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: 2,
    marginBottom: 8,
  },
  pickRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  pickLabel: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginRight: 6,
  },
  pickValue: {
    color: Colors.accent,
    fontSize: 14,
    fontWeight: "600",
  },
  analysisBlock: {
    marginTop: 4,
  },
  analysisText: {
    color: Colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 2,
  },
  analysisFallback: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontStyle: "italic",
  },
  backBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    padding: 12,
    backgroundColor: Colors.background,
    borderTopWidth: 1,
    borderTopColor: Colors.divider,
  },
  backButton: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    paddingVertical: 10,
    paddingHorizontal: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  backText: {
    color: Colors.accent,
    fontSize: 14,
    fontWeight: "600",
  },
  error: {
    color: Colors.danger,
    fontSize: 14,
  },
});
