import { Dashboard } from "./dashboard";

// Server component intentionally does not fetch — the API requires
// authentication (admin key or JWT), and we don't have per-user credentials
// at SSR time. The client-side Dashboard prompts for the admin key.
export default function Home() {
  return <Dashboard initialRun={null} />;
}
