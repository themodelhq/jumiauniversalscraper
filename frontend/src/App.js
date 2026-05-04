import React, { useState, useRef, useCallback, useEffect, createContext, useContext } from "react";

// ─── CONFIG ─────────────────────────────────────────────────────────────────
// Replace with your Render backend URL after deploying
const API = process.env.REACT_APP_API_URL || "https://your-api.onrender.com";

// ─── THEME CONTEXT ────────────────────────────────────────────────────────────
const ThemeCtx = createContext(false); // false = light (default)
const useTheme = () => useContext(ThemeCtx);

// ─── THEME FACTORY ────────────────────────────────────────────────────────────
// Light (isDark=false): white background, dark text — clean Jumia day style.
// Dark (isDark=true): near-black background, light text.
const makeT = (isDark) => ({
  orange:      "#F37218",
  orangeDeep:  "#D95F00",
  orangeLight: "#FFF3E8",
  orangeGlow:  isDark ? "rgba(243,114,24,0.15)" : "rgba(243,114,24,0.10)",
  dark:        isDark ? "#0D0D0D" : "#F5F5F5",
  darkCard:    isDark ? "#161616" : "#FFFFFF",
  darkBorder:  isDark ? "#252525" : "#E2E2E2",
  mid:         isDark ? "#2A2A2A" : "#F0F0F0",
  textPrimary: isDark ? "#F5F5F5" : "#111111",
  textSecond:  isDark ? "#999999" : "#555555",
  textMuted:   isDark ? "#555555" : "#999999",
  success:     "#22C55E",
  error:       "#EF4444",
  white:       "#FFFFFF",
  headerBg:    isDark ? "rgba(13,13,13,0.92)" : "rgba(255,255,255,0.95)",
  headerBorder:isDark ? "#252525" : "#E2E2E2",
});

// Convenience hook — returns T tokens for current theme
const useT = () => makeT(useTheme());

// Module-level fallback (used by Icon default color before hooks are available)
const T = makeT(false);

// ─── GLOBAL STYLES ────────────────────────────────────────────────────────
const GlobalStyle = ({ isDark }) => {
  const t = makeT(isDark);
  return (
  <style>{`
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'DM Sans', sans-serif;
      background: ${t.dark};
      color: ${t.textPrimary};
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      transition: background 0.25s, color 0.25s;
    }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: ${t.dark}; }
    ::-webkit-scrollbar-thumb { background: ${t.mid}; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: ${t.orange}; }
    input, textarea, select { font-family: inherit; }
    button { cursor: pointer; font-family: inherit; }
    a { color: inherit; text-decoration: none; }
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(20px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes pulse  { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    @keyframes spin   { to { transform: rotate(360deg); } }
    @keyframes shimmer {
      0%   { background-position: -400px 0; }
      100% { background-position: 400px 0; }
    }
    @keyframes growBar { from { width: 0; } to { width: var(--w); } }
    .fade-up { animation: fadeUp  0.45s ease both; }
    .fade-in { animation: fadeIn  0.3s  ease both; }
    .spin    { animation: spin    0.8s  linear infinite; }
    .pulse   { animation: pulse   1.4s  ease-in-out infinite; }
  `}</style>
  );
};

// ─── ATOMS ──────────────────────────────────────────────────────────────────

const OrangeBtn = ({ children, onClick, disabled, style, small, outline, loading }) => { const T = useT(); return (
  <button
    onClick={onClick}
    disabled={disabled || loading}
    style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      padding: small ? "8px 18px" : "13px 28px",
      background: outline ? "transparent" : disabled ? T.textMuted : T.orange,
      color: outline ? T.orange : T.white,
      border: `2px solid ${outline ? T.orange : "transparent"}`,
      borderRadius: 8,
      fontSize: small ? 13 : 15,
      fontFamily: "'Syne', sans-serif",
      fontWeight: 700,
      letterSpacing: 0.3,
      transition: "all 0.2s",
      opacity: disabled ? 0.5 : 1,
      whiteSpace: "nowrap",
      ...style,
    }}
    onMouseEnter={e => { if (!disabled) e.currentTarget.style.background = outline ? T.orangeGlow : T.orangeDeep; }}
    onMouseLeave={e => { if (!disabled) e.currentTarget.style.background = outline ? "transparent" : T.orange; }}
  >
    {loading && <span className="spin" style={{ width: 16, height: 16, border: `2px solid rgba(255,255,255,0.3)`, borderTopColor: T.white, borderRadius: "50%", display: "inline-block" }} />}
    {children}
  </button>
); }

const Card = ({ children, style, className }) => { const T = useT(); return (
  <div className={className} style={{
    background: T.darkCard,
    border: `1px solid ${T.darkBorder}`,
    borderRadius: 16,
    padding: 28,
    ...style,
  }}>
    {children}
  </div>
); }

