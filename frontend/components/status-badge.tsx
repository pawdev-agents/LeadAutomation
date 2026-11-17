import type { LeadStatus } from "@/lib/types";
const labels: Record<LeadStatus,string>={new:"New",contacted:"Contacted",qualified:"Qualified",booked:"Booked",won:"Won",lost:"Lost"};
export function StatusBadge({status}:{status:LeadStatus}){return <span className={`status status-${status}`}>{labels[status]}</span>}
export function ScoreBadge({score}:{score:number}){return <span className={`score ${score>=80?"hot":score>=55?"warm":"cold"}`}>{score>=80?"Hot":score>=55?"Warm":"Cold"} · {score}</span>}
