import type { Metadata } from "next";
import SiteNav from "../components/site-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local SportsReel — Closer to the game",
  description: "Discover remarkable sports moments in your local community. Hackathon prototype with synthetic data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SiteNav />
        {children}
      </body>
    </html>
  );
}
