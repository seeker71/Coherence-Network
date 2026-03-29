import { redirect } from "next/navigation";

// /automation has been consolidated into /nodes
// All provider stats, node health, and readiness info is now on the Nodes page.
export default function AutomationRedirect() {
  redirect("/nodes");
}
