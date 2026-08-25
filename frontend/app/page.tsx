import { TransferConsole } from "@/components/TransferConsole";

export default function Page() {
  return (
    <main>
      <header>
        <h1>Transfer</h1>
        <p className="subtitle">
          The request is written once, then the verdict arrives asynchronously over a WebSocket.
        </p>
      </header>
      <TransferConsole />
    </main>
  );
}
