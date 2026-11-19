import Link from "next/link";
import styles from "./pricing-card.module.css";

type PricingCardProps = {
  name: string;
  price: string;
  cadence?: string;
  description: string;
  features: string[];
  actionLabel: string;
  href?: string;
  onAction?: () => void;
  featured?: boolean;
  badge?: string;
  current?: boolean;
};

export default function PricingCard({ name, price, cadence, description, features, actionLabel, href,
  onAction, featured = false, badge, current = false }: PricingCardProps) {
  const className = `${styles.card} ${featured ? styles.featured : ""}`;
  return <article className={className} aria-label={`${name} plan`}>
    {badge && <span className={styles.badge}>{badge}</span>}
    <p className={styles.name}>{name}</p>
    <p className={styles.price}>{price}<span>{cadence}</span></p>
    <p className={styles.description}>{description}</p>
    <ul>{features.map(feature => <li key={feature}>{feature}</li>)}</ul>
    {href ? <Link className={featured ? styles.primary : styles.secondary} href={href}>{actionLabel}</Link>
      : <button type="button" className={featured ? styles.primary : styles.secondary} onClick={onAction} disabled={current}>
        {current ? "Premium active" : actionLabel}
      </button>}
    {current && <span className={styles.current}>Current demo access</span>}
  </article>;
}
