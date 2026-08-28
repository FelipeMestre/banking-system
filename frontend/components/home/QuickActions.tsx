import Link from "next/link";
import { Button } from "@/components/ui/button";

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
        <Button asChild className="w-full justify-start">
          <Link href="/transfer">Send a transfer</Link>
        </Button>
        <Button type="button" variant="outline" disabled className="w-full justify-start">
          Pay a bill
        </Button>
        <Button type="button" variant="outline" disabled className="w-full justify-start">
          Download statement
        </Button>
      </div>
    </section>
  );
}
