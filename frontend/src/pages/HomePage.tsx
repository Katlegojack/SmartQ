import { Link } from "react-router-dom";

export function HomePage() {
  return <div className="public-page">
    <header className="public-nav"><a className="brand" href="/"><span className="brand-mark">SQ</span><span><strong>Smart Q</strong><small>Where Time Meets Priority</small></span></a><nav><Link to="/login/">Sign in</Link><Link className="button button--dark" to="/register/">Create account</Link></nav></header>
    <main className="hero">
      <section className="hero-copy"><span className="eyebrow">Queue intelligence for real operations</span><h1>Waiting should be managed, not endured.</h1><p>Smart Q connects appointments, live queues and service counters so customers know what is happening and teams know what to do next.</p><div className="hero-actions"><Link className="button button--primary" to="/login/">Use Smart Q</Link><Link className="button button--quiet" to="/staff-login/">Staff sign in</Link></div></section>
      <section className="hero-demo" aria-label="Smart Q queue example"><div className="demo-top"><span>LIVE QUEUE</span><span className="live-dot">Live</span></div><strong className="demo-number">A104</strong><p>Smart ID application</p><div className="queue-progress"><span style={{ width: "72%" }} /></div><div className="demo-grid"><div><small>People ahead</small><strong>3</strong></div><div><small>Estimated wait</small><strong>18 min</strong></div></div><div className="demo-next">We will tell you when you are next.</div></section>
    </main>
    <section className="product-strip"><article><span>01</span><h2>Book</h2><p>Choose a real branch, service and available time.</p></article><article><span>02</span><h2>Check in</h2><p>Enter the live queue without standing in a physical line.</p></article><article><span>03</span><h2>Get served</h2><p>Reception and counter teams work from the same queue state.</p></article></section>
  </div>;
}
