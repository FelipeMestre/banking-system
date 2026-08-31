import type { Metadata } from "next";
import "./globals.css";
import { Auth0ProviderWithNavigate } from "@/lib/auth/Auth0ProviderWithNavigate";

export const metadata: Metadata = {
  title: "Banking Payment System",
  description: "Test harness for the multishard payment flow",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Auth0ProviderWithNavigate>{children}</Auth0ProviderWithNavigate>
      </body>
    </html>
  );
}
