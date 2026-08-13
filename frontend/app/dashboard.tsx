"use client";

import { useMemo, useState } from "react";
import { ApiError, createDemoRun, getRun } from "@/lib/api/client";
import type { Candidate, RunDetail } from "@/lib/api/types";

type Props = { initialRun: RunDetail | null };

const REGIME_LABEL: Record<string, string> = {
  TREND_UP: "趋势上行",
  RANGE: "区间震荡",
  RISK_OFF: "风险收缩",
};

function pct(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function amount(value: number): string {
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}亿`;
  return `${(value / 10_000).toFixed(0)}万`;
}

export function Dashboard({ initialRun }: Props) {
  const [run, setRun] = useState<RunDetail | null>(initialRun);
  const [selected, setSelected] = useState<Candidate | null>(initialRun?.candidates[0] ?? null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>(initialRun ? "已加载最近一次复盘结果" : "尚未生成任何复盘，请点击右上角执行");
  const [adminKey, setAdminKey] = useState<string>("");

  const focusCount = useMemo(() => run?.candidates.filter((c) => c.tier === "FOCUS").length ?? 0, [run]);

  async function triggerRun() {
    if (!adminKey) {
      setNotice("请填写 Admin Key 以触发复盘");
      return;
    }
    setBusy(true);
    setNotice("正在冻结数据并协调 5 个角色…");
    try {
      const { run_id } = await createDemoRun(adminKey);
      const detail = await getRun(run_id);
      setRun(detail);
      setSelected(detail.candidates[0] ?? null);
      setNotice("复盘完成，数据快照、决策链与报告已落盘");
    } catch (error) {
      if (error instanceof ApiError) {
        setNotice(`运行失败：${error.message}`);
      } else {
        setNotice("运行失败，请检查后端服务是否可用");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!run) {
    return (
      <main style={{ padding: 40, maxWidth: 720, margin: "0 auto" }}>
        <h1>知衡 · 股票复盘 Agent</h1>
        <p style={{ color: "var(--muted)" }}>暂无历史运行数据。设置 Admin Key 并点击运行以生成第一次复盘。</p>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="password"
            placeholder="Admin Key"
            value={adminKey}
            onChange={(event) => setAdminKey(event.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--panel)",
              color: "var(--ink)",
              minWidth: 240,
            }}
          />
          <button
            onClick={triggerRun}
            disabled={busy}
            style={{
              padding: "8px 18px",
              border: 0,
              borderRadius: 8,
              background: "var(--accent)",
              color: "#fff",
              fontWeight: 700,
            }}
          >
            {busy ? "分析中…" : "运行收盘复盘"}
          </button>
        </div>
        <p style={{ marginTop: 16, color: "var(--muted)", fontSize: 13 }}>{notice}</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1280, margin: "0 auto", padding: 32, color: "var(--ink)" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <p style={{ margin: 0, color: "var(--muted)", fontWeight: 700, letterSpacing: 1 }}>MARKET CLOSE · {run.trade_date}</p>
          <h1 style={{ margin: "4px 0 0", fontSize: 30, letterSpacing: -0.5 }}>收盘决策室</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{notice}</span>
          <input
            type="password"
            placeholder="Admin Key"
            value={adminKey}
            onChange={(event) => setAdminKey(event.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--panel)",
              color: "var(--ink)",
            }}
          />
          <button
            onClick={triggerRun}
            disabled={busy}
            style={{
              padding: "8px 16px",
              border: 0,
              borderRadius: 8,
              background: "var(--accent)",
              color: "#fff",
              fontWeight: 700,
            }}
          >
            {busy ? "分析中…" : "运行收盘复盘"}
          </button>
        </div>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: 16 }}>
        <article style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <span style={{ color: "var(--muted)", fontWeight: 700, fontSize: 12 }}>市场状态</span>
            <span style={pillStyle(run.market_regime)}>{REGIME_LABEL[run.market_regime] ?? run.market_regime}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 20, alignItems: "center" }}>
            <div
              style={{
                width: 108,
                height: 108,
                borderRadius: "50%",
                border: `10px solid var(--accent)`,
                borderTopColor: "var(--panel-2)",
                display: "grid",
                placeContent: "center",
                textAlign: "center",
              }}
            >
              <strong style={{ fontSize: 26 }}>{Math.round(run.market_review.advance_ratio)}</strong>
              <small style={{ color: "var(--muted)" }}>上涨占比</small>
            </div>
            <div>
              <strong style={{ fontSize: 30, color: "var(--success)" }}>{pct(run.market_review.index_change)}</strong>
              <div style={{ color: "var(--muted)", fontSize: 12 }}>样本近 5 日平均</div>
              <p style={{ marginTop: 12, color: "var(--muted)", fontSize: 13, lineHeight: 1.6 }}>{run.market_review.summary}</p>
            </div>
          </div>
          <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "18px 0" }} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, fontSize: 12 }}>
            <div>
              <span style={{ color: "var(--muted)" }}>样本成交额</span>
              <strong style={{ display: "block", marginTop: 4 }}>{amount(run.market_review.total_amount)}</strong>
            </div>
            <div>
              <span style={{ color: "var(--muted)" }}>较前一日</span>
              <strong style={{ display: "block", marginTop: 4 }}>{pct(run.market_review.volume_change)}</strong>
            </div>
            <div>
              <span style={{ color: "var(--muted)" }}>数据覆盖率</span>
              <strong style={{ display: "block", marginTop: 4 }}>{run.data_quality.coverage}%</strong>
            </div>
          </div>
        </article>

        <article style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <div>
              <span style={{ color: "var(--muted)", fontWeight: 700, fontSize: 12 }}>强势行业</span>
              <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>按近 5 日相对强度</div>
            </div>
            <b style={{ color: "var(--muted)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 11 }}>TOP 3</b>
          </div>
          <div style={{ display: "grid", gap: 14 }}>
            {run.market_review.leading_industries.map((item, index) => (
              <div key={item.name} style={{ display: "grid", gridTemplateColumns: "24px 80px 1fr 60px", alignItems: "center", gap: 10 }}>
                <span style={{ color: "var(--muted)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 11 }}>0{index + 1}</span>
                <strong>{item.name}</strong>
                <div style={{ height: 5, background: "var(--panel-2)", borderRadius: 3, overflow: "hidden" }}>
                  <i style={{ display: "block", height: "100%", width: `${Math.max(18, Math.min(100, 35 + item.change * 5))}%`, background: "var(--accent)" }} />
                </div>
                <em style={{ color: "var(--success)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, textAlign: "right", fontStyle: "normal" }}>{pct(item.change)}</em>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section style={{ marginTop: 32 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 12 }}>
          <div>
            <p style={{ margin: 0, color: "var(--muted)", fontWeight: 700, fontSize: 11, letterSpacing: 1.5 }}>NEXT SESSION WATCHLIST</p>
            <h2 style={{ margin: "6px 0 0", fontSize: 22 }}>次日重点观察池</h2>
          </div>
          <div style={{ color: "var(--muted)", fontSize: 12 }}>
            <span style={{ marginRight: 12 }}>{focusCount} 只重点</span>
            <span style={{ marginRight: 12 }}>{run.candidates.length} 只候选</span>
            <span>{run.rejected_count} 只未入池</span>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 0.85fr", gap: 16 }}>
          <div style={cardStyle}>
            {run.candidates.length ? (
              run.candidates.map((candidate) => (
                <button
                  key={candidate.security_id}
                  onClick={() => setSelected(candidate)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1.35fr 1fr 58px 65px",
                    gap: 14,
                    alignItems: "center",
                    width: "100%",
                    padding: 14,
                    border: 0,
                    borderBottom: "1px solid var(--line)",
                    background: selected?.security_id === candidate.security_id ? "var(--panel-2)" : "transparent",
                    color: "inherit",
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  <span>
                    <b>{candidate.name}</b>
                    <small style={{ display: "block", color: "var(--muted)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 10, marginTop: 4 }}>
                      {candidate.security_id} · {candidate.industry}
                    </small>
                  </span>
                  <span>
                    <div style={{ height: 4, borderRadius: 3, background: "var(--panel-2)", overflow: "hidden" }}>
                      <i style={{ display: "block", height: "100%", width: `${Math.min(100, candidate.score)}%`, background: "var(--accent)" }} />
                    </div>
                    <small style={{ display: "block", color: "var(--muted)", marginTop: 6, fontSize: 10 }}>tier {candidate.tier}</small>
                  </span>
                  <span style={{ color: "var(--success)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontWeight: 700 }}>{candidate.score.toFixed(1)}</span>
                  <span style={{ fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12 }}>{Math.round(candidate.confidence * 100)}%</span>
                </button>
              ))
            ) : (
              <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>当前没有股票满足评分与风控门槛。</div>
            )}
          </div>

          <article style={cardStyle}>
            {selected ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <span style={{ display: "inline-block", padding: "3px 8px", borderRadius: 99, background: "var(--panel-2)", color: "var(--success)", fontSize: 11, marginBottom: 10 }}>
                      {selected.tier === "FOCUS" ? "重点观察" : "扩展观察"}
                    </span>
                    <h3 style={{ margin: "4px 0", fontSize: 22 }}>{selected.name}</h3>
                    <p style={{ margin: 0, color: "var(--muted)", fontSize: 12 }}>{selected.security_id} · {selected.industry}</p>
                  </div>
                </div>
                <div style={{ marginTop: 20 }}>
                  <h4 style={{ color: "var(--muted)", fontSize: 11, letterSpacing: 1 }}>入选逻辑</h4>
                  {selected.reasons.map((reason, index) => (
                    <p key={reason} style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 8, margin: "10px 0", fontSize: 12, lineHeight: 1.55 }}>
                      <b style={{ color: "var(--success)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 10 }}>0{index + 1}</b>
                      <span>{reason}</span>
                    </p>
                  ))}
                </div>
                <div style={{ marginTop: 14, padding: 12, borderRadius: 8, background: "var(--panel-2)" }}>
                  <span style={{ color: "var(--warning)", fontSize: 11 }}>风险与失效条件</span>
                  <p style={{ margin: "6px 0 0", fontSize: 12, lineHeight: 1.5 }}>{selected.risks.join("；")}</p>
                </div>
              </>
            ) : (
              <div style={{ color: "var(--muted)", padding: 30, textAlign: "center" }}>没有可展示的候选。</div>
            )}
          </article>
        </div>
      </section>

      <section style={{ marginTop: 32 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 12 }}>
          <div>
            <p style={{ margin: 0, color: "var(--muted)", fontWeight: 700, fontSize: 11, letterSpacing: 1.5 }}>MULTI-AGENT REVIEW</p>
            <h2 style={{ margin: "6px 0 0", fontSize: 22 }}>角色协作与发布门禁</h2>
          </div>
          <span style={{ padding: "4px 10px", borderRadius: 99, background: "var(--panel-2)", color: "var(--success)", fontSize: 11, fontWeight: 700 }}>
            {run.status === "SUCCEEDED" || run.status === "DEGRADED_SUCCEEDED" ? "发布门禁通过" : "发布门禁失败"}
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          {run.agents.map((agent, index) => (
            <article key={agent.id ?? `${agent.role_id}-${index}`} style={{ ...cardStyle, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "var(--muted)", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 10 }}>0{index + 1}</span>
                <span
                  style={{
                    width: 20,
                    height: 20,
                    display: "grid",
                    placeContent: "center",
                    borderRadius: "50%",
                    background: "var(--success)",
                    color: "#fff",
                    fontSize: 10,
                  }}
                >
                  ✓
                </span>
              </div>
              <h3 style={{ margin: "20px 0 8px", fontSize: 14 }}>{agent.role_label}</h3>
              <p style={{ color: "var(--muted)", fontSize: 11, lineHeight: 1.6, minHeight: 60 }}>{agent.summary}</p>
              <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--line)", paddingTop: 10, marginTop: 12, color: "var(--muted)", fontSize: 10 }}>
                <span>置信度</span>
                <b style={{ color: "var(--success)", fontFamily: "ui-monospace, SFMono-Regular, monospace" }}>{Math.round(agent.confidence * 100)}%</b>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section style={{ marginTop: 32, padding: 18, borderRadius: 12, background: "var(--panel)", border: "1px solid var(--line)", display: "flex", justifyContent: "space-between" }}>
        <div>
          <b>每日数据已落盘</b>
          <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 3 }}>Raw 快照、Agent 决策链、候选与报告分层持久化</div>
        </div>
        <dl style={{ display: "flex", gap: 32, margin: 0 }}>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: 10 }}>快照 ID</dt>
            <dd style={{ margin: "4px 0 0", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 11 }}>{run.snapshot_id}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: 10 }}>完成时间</dt>
            <dd style={{ margin: "4px 0 0", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 11 }}>{new Date(run.completed_at).toLocaleString("zh-CN", { hour12: false })}</dd>
          </div>
          <div>
            <dt style={{ color: "var(--muted)", fontSize: 10 }}>策略版本</dt>
            <dd style={{ margin: "4px 0 0", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 11 }}>{run.strategy_version}</dd>
          </div>
        </dl>
      </section>

      <footer style={{ marginTop: 32, display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 11 }}>
        <span>知衡 Stock Intelligence</span>
        <p style={{ margin: 0 }}>仅供研究参考，不构成投资建议。股票市场存在本金损失风险。</p>
      </footer>
    </main>
  );
}

const cardStyle: React.CSSProperties = {
  background: "var(--panel)",
  border: "1px solid var(--line)",
  borderRadius: 14,
  padding: 20,
};

function pillStyle(regime: string): React.CSSProperties {
  const map: Record<string, string> = { TREND_UP: "var(--success)", RANGE: "var(--accent)", RISK_OFF: "var(--warning)" };
  return {
    padding: "4px 10px",
    borderRadius: 99,
    fontSize: 11,
    fontWeight: 700,
    color: map[regime] ?? "var(--muted)",
    background: "var(--panel-2)",
  };
}