const Label = ({ children }) => { const T = useT(); return (
  <div style={{ fontFamily: "'Syne',sans-serif", fontSize: 11, fontWeight: 700, letterSpacing: 2, color: T.textSecond, textTransform: "uppercase", marginBottom: 8 }}>
    {children}
  </div>
); }

const Input = ({ value, onChange, placeholder, style, ...rest }) => { const T = useT(); return (
  <input
    value={value}
    onChange={onChange}
    placeholder={placeholder}
    style={{
      width: "100%", padding: "12px 16px",
      background: T.mid, border: `1px solid ${T.darkBorder}`,
      borderRadius: 8, color: T.textPrimary, fontSize: 14,
      outline: "none", transition: "border-color 0.2s",
      ...style,
    }}
    onFocus={e => e.target.style.borderColor = T.orange}
    onBlur={e => e.target.style.borderColor = T.darkBorder}
    {...rest}
  />
); }

const Pill = ({ children, active, onClick }) => { const T = useT(); return (
  <button onClick={onClick} style={{
    padding: "6px 16px", borderRadius: 20, fontSize: 13, fontWeight: 600,
    border: `1.5px solid ${active ? T.orange : T.darkBorder}`,
    background: active ? T.orangeGlow : "transparent",
    color: active ? T.orange : T.textSecond,
    transition: "all 0.18s",
  }}>
    {children}
  </button>
); }

const Badge = ({ children, color }) => { const T = useT(); return (
  <span style={{
    display: "inline-block", padding: "3px 10px", borderRadius: 20,
    fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
    background: color === "success" ? "rgba(34,197,94,0.15)" :
                color === "error"   ? "rgba(239,68,68,0.15)"  :
                color === "orange"  ? T.orangeGlow : "rgba(255,255,255,0.06)",
    color: color === "success" ? T.success : color === "error" ? T.error :
           color === "orange" ? T.orange : T.textSecond,
  }}>
    {children}
  </span>
); }

const Spinner = ({ size = 22 }) => { const T = useT(); return (
  <div className="spin" style={{
    width: size, height: size, borderRadius: "50%",
    border: `2.5px solid rgba(243,114,24,0.2)`,
    borderTopColor: T.orange,
  }} />
); }

const ProgressBar = ({ value }) => { const T = useT(); return (
  <div style={{ width: "100%", height: 6, background: T.mid, borderRadius: 3, overflow: "hidden" }}>
    <div style={{
      height: "100%", borderRadius: 3,
      background: `linear-gradient(90deg, ${T.orange}, ${T.orangeDeep})`,
      width: `${value}%`, transition: "width 0.4s ease",
    }} />
  </div>
); }

const Divider = () => { const T = useT(); return (
  <div style={{ borderTop: `1px solid ${T.darkBorder}`, margin: "24px 0" }} />
); }

