import { redirect } from "next/navigation";

// /remote-ops consolidated into /nodes.
// Dispatch controls, queue, and deployment status are now at /nodes.
export default function RemoteOpsRedirect() {
  redirect("/nodes");
}
