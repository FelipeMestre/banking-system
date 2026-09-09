"use client";

export function InfoAside() {
  return (
    <aside className="flex flex-col gap-ds-8 bg-bg p-10">
      <section className="flex flex-col">
        <h3 className="font-heading text-[11px] font-extrabold uppercase tracking-[0.08em] text-text">
          How transfers work
        </h3>
        <div className="mt-3 border-t-2 border-divider">
          <ol className="flex flex-col">
            <li className="flex gap-3.5 border-b border-neutral-300 py-4">
              <span className="w-5 shrink-0 font-heading text-[14px] font-extrabold leading-6 text-accent-700">
                01
              </span>
              <span className="text-[13px] leading-6 text-neutral-700">
                Choose source account and recipient
              </span>
            </li>
            <li className="flex gap-3.5 border-b border-neutral-300 py-4">
              <span className="w-5 shrink-0 font-heading text-[14px] font-extrabold leading-6 text-accent-700">
                02
              </span>
              <span className="text-[13px] leading-6 text-neutral-700">
                Enter amount and review exchange
              </span>
            </li>
            <li className="flex gap-3.5 py-4">
              <span className="w-5 shrink-0 font-heading text-[14px] font-extrabold leading-6 text-accent-700">
                03
              </span>
              <span className="text-[13px] leading-6 text-neutral-700">Confirm and track verdict</span>
            </li>
          </ol>
        </div>
      </section>

      <section className="flex flex-col">
        <h3 className="font-heading text-[11px] font-extrabold uppercase tracking-[0.08em] text-text">
          Limits &amp; fees
        </h3>
        <div className="mt-3 border-2 border-divider p-[18px_20px]">
          <div className="flex flex-col gap-2.5 text-[13px]">
            <div className="flex justify-between">
              <span className="text-neutral-700">Daily limit</span>
              <span className="font-semibold tabular-nums text-text">$50,000.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-700">Internal fee</span>
              <span className="font-semibold tabular-nums text-text">Free</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-700">External fee</span>
              <span className="font-semibold tabular-nums text-text">0.35%</span>
            </div>
          </div>
        </div>
      </section>

      <section className="border-l-[6px] border-accent bg-bg py-1 pl-4">
        <h3 className="font-heading text-[12px] font-semibold leading-6 text-text">Need help?</h3>
        <p className="m-0 text-[12px] leading-6 text-neutral-700">
          Contact support if your transfer is delayed or declined.
        </p>
      </section>
    </aside>
  );
}
