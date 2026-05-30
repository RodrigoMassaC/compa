"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken, getUser } from "@/lib/auth";
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const PALETA = ["#3C5ACB", "#DDDD4A", "#6B7FD7", "#9EB1F0", "#2F47A8", "#C8C830", "#1E2E7A"];

type Tab = "resumen" | "precios" | "demografia" | "tendencias" | "visibilidad";

interface Empresa {
  id_empresa: string;
  nombre_comercial: string;
  plan: string;
  estado: string;
  activa_hasta: string | null;
  sector: string | null;
  rol: string;
}

interface DashboardKPI {
  empresa: { nombre: string; plan: string };
  kpis: {
    consultas_mes_total: number;
    menciones_mi_cadena_mes: number;
    porcentaje_menciones: number;
    rubros_top: { rubro: string; n: number }[];
  };
  tasa_bcv: { actual: number | null; evolucion: { fecha: string; valor: number }[] };
}

interface PrecioRubro {
  categoria: string;
  productos: number;
  precio_min: number;
  precio_max: number;
  precio_promedio: number;
  precio_mediano: number;
}

interface Demograficos {
  por_sexo:   { sexo: string;   n: number }[];
  por_ciudad: { ciudad: string; n: number }[];
  por_estado: { estado: string; n: number }[];
}

interface Tendencias {
  top_rubros: { rubro: string; consultas: number }[];
  evolucion_mensual: { mes: string; consultas: number }[];
}

interface Visibilidad {
  menciones_mensual: { mes: string; menciones: number }[];
  ranking_cadenas: { cadena: string; menciones: number }[];
  clicks_30d: { total: number; web: number; whatsapp: number };
}

export default function DashboardPage() {
  const router = useRouter();
  const [empresa, setEmpresa]   = useState<Empresa | null>(null);
  const [loading, setLoading]   = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [sinEmpresa, setSinEmpresa] = useState(false);
  const [tab, setTab]           = useState<Tab>("resumen");

  const [dash, setDash]         = useState<DashboardKPI | null>(null);
  const [precios, setPrecios]   = useState<PrecioRubro[] | null>(null);
  const [demo, setDemo]         = useState<Demograficos | null>(null);
  const [tend, setTend]         = useState<Tendencias | null>(null);
  const [vis, setVis]           = useState<Visibilidad | null>(null);

  useEffect(() => {
    const user = getUser();
    if (!user) {
      router.push("/auth?next=/dashboard");
      return;
    }
    if (user.rol_usuario !== "B2B_EMPRESA" && user.rol_usuario !== "ADMIN") {
      router.push("/empresas");
      return;
    }
    cargarEmpresa();
  }, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchAuth<T>(path: string): Promise<T> {
    const token = getToken();
    const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`Error ${r.status} en ${path}`);
    return r.json();
  }

  async function cargarEmpresa() {
    setLoading(true);
    setErrorMsg(null);
    const token = getToken();
    try {
      const r = await fetch(`${API}/b2b/empresa/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.status === 404) {
        setSinEmpresa(true);
        setLoading(false);
        return;
      }
      if (!r.ok) throw new Error("No se pudo cargar la empresa");
      setEmpresa(await r.json());
      setDash(await fetchAuth<DashboardKPI>("/b2b/empresa/me/dashboard"));
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function cargarTab(t: Tab) {
    setTab(t);
    setErrorMsg(null);
    try {
      if (t === "precios"     && !precios) setPrecios(await fetchAuth<PrecioRubro[]>("/b2b/empresa/me/precios"));
      if (t === "demografia"  && !demo)    setDemo(await fetchAuth<Demograficos>("/b2b/empresa/me/demograficos"));
      if (t === "tendencias"  && !tend)    setTend(await fetchAuth<Tendencias>("/b2b/empresa/me/tendencias"));
      if (t === "visibilidad" && !vis)     setVis(await fetchAuth<Visibilidad>("/b2b/empresa/me/visibilidad"));
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Error cargando datos");
    }
  }

  if (sinEmpresa) {
    return (
      <div className="min-h-screen bg-[#F5F7FF] flex items-center justify-center font-sans p-4">
        <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-10 max-w-md text-center">
          <div className="text-5xl mb-4">🏢</div>
          <h1 className="text-xl font-extrabold text-slate-900 mb-2">No tienes Compi activo</h1>
          <p className="text-sm text-slate-500 mb-6">
            Para acceder al dashboard B2B necesitas un plan Compi activo. Solicítalo y nuestro equipo te
            contacta para activarte en 24-48h.
          </p>
          <Link href="/empresas" className="inline-block bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-8 py-3 rounded-full transition-colors">
            Ver planes Compi →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compi</span>
        </Link>
        <div className="flex items-center gap-4">
          {empresa && (
            <div className="hidden sm:flex items-center gap-3 px-4 py-2 bg-[#F5F7FF] rounded-full">
              <span className="font-bold text-sm text-slate-700">{empresa.nombre_comercial}</span>
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#3C5ACB] bg-white px-2 py-0.5 rounded-full border border-[#DDE4FA]">
                {empresa.plan}
              </span>
            </div>
          )}
          {getUser()?.rol_usuario === "ADMIN" && (
            <Link href="/admin/b2b" className="text-xs font-bold text-slate-500 hover:text-slate-700 hidden sm:inline">
              Admin solicitudes
            </Link>
          )}
          <Link href="/perfil" className="text-sm font-bold text-slate-500 hover:text-slate-700">Perfil</Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {(["resumen","precios","demografia","tendencias","visibilidad"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => cargarTab(t)}
              className={`px-5 py-2.5 rounded-full font-bold text-sm whitespace-nowrap transition-colors ${
                tab === t
                  ? "bg-[#3C5ACB] text-white"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              {LABELS[t]}
            </button>
          ))}
        </div>

        {errorMsg && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">{errorMsg}</div>
        )}

        {loading && !dash ? (
          <div className="text-center py-20 text-slate-400">Cargando datos…</div>
        ) : (
          <>
            {tab === "resumen"     && <TabResumen     data={dash} />}
            {tab === "precios"     && <TabPrecios     data={precios} />}
            {tab === "demografia"  && <TabDemografia  data={demo} />}
            {tab === "tendencias"  && <TabTendencias  data={tend} />}
            {tab === "visibilidad" && <TabVisibilidad data={vis} empresa={empresa} />}
          </>
        )}
      </main>
    </div>
  );
}

