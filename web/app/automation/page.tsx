import { redirect } from "next/navigation";

// /automation has been consolidated into /nodes
// All provider health, readiness, and node stats are now at /nodes
export default function AutomationPage() {
  redirect("/nodes");
}
