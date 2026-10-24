"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./theme-toggle";
import styles from "./site-nav.module.css";

const links = [
  { href: "/", label: "Home" },
  { href: "/liiga", label: "Liiga" },
  { href: "/predictions", label: "Predictions" },
  { href: "/pricing", label: "Pricing" },
];

export default function SiteNav() {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="Local SportsReel home">
          <span className={styles.brandMark} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" focusable="false">
              <path d="M6 18 18 6M6 6h12v12" />
            </svg>
          </span>
          <span>KUCING<span className={styles.brandThin}>MAEW</span><span className={styles.brandDot}>.</span></span>
        </Link>
        <nav aria-label="Primary navigation">
          <ul className={styles.links}>
            {links.map(link => {
              const active = pathname === link.href || (link.href !== "/" && pathname.startsWith(`${link.href}/`));
              return (
                <li key={link.href}>
                  <Link href={link.href} className={styles.link} aria-current={active ? "page" : undefined}>
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className={styles.topbarRight}><ThemeToggle /></div>
      </div>
    </header>
  );
}
