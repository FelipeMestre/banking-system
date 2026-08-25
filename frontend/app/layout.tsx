import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Banking Payment System",
  description: "Test harness for the multishard payment flow",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
