import type { Metadata } from "next";
import "@fontsource-variable/archivo/wght.css";
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/spline-sans-mono/latin-400.css";
import "@fontsource/spline-sans-mono/latin-500.css";
import "@fontsource/spline-sans-mono/latin-700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "BusDrop — your ticket belongs to your destination",
  description:
    "When one Chennai bus overflows, BusDrop moves riders mid-route to a roomier bus going the same way. Same ticket, no extra fare. Replay the Anna Salai morning peak.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
