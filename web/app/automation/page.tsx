import { redirect } from "next/navigation";

/** Legacy route — consolidated under /nodes (automation garden). */
export default function AutomationRedirectPage() {
  redirect("/nodes");
}
