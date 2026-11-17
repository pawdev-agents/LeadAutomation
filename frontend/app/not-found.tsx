import Link from "next/link";
export default function NotFound(){return <main className="not-found"><h1>Page not found</h1><p>The page you requested does not exist or is no longer available.</p><Link className="btn" href="/">Back to dashboard</Link></main>}
