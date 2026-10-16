import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";

import { RefineRoot } from "@/components/refine";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
	title: "PhD Tracker",
	description: "Supervisor–scholar workspace for Indian university PhD programs",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
	return (
		<html lang="en" className={inter.variable}>
			<body>
				{/* usePathname() in the client (app) shell suspends prerendering (Next 16 cacheComponents) */}
				<Suspense>
					<RefineRoot>{children}</RefineRoot>
				</Suspense>
			</body>
		</html>
	);
}