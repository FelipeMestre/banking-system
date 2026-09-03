"use client";

export function InfoAside() {
  return (
    <aside className="flex flex-col gap-ds-4">
      <section className="border-t-2 border-divider bg-surface p-ds-4">
        <h3 className="font-heading text-sm font-extrabold">How transfers work</h3>
        <ol className="mt-ds-3 flex flex-col gap-ds-2">
          <li className="flex gap-ds-2 text-sm">
            <span className="font-heading font-extrabold text-neutral-500">01</span>
            <span>Choose source account and recipient</span>
          </li>
          <li className="flex gap-ds-2 text-sm">
            <span className="font-heading font-extrabold text-neutral-500">02</span>
            <span>Enter amount and review exchange</span>
          </li>
          <li className="flex gap-ds-2 text-sm">
            <span className="font-heading font-extrabold text-neutral-500">03</span>
            <span>Confirm and track verdict</span>
          </li>
        </ol>
      </section>

      <section className="border-2 border-divider bg-surface p-ds-4">
        <h3 className="font-heading text-sm font-extrabold">Limits & fees</h3>
        <p className="mt-ds-2 text-sm text-neutral-700">
          Daily limit <span className="font-semibold">$50,000</span>. Fees applied by gateway and shown before confirmation.
        </p>
      </section>

      <section className="border-l-[6px] border-accent bg-surface p-ds-4">
        <h3 className="font-heading text-sm font-extrabold">Need help?</h3>
        <p className="mt-ds-2 text-sm text-neutral-700">
          Contact support if your transfer is delayed or declined.
        </p>
      </section>
    </aside>
  );
}
