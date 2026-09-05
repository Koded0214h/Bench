import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "../auth";
import { BenchMark, PixelCritter } from "../components/marks";
import "./landing.css";

/* ------------------------------------------------------------------ */
/*  small helpers                                                      */
/* ------------------------------------------------------------------ */

/** Steps a counter 0..n-1 on an interval. Holds at the last value when
    the visitor has asked for reduced motion, so figures read as finished. */
function usePhase(count: number, ms: number) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState(reduce ? count - 1 : 0);
  useEffect(() => {
    if (reduce) return;
    const t = setInterval(() => setPhase((p) => (p + 1) % count), ms);
    return () => clearInterval(t);
  }, [reduce, count, ms]);
  return phase;
}

/** Eases a number toward its target so money and counts visibly accrue. */
function useCountUp(target: number, ms = 1500) {
  const reduce = useReducedMotion();
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    if (reduce) {
      from.current = target;
      setValue(target);
      return;
    }
    const start = from.current;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      const v = start + (target - start) * (1 - Math.pow(1 - p, 3));
      from.current = v;
      setValue(v);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, reduce]);
  return value;
}

/** Wall clock for the run, so the panel is visibly live. */
function useElapsed(from = 134) {
  const reduce = useReducedMotion();
  const [s, setS] = useState(from);
  useEffect(() => {
    if (reduce) return;
    const t = setInterval(() => setS((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, [reduce]);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/* ------------------------------------------------------------------ */
/*  hero figure — a company working, on a loop                         */
/* ------------------------------------------------------------------ */

const ROWS = [
  { task: "Draft the launch page", worker: "Engineering-01", machine: "sandbox-7f3a", cost: 0.18 },
  { task: "Research three competitors", worker: "Research-04", machine: "browser-2b9", cost: 0.24 },
  { task: "Build the launch campaign", worker: "Operations-02", machine: "browser-4c1", cost: 0.31 },
  { task: "Check the page actually serves", worker: "Engineering-03", machine: "sandbox-9d2", cost: 0.14 },
];

const ROW_H = 46;
const HEAD_H = 32;
const RUN_MS = 3400;

function CompanyPanel() {
  const reduce = useReducedMotion();
  const phase = usePhase(ROWS.length, RUN_MS);
  const elapsed = useElapsed();

  // everything before `phase` has finished; `phase` itself is running
  const settled = ROWS.slice(0, phase).reduce((n, r) => n + r.cost, 0);
  const spend = useCountUp(settled + ROWS[phase].cost * 0.6, RUN_MS * 0.8);
  const hired = useCountUp(phase + 2, 900);

  return (
    <div className="panel-wrap">
      <motion.div
        className="panel-aura"
        aria-hidden="true"
        animate={reduce ? {} : { scale: [1, 1.06, 1], opacity: [0.45, 0.66, 0.45] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="panel">
        <div className="panel-head">
          <BenchMark size={14} />
          <span className="panel-goal">Launch our new product</span>
          <span className="panel-live">
            <motion.span
              className="dot"
              animate={reduce ? {} : { opacity: [1, 0.25, 1] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
            />
            working · {elapsed}
          </span>
        </div>

        <div className="panel-scroll">
          <div className="panel-table">
            {/* the dispatch marker slides down to whichever task is live */}
            <motion.span
              className="panel-marker"
              aria-hidden="true"
              animate={{ top: HEAD_H + phase * ROW_H + ROW_H / 2 - 4 }}
              transition={{ type: "spring", stiffness: 190, damping: 22 }}
            />

            <div className="tr th">
              <span className="c-task">Task</span>
              <span className="c-worker">Worker</span>
              <span className="c-machine">Machine</span>
              <span className="c-state">State</span>
              <span className="c-cost">Cost</span>
            </div>

            {ROWS.map((r, i) => {
              const state = i < phase ? "done" : i === phase ? "run" : "wait";
              const staffed = state !== "wait";
              return (
                <div className={`tr is-${state}`} key={r.task}>
                  <span className="c-task">{r.task}</span>
                  <span className="c-worker">{staffed ? r.worker : "—"}</span>
                  <span className="c-machine">{staffed ? r.machine : "—"}</span>
                  <span className="c-state">
                    {state === "done" ? "done" : state === "run" ? "running" : "queued"}
                  </span>
                  <span className="c-cost">{staffed ? `$${r.cost.toFixed(2)}` : "—"}</span>
                  {state === "run" && !reduce && (
                    <motion.span
                      className="tr-fill"
                      key={phase}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ duration: RUN_MS / 1000, ease: "linear" }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="panel-foot">
          <span className="floor" aria-hidden="true">
            {ROWS.map((_, i) => (
              <motion.span
                key={i}
                className="floor-slot"
                animate={{
                  opacity: i <= phase ? 1 : 0.18,
                  y: reduce || i !== phase ? 0 : [0, -3, 0],
                }}
                transition={{
                  opacity: { duration: 0.45 },
                  y: { duration: 1.6, repeat: Infinity, ease: "easeInOut" },
                }}
              >
                <PixelCritter size={15} />
              </motion.span>
            ))}
          </span>
          <span>{Math.round(hired)} hired</span>
          <span className="foot-spend">${spend.toFixed(2)} spent</span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  browser beat — an agent using a site the way a person would        */
/* ------------------------------------------------------------------ */

const FIELDS = ["Campaign name", "Audience", "Budget"];

function BrowserBeat() {
  const reduce = useReducedMotion();
  const phase = usePhase(5, 1500); // 0,1,2 fields · 3 submit · 4 saved

  const target = phase < 3 ? phase : 3;
  return (
    <div className="browser" aria-hidden="true">
      <div className="browser-bar">
        <span className="browser-dots"><i /><i /><i /></span>
        <span className="browser-url">app.example.com/campaigns/new</span>
      </div>

      <div className="browser-body">
        {FIELDS.map((f, i) => (
          <div className={`field ${phase > i ? "is-filled" : ""}`} key={f}>
            <span className="field-name">{f}</span>
            <span className="field-box">
              {phase > i && (
                <motion.span
                  className="field-value"
                  initial={reduce ? false : { clipPath: "inset(0 100% 0 0)" }}
                  animate={{ clipPath: "inset(0 0% 0 0)" }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                >
                  {["Product Launch", "Existing customers", "$4,000"][i]}
                </motion.span>
              )}
            </span>
          </div>
        ))}

        <div className={`field-submit ${phase >= 3 ? "is-hit" : ""}`}>
          {phase >= 4 ? "Saved" : "Create campaign"}
        </div>

        {!reduce && (
          <motion.span
            className="cursor"
            animate={{ top: target * 52 + 34, left: target === 3 ? 96 : 210 }}
            transition={{ type: "spring", stiffness: 130, damping: 18 }}
          >
            <svg viewBox="0 0 12 18" width="13" height="19">
              <path d="M1 1l10 9-4.6.6L9 16.4l-2 .9-2.5-5.9L1 14z" />
            </svg>
          </motion.span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  flow — a goal enters, tasks fan out, finished work comes back      */
/* ------------------------------------------------------------------ */

const LANES = ["Engineering", "Operations", "Research"];

function Wire({ delay, tall }: { delay: number; tall?: boolean }) {
  const reduce = useReducedMotion();
  return (
    <div className={`wire ${tall ? "is-tall" : ""}`}>
      {!reduce && (
        <motion.span
          className="comet"
          animate={{ top: ["-34px", "100%"] }}
          transition={{ duration: 0.95, repeat: Infinity, repeatDelay: 4.4, delay, ease: "easeIn" }}
        />
      )}
    </div>
  );
}

function FlowDiagram() {
  const reduce = useReducedMotion();
  return (
    <div className="flow" aria-hidden="true">
      <div className="node">
        <span className="node-kicker">your goal</span>
        Launch our new product
      </div>

      <Wire delay={0} />

      <div className="node is-bench">
        <BenchMark size={15} /> Bench decides the work
      </div>

      <div className="fan">
        <span className="fan-rail" />
        {LANES.map((l, i) => (
          <div className="fan-col" key={l}>
            <Wire delay={1.2 + i * 0.12} />
            <motion.span
              className="lane"
              animate={
                reduce
                  ? {}
                  : {
                      borderColor: ["var(--line)", "var(--teal)", "var(--line)"],
                      color: ["var(--mid)", "var(--ink)", "var(--mid)"],
                    }
              }
              transition={{ duration: 1.7, repeat: Infinity, repeatDelay: 3.6, delay: 2.1 + i * 0.12 }}
            >
              {l}
            </motion.span>
            <Wire delay={3.1 + i * 0.12} />
          </div>
        ))}
        <span className="fan-rail is-low" />
      </div>

      <div className="node is-out">Finished work, back to you</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  lifecycle — one continuous run, not five separate steps            */
/* ------------------------------------------------------------------ */

const STEPS = [
  ["Goal", "You name the outcome"],
  ["Plan", "Bench works out the steps"],
  ["Work", "Agents carry it out"],
  ["Verify", "Checked in a clean run"],
  ["Done", "The result comes back"],
];

function LifecycleTrack() {
  const reduce = useReducedMotion();
  const active = usePhase(STEPS.length, 1500);
  const pct = (active / (STEPS.length - 1)) * 100;

  return (
    <ol className="track">
      <span className="track-rail" aria-hidden="true">
        <motion.span
          className="track-rail-fill"
          animate={{ width: `${reduce ? 100 : pct}%` }}
          transition={{ duration: 0.8, ease: [0.2, 0, 0, 1] }}
        />
      </span>
      {STEPS.map(([name, copy], i) => (
        <li className="step" data-on={i <= active} key={name}>
          <span className="step-dot" />
          <span className="step-name">{name}</span>
          <span className="step-copy">{copy}</span>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------------ */
/*  org — management persists, workers clock in and out                */
/* ------------------------------------------------------------------ */

const DEPTS = [
  { name: "Engineering", crew: 3, line: "Writes, runs and ships software." },
  { name: "Operations", crew: 3, line: "Works through apps like a person." },
  { name: "Research", crew: 2, line: "Digs in and returns findings." },
];

function OrgTree() {
  const reduce = useReducedMotion();
  const beat = usePhase(4, 1900);

  return (
    <div className="org" aria-hidden="true">
      <div className="node is-bench">
        <BenchMark size={15} /> Management
      </div>
      <div className="org-stem" />

      <div className="org-cols">
        <span className="org-rail" />
        {DEPTS.map((d, di) => {
          // the last critter in each dept is the one being hired and dismissed
          const on = (beat + di) % 4 < 2;
          return (
            <div className="dept" key={d.name}>
              <span className="dept-stem" />
              <div className="dept-name">{d.name}</div>
              <div className="crew">
                {Array.from({ length: d.crew }).map((_, i) => {
                  const temp = i === d.crew - 1;
                  return (
                    <motion.span
                      key={i}
                      className={temp ? "crew-temp" : ""}
                      animate={
                        reduce
                          ? {}
                          : temp
                            ? { opacity: on ? 1 : 0.12, scale: on ? 1 : 0.7 }
                            : { y: [0, -2.5, 0] }
                      }
                      transition={
                        temp
                          ? { duration: 0.45, ease: "easeOut" }
                          : { duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: di * 0.3 + i * 0.2 }
                      }
                    >
                      <PixelCritter size={16} />
                    </motion.span>
                  );
                })}
              </div>
              <p className="dept-line">{d.line}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  output — machines reporting back, line by line                     */
/* ------------------------------------------------------------------ */

const OUTPUTS = [
  { tag: "Build", lines: ["npm run build", "compiled in 4.2s", "31 tests passed", "server up on :4173"] },
  { tag: "Operate", lines: ["opened app.example.com", "signed in", "campaign created", "record saved"] },
  { tag: "Deliver", lines: ["landing-page.zip", "preview URL live", "checked in sandbox", "merged"] },
];

/** Each machine reports at its own pace, so the three cards never march in step. */
function OutputCard({ tag, lines, pace }: { tag: string; lines: string[]; pace: number }) {
  const reduce = useReducedMotion();
  const step = usePhase(lines.length + 2, pace);
  const shown = reduce ? lines.length : Math.min(step, lines.length);

  return (
    <div className="out">
      <div className="out-tag">{tag}</div>
      <div className="out-body">
        {lines.map((l, i) => (
          <motion.div
            className="out-line"
            key={l}
            animate={{ opacity: i < shown ? 1 : 0.14, x: i < shown ? 0 : -4 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          >
            <span className="out-mark">{i === 0 ? "›" : "✓"}</span>
            {l}
          </motion.div>
        ))}
        {!reduce && (
          <motion.span
            className="out-caret"
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
          />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  demo notice — shown only when a run would actually fail            */
/* ------------------------------------------------------------------ */

function DemoNotice() {
  const [notice, setNotice] = useState("");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let live = true;
    // A visitor arriving from a shared link should never be told the demo is
    // down because their network hiccuped, so failure here stays silent.
    fetch("/api/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (live && d?.demo_paused && d?.notice) setNotice(String(d.notice));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (!notice || dismissed) return null;

  return (
    <motion.aside
      className="notice"
      role="status"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.6, ease: [0.2, 0, 0, 1] }}
    >
      <span className="notice-dot" aria-hidden="true" />
      <p>{notice}</p>
      <button type="button" onClick={() => setDismissed(true)} aria-label="Dismiss">
        &times;
      </button>
    </motion.aside>
  );
}

/* ------------------------------------------------------------------ */

export function Landing() {
  const { user } = useAuth();
  const go = user ? "/dashboard" : "/login";
  const cta = user ? "Go to dashboard" : "Build your company";

  return (
    <div className="landing">
      <DemoNotice />
      <header className="topbar">
        <span className="brand">
          <BenchMark size={22} />
          <span className="brand-word">Bench</span>
        </span>
        <span className="spacer" />
        <a href="#how" className="nav-link">How it works</a>
        <Link to={go} className="nav-link">{user ? "Dashboard" : "Sign in"}</Link>
      </header>

      {/* hero */}
      <section className="hero">
        <motion.div
          className="hero-copy"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.2, 0, 0, 1] }}
        >
          <h1>Give your company a goal.<br />Let it get to work.</h1>
          <p className="lede">A workforce of AI agents that plans, works, and hands back the result.</p>
          <div className="cta-row">
            <Link to={go} className="btn btn-solid">{cta}</Link>
            <a href="#how" className="btn btn-ghost">See how it works</a>
          </div>
          <div className="hero-proof" aria-label="Bench capabilities">
            <span>Browser work</span>
            <span>Disposable machines</span>
            <span>Policy checks</span>
          </div>
        </motion.div>

        <motion.div
          className="hero-figure"
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.25, ease: [0.2, 0, 0, 1] }}
        >
          <CompanyPanel />
        </motion.div>
      </section>

      {/* thesis */}
      <section className="sec">
        <div className="head">
          <h2>It doesn&rsquo;t need an integration.<br />It needs a browser and a login.</h2>
          <p>If a person can do the job on a website, so can the agent &mdash; on day one.</p>
        </div>
        <figure className="fig"><BrowserBeat /></figure>
      </section>

      {/* the model */}
      <section className="sec">
        <div className="head">
          <h2>Not an assistant. A company.</h2>
          <p>You set the direction. Bench decides what work exists and hires for it.</p>
        </div>
        <figure className="fig"><FlowDiagram /></figure>
      </section>

      {/* lifecycle */}
      <section className="sec" id="how">
        <div className="head">
          <h2>Work moves. You don&rsquo;t.</h2>
          <p>Every task gets the right agent, its own machine, and a clean run before anything comes back.</p>
        </div>
        <figure className="fig fig-wide"><LifecycleTrack /></figure>
      </section>

      {/* workforce */}
      <section className="sec">
        <div className="head">
          <h2>A workforce that scales with the work.</h2>
        </div>
        <figure className="fig"><OrgTree /></figure>
        <div className="pair">
          <div>
            <h3>Management persists</h3>
            <p>A small standing team holds the goals, the budget and the standards. It decides what work exists and whether the result is good enough.</p>
          </div>
          <div>
            <h3>Workers are hired per task</h3>
            <p>A worker is spawned with one job, one machine, and only the access that job needs. It hands back its output and is dismissed with the machine.</p>
          </div>
        </div>
      </section>

      {/* execution */}
      <section className="sec sec-dark">
        <div className="head">
          <h2>The work doesn&rsquo;t stop at the answer.</h2>
          <p>Agents write code, run it, move through apps, and prove the output works before it ships.</p>
        </div>
        <figure className="fig fig-wide">
          <div className="out-grid">
            {OUTPUTS.map((o, i) => (
              <OutputCard key={o.tag} tag={o.tag} lines={o.lines} pace={980 + i * 190} />
            ))}
          </div>
        </figure>
        <p className="claim">Every dispatch is policy-checked. Every machine is disposable.</p>
      </section>

      {/* close */}
      <section className="close">
        <BenchMark size={40} />
        <h2>Give your company something to do.</h2>
        <Link to={go} className="btn btn-solid">{cta}</Link>
      </section>

      <footer className="foot">
        <span className="brand">
          <BenchMark size={16} />
          <span className="brand-word">Bench</span>
        </span>
        <span className="foot-note">A company that runs on agents.</span>
      </footer>
    </div>
  );
}