// ─── ICONS ──────────────────────────────────────────────────────────────────
const Icon = ({ d, size = 18, color = '#999999', style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d={d} />
  </svg>
);

const Icons = {
  link:     "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
  upload:   "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
  list:     "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  check:    "M20 6 9 17l-5-5",
  x:        "M18 6 6 18M6 6l12 12",
  search:   "M11 17.25a6.25 6.25 0 1 1 0-12.5 6.25 6.25 0 0 1 0 12.5zM16 16l4.5 4.5",
  zap:      "M13 2 3 14h9l-1 8 10-12h-9l1-8z",
  box:      "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z",
  tag:      "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01",
  eye:      "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  copy:     "M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2M8 4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2M8 4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2",
  grid:     "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
};

// ─── HEADER ─────────────────────────────────────────────────────────────────
const Header = ({ isDark, onToggle }) => { const T = useT(); return (
  <header style={{
    position: "sticky", top: 0, zIndex: 100,
    background: T.headerBg, backdropFilter: "blur(16px)",
    borderBottom: `1px solid ${T.headerBorder}`,
    padding: "0 32px", height: 64,
    display: "flex", alignItems: "center", justifyContent: "space-between",
    transition: "background 0.25s, border-color 0.25s",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: T.orange,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon d={Icons.zap} size={18} color={T.white} />
      </div>
      <div>
        <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 800, fontSize: 18, color: T.textPrimary, lineHeight: 1 }}>
          Scraper<span style={{ color: T.orange }}>Pro</span>
        </div>
        <div style={{ fontSize: 10, color: T.textMuted, letterSpacing: 1.5, textTransform: "uppercase" }}>
          Universal Product Scraper
        </div>
      </div>
    </div>
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <Badge color="success">● Live</Badge>
      <div style={{ fontSize: 12, color: T.textMuted, marginLeft: 8 }}>
        Powered by <span style={{ color: T.orange }}>FastAPI</span>
      </div>
      {/* Theme toggle */}
      <button
        onClick={onToggle}
        title={isDark ? "Switch to Light theme" : "Switch to Dark theme"}
        style={{
          marginLeft: 8,
          width: 44, height: 26, borderRadius: 13, border: "none",
          background: isDark ? "#3A3A3A" : "#E0E0E0",
          position: "relative", cursor: "pointer",
          transition: "background 0.25s", flexShrink: 0,
        }}
      >
        <div style={{
          position: "absolute", top: 3,
          left: isDark ? 21 : 3,
          width: 20, height: 20, borderRadius: "50%",
          background: isDark ? T.orange : "#FFFFFF",
          boxShadow: "0 1px 4px rgba(0,0,0,0.25)",
          transition: "left 0.22s, background 0.22s",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11,
        }}>
          {isDark ? "🌙" : "☀️"}
        </div>
      </button>
    </div>
  </header>
); }

// ─── HERO ────────────────────────────────────────────────────────────────────
const Hero = () => { const T = useT(); return (
  <div style={{
    padding: "72px 32px 48px", textAlign: "center", position: "relative",
    overflow: "hidden",
  }}>
    {/* Background glow */}
    <div style={{
      position: "absolute", top: -60, left: "50%", transform: "translateX(-50%)",
      width: 600, height: 300,
      background: `radial-gradient(ellipse, ${T.orangeGlow} 0%, transparent 70%)`,
      pointerEvents: "none",
    }} />
    <div className="fade-up" style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      padding: "6px 16px", borderRadius: 20,
      border: `1px solid ${T.darkBorder}`,
      background: T.darkCard,
      fontSize: 12, color: T.textSecond, marginBottom: 24,
      letterSpacing: 1, textTransform: "uppercase",
    }}>
      <Icon d={Icons.tag} size={12} color={T.orange} />
      Supports Amazon · Noon · GSMArena · Any Website
    </div>
    <h1 className="fade-up" style={{
      fontFamily: "'Syne',sans-serif", fontSize: "clamp(36px,6vw,72px)",
      fontWeight: 800, lineHeight: 1.05, color: T.textPrimary,
      animationDelay: "0.05s",
    }}>
      Scrape Products.<br />
      <span style={{ color: T.orange }}>Export Instantly.</span>
    </h1>
    <p className="fade-up" style={{
      marginTop: 20, fontSize: 17, color: T.textSecond, maxWidth: 560, margin: "20px auto 0",
      lineHeight: 1.7, animationDelay: "0.1s",
    }}>
      Extract product data from any website and export to Jumia BOBTemplate,
      VendorCenter, or raw CSV — in seconds.
    </p>
  </div>
); }

