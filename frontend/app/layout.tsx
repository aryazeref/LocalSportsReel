import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local SportsReel — Closer to the game",
  description: "Discover remarkable sports moments in your local community. Hackathon prototype with synthetic data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
