import type { Metadata } from "next";
import localFont from "next/font/local";
import SiteNav from "../components/site-nav";
import { THEME_INIT_SCRIPT } from "../lib/theme";
import "./globals.css";

const jakarta = localFont({
  src: "../node_modules/@fontsource-variable/plus-jakarta-sans/files/plus-jakarta-sans-latin-wght-normal.woff2",
  weight: "400 800", display: "swap", variable: "--font-jakarta",
});
const plexMono = localFont({
  src: [
    { path: "../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2", weight: "500" },
    { path: "../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-600-normal.woff2", weight: "600" },
  ],
  display: "swap", variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Local SportsReel — Closer to the game",
  description: "Discover remarkable sports moments in your local community. Hackathon prototype with synthetic data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning className={`${jakarta.variable} ${plexMono.variable}`}>
      <head><script id="siniristi-theme-init" dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head>
      <body>
        <SiteNav />
        {children}
      </body>
    </html>
  );
}