// ─── STATS BAR ───────────────────────────────────────────────────────────────
const StatsBar = ({ jobHistory }) => {
  const T = useT();
  const total   = jobHistory.reduce((s, j) => s + (j.total || 0), 0);
  const success = jobHistory.reduce((s, j) => s + (j.completed || 0), 0);
  const jobs    = jobHistory.length;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(3,1fr)",
      gap: 1, background: T.darkBorder,
      margin: "0 32px 32px", borderRadius: 12, overflow: "hidden",
    }}>
      {[
        { label: "Jobs run", value: jobs, icon: Icons.grid },
        { label: "URLs processed", value: total, icon: Icons.link },
        { label: "Products scraped", value: success, icon: Icons.box },
      ].map(({ label, value, icon }) => (
        <div key={label} style={{
          background: T.darkCard, padding: "20px 28px",
          display: "flex", alignItems: "center", gap: 16,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10,
            background: T.orangeGlow,
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <Icon d={icon} size={20} color={T.orange} />
          </div>
          <div>
            <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 800, fontSize: 26, color: T.white }}>
              {value}
            </div>
            <div style={{ fontSize: 12, color: T.textSecond }}>{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ─── FORMAT SELECTOR ─────────────────────────────────────────────────────────
const FormatSelector = ({ value, onChange }) => { const T = useT(); return (
  <div>
    <Label>Export Format</Label>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {[
        { v: "bob",    label: "BOBTemplate CSV",        desc: "Jumia BOB" },
        { v: "vendor", label: "VendorCenter XLSX",      desc: "Jumia Vendor" },
        { v: "csv",    label: "Raw CSV",                desc: "All fields" },
      ].map(({ v, label, desc }) => (
        <button key={v} onClick={() => onChange(v)} style={{
          padding: "10px 18px", borderRadius: 10, cursor: "pointer",
          border: `1.5px solid ${value === v ? T.orange : T.darkBorder}`,
          background: value === v ? T.orangeGlow : T.mid,
          color: value === v ? T.orange : T.textSecond,
          transition: "all 0.18s", textAlign: "left",
        }}>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 13 }}>{label}</div>
          <div style={{ fontSize: 11, color: value === v ? T.orange : T.textMuted, marginTop: 2 }}>{desc}</div>
        </button>
      ))}
    </div>
  </div>
); } ─────────────────────────────────────────────────────────────
const ResultCard = ({ result, download, index }) => {
  const T = useT();
  const [expanded, setExpanded] = useState(false);
  const imgs = (result.Images || "").split(/[|,]/).map(u => u.trim()).filter(Boolean);
  const hasError = !!result.Error;
  return (
    <div className="fade-up" style={{
      border: `1px solid ${hasError ? "rgba(239,68,68,0.3)" : T.darkBorder}`,
      borderRadius: 12, overflow: "hidden", background: T.darkCard,
      animationDelay: `${index * 0.04}s`,
    }}>
      <div style={{ padding: "16px 20px", display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* Thumbnail */}
        <div style={{
          width: 64, height: 64, borderRadius: 8, flexShrink: 0, overflow: "hidden",
          background: T.mid, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {imgs[0]
            ? <img src={imgs[0]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }}
                onError={e => e.target.style.display = "none"} />
            : <Icon d={Icons.box} size={24} color={T.textMuted} />}
        </div>
        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
            <Badge color={hasError ? "error" : "success"}>{hasError ? "Error" : "Scraped"}</Badge>
            {result.Website && <Badge>{result.Website}</Badge>}
          </div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 15, color: T.white, marginBottom: 4 }}>
            {result["Product Name"] || result.URL?.substring(0, 60) || "Unknown Product"}
          </div>
          <div style={{ fontSize: 13, color: T.textSecond, display: "flex", gap: 16, flexWrap: "wrap" }}>
            {result.Brand && <span><span style={{ color: T.textMuted }}>Brand:</span> {result.Brand}</span>}
            {result.Price && <span style={{ color: T.orange, fontWeight: 600 }}>{result.Price} {result.Currency}</span>}
            {result.SKU && <span><span style={{ color: T.textMuted }}>SKU:</span> {result.SKU}</span>}
          </div>
          {hasError && <div style={{ marginTop: 6, fontSize: 12, color: T.error }}>{result.Error}</div>}
        </div>
        {/* Actions */}
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button onClick={() => setExpanded(x => !x)} style={{
            width: 32, height: 32, borderRadius: 6, border: `1px solid ${T.darkBorder}`,
            background: "transparent", color: T.textSecond, display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Icon d={expanded ? Icons.x : Icons.eye} size={14} color={T.textSecond} />
          </button>
          {download && (
            <a href={`${API}${download}`} download style={{
              width: 32, height: 32, borderRadius: 6,
              background: T.orange, color: T.white,
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "none",
            }}>
              <Icon d={Icons.download} size={14} color={T.white} />
            </a>
          )}
        </div>
      </div>
      {/* Expanded detail */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${T.darkBorder}`, padding: "16px 20px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 12 }}>
            {[
              ["Category", result.Category],
              ["Rating", result.Rating],
              ["Reviews", result["Reviews Count"]],
              ["Availability", result.Availability],
              ["GTIN", result.GTIN],
              ["URL", result.URL],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={k} style={{ background: T.mid, padding: "10px 14px", borderRadius: 8 }}>
                <div style={{ fontSize: 10, color: T.textMuted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 4 }}>{k}</div>
                <div style={{ fontSize: 12, color: T.textPrimary, wordBreak: "break-all" }}>{String(v).substring(0, 120)}</div>
              </div>
            ))}
          </div>
          {result["Key Features"] && (
            <div style={{ marginTop: 12, background: T.mid, padding: "12px 14px", borderRadius: 8 }}>
              <div style={{ fontSize: 10, color: T.textMuted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 6 }}>Key Features</div>
              <div style={{ fontSize: 12, color: T.textPrimary, lineHeight: 1.7 }}>{result["Key Features"]}</div>
            </div>
          )}
          {imgs.length > 0 && (
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              {imgs.slice(0, 6).map((src, i) => (
                <img key={i} src={src} alt="" style={{
                  width: 72, height: 72, objectFit: "cover", borderRadius: 8,
                  border: `1px solid ${T.darkBorder}`,
                }} onError={e => e.target.style.display = "none"} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── JOB TRACKER ─────────────────────────────────────────────────────────────
const useJobPoller = (jobId, onDone) => {
  const T = useT();
  const [job, setJob] = useState(null);
  const timer = useRef(null);
  useEffect(() => {
    if (!jobId) return;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/job/${jobId}`);
        const data = await res.json();
        setJob(data);
        if (data.status === "done" || data.status === "error") {
          clearInterval(timer.current);
          onDone && onDone(data);
        }
      } catch (_) {}
    };
    poll();
    timer.current = setInterval(poll, 1200);
    return () => clearInterval(timer.current);
  }, [jobId]);
  return job;
};


// ─── BRAND SEARCH PANEL ───────────────────────────────────────────────────────
const BrandSearchPanel = ({ onResult, onJobStart }) => {
  const T = useT();
  const [mode, setMode] = useState("single"); // "single" | "batch"
  const [query, setQuery] = useState("");
  const [batchText, setBatchText] = useState("");
  const [fmt, setFmt] = useState("bob");
  const [delay, setDelay] = useState(2);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const queries = batchText.split("\n").map(q => q.trim()).filter(Boolean);

  const submitSingle = async () => {
    if (!query.trim()) { setErr("Please enter a product query"); return; }
    setErr(""); setLoading(true);
    try {
      const res = await fetch(`${API}/scrape/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), format: fmt }),
      });
      const data = await res.json();
      if (!res.ok) { setErr(data.detail || "Failed"); return; }
      onResult({ ...data, format: fmt });
    } catch (e) { setErr("Network error — is the backend running?"); }
    finally { setLoading(false); }
  };

  const submitBatch = async () => {
    if (!queries.length) { setErr("Enter at least one query (one per line)"); return; }
    setErr(""); setLoading(true);
    try {
      const res = await fetch(`${API}/scrape/batch-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queries, format: fmt, delay }),
      });
      const data = await res.json();
      if (!res.ok) { setErr(data.detail || "Failed"); return; }
      onJobStart({ job_id: data.job_id, total: data.total, format: fmt });
    } catch (e) { setErr("Network error"); }
    finally { setLoading(false); }
  };

  return (
    <Card>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: T.orangeGlow, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon d={Icons.search} size={18} color={T.orange} />
        </div>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 16, color: T.white }}>Brand Website Search</div>
          <div style={{ fontSize: 12, color: T.textSecond }}>Search brand official sites by product name — no URL needed</div>
        </div>
      </div>

      {/* Format: hint */}
      <div style={{ padding: "10px 16px", background: T.orangeGlow, borderRadius: 8, border: `1px solid rgba(243,114,24,0.25)`, marginBottom: 20, fontSize: 12, color: T.orange }}>
        <strong>Format:</strong> Brand · Model · Colour · Storage · Model Code<br />
        <span style={{ color: T.textSecond }}>e.g. <code style={{ color: T.white }}>Samsung Galaxy A06 Black 128GB SM-A065FZKHAFB</code></span>
      </div>

      {/* Mode toggle */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {[["single","Single Query"],["batch","Batch Queries"]].map(([v,l]) => (
          <Pill key={v} active={mode===v} onClick={() => setMode(v)}>{l}</Pill>
        ))}
      </div>

      {mode === "single" ? (
        <>
          <Label>Product Query</Label>
          <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
            <Input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Samsung Galaxy A06 Black 128GB SM-A065FZKHAFB"
              onKeyDown={e => e.key === "Enter" && submitSingle()}
              style={{ flex: 1 }} />
            <OrangeBtn onClick={submitSingle} loading={loading} disabled={loading}>
              <Icon d={Icons.search} size={16} color={T.white} />
              Search
            </OrangeBtn>
          </div>
        </>
      ) : (
        <>
          <Label>Product Queries (one per line)</Label>
          <textarea
            value={batchText} onChange={e => setBatchText(e.target.value)}
            placeholder={"Samsung Galaxy A06 Black 128GB\nHisense 43 inch TV 43A4N\nLG Refrigerator 308L GN-B392PLGB"}
            rows={6}
            style={{ width:"100%", padding:"12px 16px", background:T.mid, border:`1px solid ${T.darkBorder}`,
              borderRadius:8, color:T.textPrimary, fontSize:13, resize:"vertical", outline:"none",
              marginBottom:20, fontFamily:"inherit", lineHeight:1.7 }}
            onFocus={e => e.target.style.borderColor = T.orange}
            onBlur={e => e.target.style.borderColor = T.darkBorder}
          />
          <div style={{ marginBottom: 20 }}>
            <Label>Delay between searches (sec)</Label>
            <div style={{ display: "flex", gap: 6 }}>
              {[1, 2, 3, 5].map(d => (
                <Pill key={d} active={delay===d} onClick={() => setDelay(d)}>{d}s</Pill>
              ))}
            </div>
          </div>
        </>
      )}

      <FormatSelector value={fmt} onChange={setFmt} />

      {mode === "batch" && (
        <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 13, color: T.textSecond }}>
            {queries.length > 0 ? <><span style={{ color: T.orange, fontWeight: 600 }}>{queries.length}</span> quer{queries.length !== 1 ? "ies" : "y"} ready</> : "No queries"}
          </div>
          <OrangeBtn onClick={submitBatch} loading={loading} disabled={loading || !queries.length}>
            <Icon d={Icons.zap} size={16} color={T.white} />
            Start Batch Search
          </OrangeBtn>
        </div>
      )}

      {err && <div style={{ marginTop: 14, padding:"10px 14px", background:"rgba(239,68,68,0.1)", border:"1px solid rgba(239,68,68,0.3)", borderRadius:8, fontSize:13, color:T.error }}>{err}</div>}
    </Card>
  );
};


