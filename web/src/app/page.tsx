import { redirect } from "next/navigation";

// No public landing page — the app is the workspace. Logged-in users bounce
// through /login, which sends them to /dashboard.
export default function RootPage() {
	redirect("/login");
}