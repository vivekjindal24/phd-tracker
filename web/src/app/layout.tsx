import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";

export const metadata: Metadata = {
	title: "PhD Tracker",
	description: "Supervisor–scholar workspace for Indian university PhD programs",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
	return (
		<html lang="en">
			<body>
				{/* usePathname() in the client (app) shell suspends prerendering (Next 16 cacheComponents) */}
				<Suspense>{children}</Suspense>
			</body>
		</html>
	);
}