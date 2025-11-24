// app/index.tsx
import React, { useCallback, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Linking,
  SafeAreaView,
  ScrollView,
  ImageBackground,
} from "react-native";
import { useRouter } from "expo-router";
import { Colors, layout } from "../constants/theme";
import mobileAds, {
  MaxAdContentRating,
  useInterstitialAd,
} from "react-native-google-mobile-ads";

const legalLinks = [
  { label: "Legal", url: "https://naksirpredictions.top/legal-disclaimer" },
  { label: "Privacy", url: "https://naksirpredictions.top/privacy-policy" },
  { label: "Terms of Use", url: "https://naksirpredictions.top/terms-of-use" },
];

const INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-1726722567967096/7805445199";

export default function LandingScreen() {
  const router = useRouter();
  const { isLoaded, isClosed, load, show } = useInterstitialAd(
    INTERSTITIAL_AD_UNIT_ID,
    {
      requestNonPersonalizedAdsOnly: true,
    },
  );

  useEffect(() => {
    mobileAds().initialize({
      requestConfiguration: {
        maxAdContentRating: MaxAdContentRating.T,
        tagForChildDirectedTreatment: false,
      },
    });
    load();
  }, [load]);

  useEffect(() => {
    if (isClosed) {
      router.push("/tickets");
      load();
    }
  }, [isClosed, load, router]);

  const handleTicketsPress = useCallback(() => {
    if (isLoaded) {
      show();
    } else {
      router.push("/tickets");
    }
  }, [isLoaded, router, show]);

  return (
    <SafeAreaView style={s.safeArea}>
      <ImageBackground
        source={require("../assets/background.png.png")}
        style={s.background}
        imageStyle={s.backgroundImage}
      >
        <View style={s.overlay}>
          <ScrollView contentContainerStyle={s.container}>
            <View style={s.glowLayer} />

            <Text style={s.logo}>Naksir Ultimate</Text>
            <Text style={s.tagline}>2+ Tickets, AI assisted — Naksir soccer analyst.</Text>

            <View style={s.linksRow}>
              {legalLinks.map((link) => (
                <Pressable
                  key={link.label}
                  onPress={() => Linking.openURL(link.url)}
                  style={({ pressed }) => [s.linkButton, pressed && s.pressed]}
                >
                  <Text style={s.linkText}>{link.label}</Text>
                </Pressable>
              ))}
            </View>

            <Pressable
              onPress={() => Linking.openURL("https://t.me/naksiranalysis")}
              style={({ pressed }) => [s.primaryButton, pressed && s.pressed]}
            >
              <Text style={s.primaryText}>Telegram</Text>
              <Text style={s.subText}>Join our analysis channel</Text>
            </Pressable>

            <View style={s.spacer} />

            <Pressable
              onPress={handleTicketsPress}
              style={({ pressed }) => [s.ctaButton, pressed && s.pressed]}
            >
              <Text style={s.ctaLabel}>Naksir Ultimate 2+ Tickets</Text>
              <Text style={s.ctaHint}>Enter for daily updated Tickets →</Text>
            </Pressable>
          </ScrollView>
        </View>
      </ImageBackground>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  background: {
    flex: 1,
    width: "100%",
  },
  backgroundImage: {
    opacity: 0.55,
  },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(2, 4, 9, 0.8)",
  },
  container: {
    flexGrow: 1,
    padding: layout.paddingScreen,
    alignItems: "center",
    gap: 18,
  },
  glowLayer: {
    position: "absolute",
    top: -120,
    width: 380,
    height: 380,
    borderRadius: 999,
    backgroundColor: "rgba(57,255,20,0.08)",
    shadowColor: Colors.accent,
    shadowRadius: 60,
    shadowOpacity: 0.6,
    shadowOffset: { width: 0, height: 0 },
  },
  logo: {
    marginTop: 12,
    color: Colors.accent,
    fontSize: 30,
    fontWeight: "900",
    letterSpacing: 1,
    textShadowColor: Colors.accent,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  tagline: {
    color: Colors.textSecondary,
    textAlign: "center",
    fontSize: 14,
    maxWidth: 320,
  },
  linksRow: {
    width: "100%",
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
    marginTop: 6,
  },
  linkButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    backgroundColor: Colors.card,
    alignItems: "center",
    ...layout.shadow,
  },
  linkText: {
    color: Colors.textPrimary,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  primaryButton: {
    width: "100%",
    paddingVertical: 16,
    borderRadius: 14,
    backgroundColor: Colors.telegram,
    borderWidth: 1,
    borderColor: "rgba(0,136,204,0.9)",
    ...layout.shadow,
    shadowColor: Colors.telegram,
    alignItems: "center",
    gap: 4,
  },
  primaryText: {
    color: "#e9f6ff",
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  subText: {
    color: "#d4e8ff",
    fontSize: 13,
  },
  ctaButton: {
    width: "100%",
    paddingVertical: 18,
    borderRadius: 16,
    backgroundColor: Colors.card,
    borderWidth: 3,
    borderColor: Colors.accent,
    alignItems: "center",
    ...layout.shadow,
  },
  ctaLabel: {
    color: Colors.textPrimary,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 0.6,
    textAlign: "center",
  },
  ctaHint: {
    marginTop: 6,
    color: Colors.accent,
    fontSize: 13,
  },
  pressed: {
    transform: [{ scale: 0.99 }],
    opacity: 0.95,
  },
  spacer: {
    height: 64,
  },
});
