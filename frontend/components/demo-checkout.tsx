"use client";

import { useEffect, useRef } from "react";
import styles from "./demo-checkout.module.css";

export type CheckoutProduct =
  | { kind: "report"; title: string; reportId: string }
  | { kind: "premium"; title: string };

type DemoCheckoutProps = {
  product: CheckoutProduct | null;
  onClose: () => void;
  onConfirm: (product: CheckoutProduct) => void;
};

/** Native dialog provides keyboard focus handling and Escape support. */
export default function DemoCheckout({ product, onClose, onConfirm }: DemoCheckoutProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !product || dialog.open) return;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [product]);

  const price = product?.kind === "report" ? "€0.49" : "€4.99/month";
  return <dialog ref={dialogRef} className={styles.dialog} aria-labelledby="checkout-title"
    aria-describedby="checkout-description" onCancel={onClose} onClose={onClose}>
    {product && <div className={styles.content}>
      <div className={styles.topline}><span>DEMO CHECKOUT</span><button type="button" className={styles.close}
        aria-label="Close checkout" onClick={onClose}>×</button></div>
      <p className={styles.eyebrow}>{product.kind === "report" ? "SINGLE MATCH REPORT" : "UNLIMITED ACCESS"}</p>
      <h2 id="checkout-title">Confirm your demo access</h2>
      <p id="checkout-description" className={styles.description}>Review the selection below. This is a demo checkout. No payment will be collected.</p>
      <div className={styles.order}>
        <span><strong>{product.kind === "report" ? "Advanced match report" : "Premium"}</strong><small>{product.title}</small></span>
        <strong>{price}</strong>
      </div>
      <p className={styles.disclaimer}>Confirming only changes this browser&apos;s demo access. It does not create a real subscription or charge.</p>
      <div className={styles.actions}>
        <button type="button" className={styles.secondary} onClick={onClose}>Go back</button>
        <button type="button" className={styles.primary} onClick={() => onConfirm(product)}>Confirm demo access</button>
      </div>
    </div>}
  </dialog>;
}