const LABELS: Record<Tab, string> = {
  resumen:     "Resumen",
  precios:     "Precios",
  demografia:  "Demografía",
  tendencias:  "Tendencias",
  visibilidad: "Visibilidad",
};

/* ── Tabs ─────────────────────────────────────────────────────────────────── */

function TabResumen({ data }: { data: DashboardKPI | null }) {
  if (!data) return <Skel />;
  const { kpis, tasa_bcv } = data;
  return (
    <div className="space-y-6">
      <div className="grid sm:grid-cols-3 gap-4">
        <Kpi label="Consultas este mes (mercado)" valor={kpis.consultas_mes_total.toLocaleString()} />
        <Kpi label="Menciones de tu cadena" valor={kpis.menciones_mi_cadena_mes.toLocaleString()} />
        <Kpi label="% de participación" valor={`${kpis.porcentaje_menciones}%`} acento />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardTitle>Tasa BCV — últimos 30 días</CardTitle>
          <p className="text-sm text-slate-500 mb-3">Actual: <strong>Bs. {tasa_bcv.actual?.toFixed(2) ?? "—"}</strong></p>
          {tasa_bcv.evolucion.length === 0 ? <Empty inline /> : (
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={tasa_bcv.evolucion}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef0f7" />
                  <XAxis dataKey="fecha" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="valor" stroke="#3C5ACB" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <CardTitle>Top rubros del mes</CardTitle>
          {kpis.rubros_top.length === 0 ? (
            <p className="text-sm text-slate-400">Aún no hay datos clasificados este mes.</p>
          ) : (
            <ul className="space-y-2 mt-2">
              {kpis.rubros_top.map((r) => (
                <li key={r.rubro} className="flex items-center justify-between bg-slate-50 rounded-xl px-4 py-2.5">
                  <span className="text-sm font-bold text-slate-700 capitalize">{formatRubro(r.rubro)}</span>
                  <span className="text-sm font-extrabold text-[#3C5ACB]">{r.n}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function TabPrecios({ data }: { data: PrecioRubro[] | null }) {
  if (!data) return <Skel />;
  if (data.length === 0) return <Empty texto="Aún no hay suficientes precios clasificados." />;

  return (
    <Card>
      <CardTitle>Análisis de precios del mercado (USD, últimos 60 días)</CardTitle>
      <p className="text-sm text-slate-500 mb-4">Por categoría de producto, agregando todas las cadenas monitoreadas.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            <tr className="border-b border-slate-100">
              <th className="text-left py-3 pr-4">Categoría</th>
              <th className="text-right py-3 pr-4">Productos</th>
              <th className="text-right py-3 pr-4">Mín</th>
              <th className="text-right py-3 pr-4">Mediano</th>
              <th className="text-right py-3 pr-4">Promedio</th>
              <th className="text-right py-3">Máx</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.categoria} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="py-3 pr-4 font-bold text-slate-700 capitalize">{r.categoria.replace(/_/g, " ")}</td>
                <td className="py-3 pr-4 text-right text-slate-500">{r.productos}</td>
                <td className="py-3 pr-4 text-right font-bold text-green-700">${r.precio_min?.toFixed(2)}</td>
                <td className="py-3 pr-4 text-right text-slate-700">${r.precio_mediano?.toFixed(2)}</td>
                <td className="py-3 pr-4 text-right text-slate-700">${r.precio_promedio?.toFixed(2)}</td>
                <td className="py-3 text-right font-bold text-red-700">${r.precio_max?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TabDemografia({ data }: { data: Demograficos | null }) {
  if (!data) return <Skel />;
  const sinDatos = data.por_sexo.length === 0 && data.por_ciudad.length === 0;
  if (sinDatos) return <Empty texto="Aún no hay suficientes datos demográficos de usuarios registrados." />;

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <Card>
        <CardTitle>Por sexo (90d)</CardTitle>
        {data.por_sexo.length === 0 ? <Empty inline /> : (
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data.por_sexo} dataKey="n" nameKey="sexo" outerRadius={80} label={(e: { sexo: string; n: number }) => `${e.sexo}: ${e.n}`}>
                  {data.por_sexo.map((_, i) => <Cell key={i} fill={PALETA[i % PALETA.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Top ciudades (90d)</CardTitle>
        {data.por_ciudad.length === 0 ? <Empty inline /> : (
          <ul className="space-y-1.5 mt-2 max-h-64 overflow-y-auto">
            {data.por_ciudad.map((c) => (
              <li key={c.ciudad} className="flex justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm">
                <span className="font-bold text-slate-700 truncate">{c.ciudad}</span>
                <span className="font-extrabold text-[#3C5ACB] ml-2">{c.n}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardTitle>Top estados (90d)</CardTitle>
        {data.por_estado.length === 0 ? <Empty inline /> : (
          <ul className="space-y-1.5 mt-2 max-h-64 overflow-y-auto">
            {data.por_estado.map((c) => (
              <li key={c.estado} className="flex justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm">
                <span className="font-bold text-slate-700 truncate">{c.estado}</span>
                <span className="font-extrabold text-[#3C5ACB] ml-2">{c.n}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function TabTendencias({ data }: { data: Tendencias | null }) {
  if (!data) return <Skel />;
  return (
    <div className="space-y-4">
      <Card>
        <CardTitle>Evolución mensual del mercado (12m)</CardTitle>
        {data.evolucion_mensual.length === 0 ? <Empty inline /> : (
          <div className="h-72">
            <ResponsiveContainer>
              <LineChart data={data.evolucion_mensual}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f7" />
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="consultas" stroke="#3C5ACB" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Top 15 rubros (90d)</CardTitle>
        {data.top_rubros.length === 0 ? <Empty inline /> : (
          <div className="h-96">
            <ResponsiveContainer>
              <BarChart data={data.top_rubros.map(r => ({ ...r, rubro: formatRubro(r.rubro) }))} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f7" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="rubro" tick={{ fontSize: 11 }} width={140} />
                <Tooltip />
                <Bar dataKey="consultas" fill="#3C5ACB" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}

function TabVisibilidad({ data, empresa }: { data: Visibilidad | null; empresa: Empresa | null }) {
  if (!data) return <Skel />;
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">
        <Kpi label="Clicks 30d (total)" valor={data.clicks_30d.total.toLocaleString()} />
        <Kpi label="Clicks 30d → Web" valor={data.clicks_30d.web.toLocaleString()} />
        <Kpi label="Clicks 30d → WhatsApp" valor={data.clicks_30d.whatsapp.toLocaleString()} />
      </div>

      <Card>
        <CardTitle>Menciones mensuales de {empresa?.nombre_comercial || "tu cadena"} (12m)</CardTitle>
        {data.menciones_mensual.length === 0 ? <Empty inline texto="Aún no hay menciones registradas. Las consultas nuevas ya se están clasificando." /> : (
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={data.menciones_mensual}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f7" />
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="menciones" stroke="#DDDD4A" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Ranking del mes — menciones por cadena</CardTitle>
        {data.ranking_cadenas.length === 0 ? <Empty inline /> : (
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={data.ranking_cadenas}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f7" />
                <XAxis dataKey="cadena" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="menciones" radius={[6, 6, 0, 0]}>
                  {data.ranking_cadenas.map((c, i) => (
                    <Cell key={i} fill={c.cadena === empresa?.nombre_comercial ? "#3C5ACB" : "#9EB1F0"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ── Helpers UI ───────────────────────────────────────────────────────────── */

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white rounded-3xl border border-slate-100 shadow-sm p-6 ${className || ""}`}>{children}</div>;
}
function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="font-extrabold text-slate-800 mb-3">{children}</h2>;
}
function Kpi({ label, valor, acento }: { label: string; valor: string; acento?: boolean }) {
  return (
    <div className={`rounded-3xl border shadow-sm p-6 ${acento ? "bg-[#3C5ACB] border-[#3C5ACB] text-white" : "bg-white border-slate-100"}`}>
      <p className={`text-xs font-bold uppercase tracking-widest mb-2 ${acento ? "text-blue-200" : "text-slate-400"}`}>{label}</p>
      <p className="text-3xl font-extrabold">{valor}</p>
    </div>
  );
}
function Skel() { return <div className="bg-white rounded-3xl border border-slate-100 p-10 text-center text-slate-400 text-sm">Cargando…</div>; }
function Empty({ texto, inline }: { texto?: string; inline?: boolean }) {
  return <div className={`text-slate-400 text-sm ${inline ? "py-4 text-center" : "bg-white rounded-3xl border border-slate-100 p-10 text-center"}`}>{texto || "Sin datos aún."}</div>;
}
function formatRubro(r: string): string {
  return r.replace(/^farmacia_/, "💊 ").replace(/_/g, " ");
}
