import Link from "next/link";

/**
 * "Pay a bill" and "Download statement" have no destination in this app yet
 * — rendering them `disabled` rather than live-looking-but-inert is the same
 * honesty rule applied to the sidebar's non-Home icons: nothing on this
 * screen should look clickable and silently do nothing.
 */
export function QuickActions() {
  return (
    <section>
      <h6 className="mb-[14px] text-xs">Quick actions</h6>
      <div className="flex flex-col gap-[2px]">
        <Link href="/transfer" className="btn btn-primary btn-block mt-0">
          Send a transfer
        </Link>
        <button type="button" disabled className="btn btn-secondary btn-block mt-0">
          Pay a bill
        </button>
        <button type="button" disabled className="btn btn-secondary btn-block mt-0">
          Download statement
        </button>
      </div>
    </section>
  );
}
