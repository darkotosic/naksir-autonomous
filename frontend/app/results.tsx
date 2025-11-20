// app/results.tsx
import React from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl } from "react-native";
import { useTickets } from "../hooks/useTickets";
import { TicketCard } from "../components/TicketCard";
import { Colors, layout } from "../constants/theme";

export default function ResultsPage() {
  const { loading, error, date, sets, reload } = useTickets();

  return (
    <View style={s.screen}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={reload} tintColor={Colors.accent} />
        }
      >
        <Text style={s.heading}>Evaluation</Text>
        {date ? <Text style={s.subHeading}>📅 {date}</Text> : null}

        {error ? <Text style={s.error}>⚠️ {error}</Text> : null}

        {sets.map((set) => (
          <View key={set.code} style={s.setBlock}>
            <Text style={s.setTitle}>{set.label || set.code}</Text>
            {set.tickets.map((t) => (
              <TicketCard key={t.ticket_id} ticket={t} />
            ))}
          </View>
        ))}

        {!loading && !error && !sets.length && (
          <Text style={s.empty}>Još nema evaluacije za danas.</Text>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.background },
  scroll: { flex: 1 },
  content: { padding: layout.paddingScreen, paddingBottom: 32 },
  heading: {
    color: Colors.textPrimary,
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  subHeading: { color: Colors.textSecondary, fontSize: 13, marginBottom: 14 },
  setBlock: { marginBottom: 24 },
  setTitle: { color: Colors.accent, fontSize: 15, fontWeight: "700", marginBottom: 10 },
  error: { color: Colors.danger, marginTop: 16 },
  empty: { color: Colors.textSecondary, marginTop: 24 },
});
