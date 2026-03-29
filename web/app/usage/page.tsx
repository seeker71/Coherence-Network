import { redirect } from "next/navigation";

/** Legacy route — consolidated under /pipeline (usage & remote ops). */
export default function UsageRedirectPage() {
  redirect("/pipeline");
}
