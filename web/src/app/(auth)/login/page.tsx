"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { doLogin } from "@/lib/auth";
import { Button, ErrorText, Field } from "@/lib/ui";
import "@/app/(app)/app.css";

export default function LoginPage() {
	const router = useRouter();
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);

	async function submit(e: FormEvent) {
		e.preventDefault();
		setError("");
		setBusy(true);
		try {
			await doLogin(email, password);
			router.replace("/dashboard");
		} catch (err) {
			setError(err instanceof Error ? err.message : "Login failed");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="login-wrap">
			<div className="login-card">
				<h1>PhD Tracker</h1>
				<p className="login-sub">Supervisor–scholar workspace · university login</p>
				<form onSubmit={submit}>
					<Field label="Email">
						<input
							type="email"
							required
							autoComplete="email"
							autoFocus
							value={email}
							onChange={(e) => setEmail(e.target.value)}
						/>
					</Field>
					<Field label="Password">
						<input
							type="password"
							required
							autoComplete="current-password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
						/>
					</Field>
					<ErrorText>{error}</ErrorText>
					<Button type="submit" kind="primary" disabled={busy}>
						{busy ? "Signing in…" : "Sign in"}
					</Button>
				</form>
			</div>
		</div>
	);
}