// ─── SINGLE URL PANEL ────────────────────────────────────────────────────────
const SingleURLPanel = ({ onResult }) => {
  const T = useT();
  const [url, setUrl] = useState("");
  const [fmt, setFmt] = useState("bob");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!url.trim()) { setErr("Please enter a URL"); return; }
    setErr(""); setLoading(true);
    try {
      const res = await fetch(`${API}/scrape/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), format: fmt }),
      });
      const data = await res.json();
      if (!res.ok) { setErr(data.detail || "Failed"); return; }
      onResult({ ...data, format: fmt });
    } catch (e) { setErr("Network error — is the backend running?"); }
    finally { setLoading(false); }
  };

  return (
    <Card>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: T.orangeGlow, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon d={Icons.link} size={18} color={T.orange} />
        </div>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 16, color: T.white }}>Single URL Scraper</div>
          <div style={{ fontSize: 12, color: T.textSecond }}>Paste any product URL and export instantly</div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.amazon.com/dp/..." onKeyDown={e => e.key === "Enter" && submit()} style={{ flex: 1 }} />
        <OrangeBtn onClick={submit} loading={loading} disabled={loading}>
          <Icon d={Icons.search} size={16} color={T.white} />
          Scrape
        </OrangeBtn>
      </div>
      <FormatSelector value={fmt} onChange={setFmt} />
      {err && <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, fontSize: 13, color: T.error }}>{err}</div>}
    </Card>
  );
};

// ─── BATCH URL PANEL ──────────────────────────────────────────────────────────
const BatchURLPanel = ({ onJobStart }) => {
  const T = useT();
  const [text, setText] = useState("");
  const [fmt, setFmt] = useState("bob");
  const [delay, setDelay] = useState(1.5);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const urls = text.split("\n").map(u => u.trim()).filter(u => u.startsWith("http"));

  const submit = async () => {
    if (!urls.length) { setErr("Enter at least one valid URL (one per line)"); return; }
    setErr(""); setLoading(true);
    try {
      const res = await fetch(`${API}/scrape/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls, format: fmt, delay }),
      });
      const data = await res.json();
      if (!res.ok) { setErr(data.detail || "Failed"); return; }
      onJobStart({ job_id: data.job_id, total: data.total, format: fmt });
    } catch (e) { setErr("Network error"); }
    finally { setLoading(false); }
  };

  return (
    <Card>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: T.orangeGlow, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon d={Icons.list} size={18} color={T.orange} />
        </div>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 16, color: T.white }}>Batch URL Scraper</div>
          <div style={{ fontSize: 12, color: T.textSecond }}>Paste URLs one per line — runs in background</div>
        </div>
      </div>
      <Label>Product URLs (one per line)</Label>
      <textarea
        value={text} onChange={e => setText(e.target.value)}
        placeholder={"https://www.amazon.com/dp/B0...\nhttps://www.noon.com/...\nhttps://www.gsmarena.com/..."}
        rows={6}
        style={{
          width: "100%", padding: "12px 16px",
          background: T.mid, border: `1px solid ${T.darkBorder}`,
          borderRadius: 8, color: T.textPrimary, fontSize: 13,
          resize: "vertical", outline: "none", marginBottom: 20, fontFamily: "inherit", lineHeight: 1.7,
        }}
        onFocus={e => e.target.style.borderColor = T.orange}
        onBlur={e => e.target.style.borderColor = T.darkBorder}
      />
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <FormatSelector value={fmt} onChange={setFmt} />
        </div>
        <div>
          <Label>Delay between requests (sec)</Label>
          <div style={{ display: "flex", gap: 6 }}>
            {[0.5, 1, 1.5, 2, 3].map(d => (
              <Pill key={d} active={delay === d} onClick={() => setDelay(d)}>{d}s</Pill>
            ))}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, color: T.textSecond }}>
          {urls.length > 0 ? <><span style={{ color: T.orange, fontWeight: 600 }}>{urls.length}</span> URL{urls.length !== 1 ? "s" : ""} ready</> : "No valid URLs detected"}
        </div>
        <OrangeBtn onClick={submit} loading={loading} disabled={loading || !urls.length}>
          <Icon d={Icons.zap} size={16} color={T.white} />
          Start Batch
        </OrangeBtn>
      </div>
      {err && <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, fontSize: 13, color: T.error }}>{err}</div>}
    </Card>
  );
};

