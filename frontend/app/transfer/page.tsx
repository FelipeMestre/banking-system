import { TransferConsole } from "@/features/transfers";

export default function Page() {
  return (
    <main>
      <header>
        <h1>Transfer</h1>
        <p className="m-0 text-[0.9rem] text-neutral-600">
          The request is written once, then the verdict arrives asynchronously over a WebSocket.
        </p>
      </header>
      <TransferConsole />
    </main>
  );
}
