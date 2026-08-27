import { AccountsAndTransactions } from "@/components/home/AccountsAndTransactions";
import { CreditCardPanel } from "@/components/home/CreditCardPanel";
import { QuickActions } from "@/components/home/QuickActions";
import { TotalPosition } from "@/components/home/TotalPosition";
import {
  BALANCES_AS_OF,
  CREDIT_CARD,
  HOME_ACCOUNTS,
  SHOW_CREDIT_CARD,
  TOTAL_POSITION,
  TRANSACTIONS_BY_ACCOUNT,
} from "@/lib/placeholder-home";

export default function Page() {
  return (
    <AccountsAndTransactions
      accounts={HOME_ACCOUNTS}
      transactionsByAccount={TRANSACTIONS_BY_ACCOUNT}
      asOf={BALANCES_AS_OF}
      aside={
        <aside className="flex flex-col gap-[28px]">
          {SHOW_CREDIT_CARD ? <CreditCardPanel card={CREDIT_CARD} /> : null}
          <QuickActions />
          <TotalPosition position={TOTAL_POSITION} />
        </aside>
      }
    />
  );
}