// ─── FILE UPLOAD PANEL ────────────────────────────────────────────────────────
const FileUploadPanel = ({ onJobStart }) => {
  const T = useT();
  const [file, setFile] = useState(null);
  const [fmt, setFmt] = useState("bob");
  const [delay, setDelay] = useState(1.5);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [drag, setDrag] = useState(false);
  const inputRef = useRef();

  const handleFile = f => {
    if (f && (f.name.endsWith(".csv") || f.name.endsWith(".xlsx") || f.name.endsWith(".xls"))) {
      setFile(f); setErr("");
    } else {
      setErr("Please select a CSV or Excel file");
    }
  };

  const submit = async () => {
    if (!file) { setErr("Please select a file"); return; }
    setErr(""); setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("format", fmt);
    fd.append("delay", delay);
    try {
      const res = await fetch(`${API}/scrape/file`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) { setErr(data.detail || "Failed"); return; }
      onJobStart({ job_id: data.job_id, total: data.total, format: fmt });
      setFile(null);
    } catch (e) { setErr("Network error"); }
    finally { setLoading(false); }
  };

  return (
    <Card>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: T.orangeGlow, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon d={Icons.upload} size={18} color={T.orange} />
        </div>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 16, color: T.white }}>File Upload Scraper</div>
          <div style={{ fontSize: 12, color: T.textSecond }}>Upload CSV/Excel with a URL column</div>
        </div>
      </div>
      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
        style={{
          border: `2px dashed ${drag ? T.orange : file ? T.success : T.darkBorder}`,
          borderRadius: 12, padding: "32px 20px", textAlign: "center",
          cursor: "pointer", marginBottom: 20, transition: "all 0.2s",
          background: drag ? T.orangeGlow : "transparent",
        }}
      >
        <input ref={inputRef} type="file" accept=".csv,.xls,.xlsx" style={{ display: "none" }}
          onChange={e => handleFile(e.target.files[0])} />
        {file ? (
          <>
            <Icon d={Icons.check} size={32} color={T.success} style={{ margin: "0 auto 10px" }} />
            <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, color: T.success }}>{file.name}</div>
            <div style={{ fontSize: 12, color: T.textSecond, marginTop: 4 }}>{(file.size / 1024).toFixed(1)} KB</div>
          </>
        ) : (
          <>
            <Icon d={Icons.upload} size={32} color={T.textMuted} style={{ margin: "0 auto 10px" }} />
            <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 600, color: T.textSecond }}>Drop CSV / Excel here</div>
            <div style={{ fontSize: 12, color: T.textMuted, marginTop: 4 }}>or click to browse — must have a URL column</div>
          </>
        )}
      </div>
      <div style={{ marginBottom: 20 }}>
        <FormatSelector value={fmt} onChange={setFmt} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {file && (
          <button onClick={() => setFile(null)} style={{ background: "none", border: "none", color: T.textMuted, fontSize: 13 }}>
            ✕ Clear file
          </button>
        )}
        <OrangeBtn onClick={submit} loading={loading} disabled={loading || !file} style={{ marginLeft: "auto" }}>
          <Icon d={Icons.upload} size={16} color={T.white} />
          Upload & Scrape
        </OrangeBtn>
      </div>
      {err && <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, fontSize: 13, color: T.error }}>{err}</div>}
    </Card>
  );
};

