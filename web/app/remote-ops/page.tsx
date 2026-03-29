import { redirect } from "next/navigation";

/** Legacy route — consolidated under /pipeline. */
export default function RemoteOpsRedirectPage() {
  redirect("/pipeline");
}
