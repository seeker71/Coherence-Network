import { redirect } from "next/navigation";

// /remote-ops has been consolidated into /pipeline
// Queue, controls, and pipeline management is now on the Pipeline page.
export default function RemoteOpsRedirect() {
  redirect("/pipeline");
}