// ─── JOB PROGRESS PANEL ───────────────────────────────────────────────────────
const JobProgressPanel = ({ jobId, onDone }) => {
  const T = useT();
  const job = useJobPoller(jobId, onDone);
  if (!job) return (
    <Card style={{ textAlign: "center", padding: 40 }}>
      <Spinner size={32} />
      <div style={{ marginTop: 16, color: T.textSecond }}>Connecting to job {jobId}…</div>
    </Card>
  );
  const done = job.status === "done";
  const err = job.status === "error";
  return (
    <Card className="fade-in">
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: done ? "rgba(34,197,94,0.15)" : T.orangeGlow, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {done ? <Icon d={Icons.check} size={20} color={T.success} /> : err ? <Icon d={Icons.x} size={20} color={T.error} /> : <Spinner size={20} />}
        </div>
        <div>
          <div style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 16, color: T.white }}>
            {done ? "Scraping Complete!" : err ? "Job Failed" : "Scraping in progress…"}
          </div>
          <div style={{ fontSize: 12, color: T.textSecond }}>Job ID: {jobId}</div>
        </div>
        {done && job.download_url && (
          <a href={`${API}${job.download_url}`} download
            style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 20px", borderRadius: 8, background: T.orange, color: T.white, fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 14 }}>
            <Icon d={Icons.download} size={16} color={T.white} />
            Download File
          </a>
        )}
      </div>
      <div style={{ marginBottom: 12 }}>
        <ProgressBar value={job.progress} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, color: T.textSecond }}>{job.message}</div>
        <div style={{ fontSize: 13, color: T.orange, fontFamily: "'Syne',sans-serif", fontWeight: 700 }}>
          {job.completed}/{job.total} products
        </div>
      </div>
      {/* Live results preview */}
      {job.results && job.results.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Label>Live Results Preview</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 320, overflowY: "auto" }}>
            {job.results.slice(-5).reverse().map((r, i) => (
              <div key={i} style={{
                display: "flex", gap: 12, alignItems: "center",
                padding: "10px 14px", background: T.mid, borderRadius: 8,
              }}>
                <Badge color={r.Error ? "error" : "success"}>{r.Error ? "✗" : "✓"}</Badge>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: T.textPrimary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r["Product Name"] || r.URL}
                  </div>
                  {r.Error && <div style={{ fontSize: 11, color: T.error }}>{r.Error}</div>}
                </div>
                {r.Brand && <Badge>{r.Brand}</Badge>}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

// ─── SETUP GUIDE ──────────────────────────────────────────────────────────────
// ─── MAIN APP ────────────────────────────────────────────────────────────────
export default function App() {
  const [isDark, setIsDark] = useState(false); // light theme default
  const T = makeT(isDark);
  const [tab, setTab] = useState("single");
  const [singleResult, setSingleResult] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [completedJob, setCompletedJob] = useState(null);
  const [jobHistory, setJobHistory] = useState([]);
  const resultsRef = useRef();

  const handleSingleResult = useCallback(data => {
    setSingleResult(data);
    setJobHistory(h => [{ ...data, completed: 1, total: 1 }, ...h]);
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
  }, []);

  const handleJobStart = useCallback(data => {
    setActiveJobId(data.job_id);
    setCompletedJob(null);
    setTab("progress");
    setJobHistory(h => [data, ...h]);
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
  }, []);

  const handleJobDone = useCallback(job => {
    setCompletedJob(job);
    setJobHistory(h => h.map(j => j.job_id === job.id ? job : j));
  }, []);

  const tabs = [
    { id: "single",   label: "Single URL",   icon: Icons.link   },
    { id: "batch",    label: "Batch URLs",   icon: Icons.list   },
    { id: "file",     label: "File Upload",  icon: Icons.upload },
    { id: "query",    label: "Brand Search",  icon: Icons.search },
    { id: "progress", label: "Job Status",   icon: Icons.grid,  hide: !activeJobId },
  ];

  return (
    <>
      <ThemeCtx.Provider value={isDark}>
      <GlobalStyle isDark={isDark} />
      <div style={{ minHeight: "100vh", background: T.dark, transition: "background 0.25s" }}>
        <Header isDark={isDark} onToggle={() => setIsDark(d => !d)} />
        <Hero />
        <StatsBar jobHistory={jobHistory} />

        {/* Main panel */}
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "0 32px 80px" }}>
          {/* Tab bar */}
          <div style={{ display: "flex", gap: 4, marginBottom: 24, background: T.darkCard, padding: 6, borderRadius: 12, border: `1px solid ${T.darkBorder}`, width: "fit-content" }}>
            {tabs.filter(t => !t.hide).map(({ id, label, icon }) => (
              <button key={id} onClick={() => setTab(id)} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "9px 18px", borderRadius: 8, border: "none",
                background: tab === id ? T.orange : "transparent",
                color: tab === id ? T.white : T.textSecond,
                fontFamily: "'Syne',sans-serif", fontWeight: 700, fontSize: 13,
                transition: "all 0.18s",
              }}>
                <Icon d={icon} size={14} color={tab === id ? T.white : T.textSecond} />
                {label}
              </button>
            ))}
          </div>

          {/* Panels */}
          <div className="fade-in" key={tab}>
            {tab === "single" && (
              <>
                <SingleURLPanel onResult={handleSingleResult} />
                {singleResult && (
                  <div ref={resultsRef} style={{ marginTop: 24 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                      <Label>Result</Label>
                      {singleResult.download && (
                        <a href={`${API}${singleResult.download}`} download>
                          <OrangeBtn small>
                            <Icon d={Icons.download} size={14} color={T.white} />
                            Download {singleResult.format?.toUpperCase()}
                          </OrangeBtn>
                        </a>
                      )}
                    </div>
                    <ResultCard result={singleResult.result} download={singleResult.download} index={0} />
                  </div>
                )}
              </>
            )}
            {tab === "batch" && <BatchURLPanel onJobStart={handleJobStart} />}
            {tab === "file"  && <FileUploadPanel onJobStart={handleJobStart} />}
            {tab === "progress" && activeJobId && (
              <div ref={resultsRef}>
                <JobProgressPanel jobId={activeJobId} onDone={handleJobDone} />
                {completedJob?.results?.length > 0 && (
                  <div style={{ marginTop: 24 }}>
                    <Label>All Results ({completedJob.results.length})</Label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
                      {completedJob.results.map((r, i) => (
                        <ResultCard key={i} result={r} index={i} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer style={{
          borderTop: `1px solid ${T.darkBorder}`, padding: "28px 32px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexWrap: "wrap", gap: 16,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: T.orange, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Icon d={Icons.zap} size={14} color={T.white} />
            </div>
            <span style={{ fontFamily: "'Syne',sans-serif", fontWeight: 700, color: T.textPrimary }}>
              Scraper<span style={{ color: T.orange }}>Pro</span>
            </span>
          </div>
          <div style={{ fontSize: 12, color: T.textMuted }}>
            Exports to Jumia <span style={{ color: T.orange }}>BOBTemplate</span> · <span style={{ color: T.orange }}>VendorCenter</span> · Raw CSV
          </div>
        </footer>
      </div>
    </ThemeCtx.Provider>
    </>
  );
}
