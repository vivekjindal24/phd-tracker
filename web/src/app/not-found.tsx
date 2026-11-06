import Link from "next/link";
import { Owl } from "@/components/brand/Owl";
import "@/components/ui/ui.css";

export default function NotFound() {
  return (
    <main className="empty-state">
      <Owl pose="empty" size={110} />
      <h1>We can&apos;t find that page</h1>
      <p>The link may be old or mistyped.</p>
      <Link href="/home">Go to home</Link>
    </main>
  );
}
