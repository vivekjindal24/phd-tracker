import type { Metadata, Viewport } from "next";
import { Fraunces, Nunito } from "next/font/google";
import { headers } from "next/headers";
import Script from "next/script";
import type { ReactNode } from "react";
import { WakingOverlay } from "@/components/WakingOverlay";
import { SessionProvider } from "@/lib/session";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  axes: ["SOFT"],
  variable: "--font-display",
  display: "swap",
});
const body = Nunito({ subsets: ["latin"], variable: "--font-body", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Anveshan", template: "%s · Anveshan" },
  description: "The research system of your university.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6efe6" },
    { media: "(prefers-color-scheme: dark)", color: "#221a2e" },
  ],
};

// Applies the remembered theme before first paint (no flash). Static string, no user input.
const THEME_INIT = `try{var t=localStorage.getItem("anveshan.theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The per-request nonce from proxy.ts (the CSP); reading it renders every page per request.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`} suppressHydrationWarning>
      <body>
        <Script id="theme-init" strategy="beforeInteractive" nonce={nonce}>
          {THEME_INIT}
        </Script>
        <SessionProvider>
          {children}
          <WakingOverlay />
        </SessionProvider>
      </body>
    </html>
  );
}
