// app/_layout.tsx
import React from "react";
import { Drawer } from "expo-router/drawer";
import {
  DrawerContentScrollView,
  DrawerItem,
  DrawerContentComponentProps,
} from "@react-navigation/drawer";
import { StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import * as Linking from "expo-linking";
import { Colors } from "../constants/theme";

function CustomDrawerContent(props: DrawerContentComponentProps) {
  const router = useRouter();
  const close = () => props.navigation.closeDrawer();

  const items = [
    { label: "Home", action: () => router.push("/") },
    { label: "Naksir Tickets", action: () => router.push("/tickets") },
    { label: "Results / Evaluation", action: () => router.push("/results") },
    {
      label: "Legal & Disclaimer",
      action: () => Linking.openURL("https://naksirpredictions.top/legal-disclaimer"),
    },
    {
      label: "Naksir Telegram",
      action: () => Linking.openURL("https://t.me/naksiranalysis"),
    },
  ];

  return (
    <DrawerContentScrollView {...props} style={s.drawer}>
      {items.map((item, idx) => (
        <DrawerItem
          key={idx}
          label={item.label}
          onPress={() => {
            item.action();
            close();
          }}
          labelStyle={s.drawerLabel}
          style={s.drawerItem}
        />
      ))}
    </DrawerContentScrollView>
  );
}

export default function RootLayout() {
  return (
    <Drawer
      screenOptions={{
        headerShown: false,
        drawerStyle: s.drawer,
      }}
      drawerContent={(props) => <CustomDrawerContent {...props} />}
    />
  );
}

const s = StyleSheet.create({
  drawer: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  drawerItem: {
    borderRadius: 12,
    marginHorizontal: 12,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    backgroundColor: Colors.accentSoft,
  },
  drawerLabel: {
    fontWeight: "700",
    letterSpacing: 0.6,
    color: Colors.textPrimary,
    textTransform: "uppercase",
    fontSize: 13,
  },
});
