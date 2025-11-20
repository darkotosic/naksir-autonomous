// app/tickets.tsx
import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { useRouter } from "expo-router";
import { useTickets } from "../hooks/useTickets";
import { TicketCard } from "../components/TicketCard";
import { Colors, layout } from "../constants/theme";

export default function TicketsScreen() {
  const { loading, error, date, sets, reload } = useTickets();
  const router = useRouter();

  return (
    <View style={s.screen}>
      <View style={s.header}>
        <Pressable onPress={() => router.back()} style={({ pressed }) => [s.back, pressed && s.pressed]}>
          <Text style={s.backText}>← Back</Text>
        </Pressable>
        <View style={s.titleWrap}>
          <Text style={s.heading}>Naksir Ultimate 2+ Tickets</Text>
          {date ? <Text style={s.subHeading}>📅 {date}</Text> : null}
        </View>
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={reload} tintColor={Colors.accent} />
        }
      >
        <View style={s.heroCard}>
          <Text style={s.heroTitle}>Autonomous AI picks</Text>
          <Text style={s.heroCopy}>
            Curated 2+ tickets with neon-grade confidence. Pull to refresh for the latest drop.
          </Text>
        </View>

        {loading && !sets.length && <ActivityIndicator style={{ marginTop: 30 }} size="large" />}

        {error ? <Text style={s.error}>⚠️ {error}</Text> : null}

        {sets.map((set) => (
          <View key={set.code} style={s.setBlock}>
            <View style={s.setHeader}>
              <Text style={s.setTitle}>{set.label || set.code}</Text>
              <View style={s.pill}>
                <Text style={s.pillText}>{set.tickets.length} tickets</Text>
              </View>
            </View>
            {set.tickets.map((t) => (
              <TicketCard key={t.ticket_id} ticket={t} />
            ))}
          </View>
        ))}

        {!loading && !error && !sets.length && <Text style={s.empty}>Nema tiketa za danas.</Text>}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingTop: 12,
    paddingHorizontal: layout.paddingScreen,
    paddingBottom: 6,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  back: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    backgroundColor: Colors.card,
    ...layout.shadow,
  },
  backText: {
    color: Colors.textPrimary,
    fontWeight: "800",
  },
  titleWrap: {
    flex: 1,
  },
  heading: {
    color: Colors.textPrimary,
    fontSize: 18,
    fontWeight: "900",
    letterSpacing: 0.8,
  },
  subHeading: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 4,
  },
  scroll: {
    flex: 1,
  },
  content: {
    padding: layout.paddingScreen,
    paddingBottom: 32,
    gap: 16,
  },
  heroCard: {
    backgroundColor: Colors.card,
    borderRadius: layout.radiusLg,
    padding: layout.paddingCard,
    borderWidth: 1,
    borderColor: Colors.accent,
    ...layout.shadow,
  },
  heroTitle: {
    color: Colors.accent,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: 6,
  },
  heroCopy: {
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  setBlock: {
    gap: 12,
  },
  setHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  setTitle: {
    color: Colors.textPrimary,
    fontSize: 16,
    fontWeight: "800",
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: Colors.accentSoft,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
  },
  pillText: {
    color: Colors.accent,
    fontWeight: "700",
    fontSize: 12,
  },
  error: {
    color: Colors.danger,
    marginTop: 16,
  },
  empty: {
    color: Colors.textSecondary,
    marginTop: 24,
  },
  pressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.95,
  },
});
