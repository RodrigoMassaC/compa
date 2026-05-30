"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken, getUser } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface Solicitud {
  id_solicitud: string;
  nombre_comercial: string;
  rif: string | null;
  sector: string | null;
  contacto_nombre: string;
  contacto_email: string;
  contacto_telefono: string | null;
  plan_interes: string | null;
  mensaje: string | null;
  estado: string;
  creado_en: string;
  atendida_en: string | null;
  id_empresa_creada: string | null;
}

export default function AdminB2BPage() {
  const router = useRouter();
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtroEstado, setFiltroEstado] = useState<string>("pendiente");
  const [activando, setActivando] = useState<string | null>(null);

  useEffect(() => {
    const user = getUser();
    if (!user || user.rol_usuario !== "ADMIN") {
      router.push("/");
      return;
    }
    cargar();
  }, [router, filtroEstado]); // eslint-disable-line react-hooks/exhaustive-deps

  async function cargar() {
    setLoading(true);
    const token = getToken();
    try {
      const res = await fetch(`${API}/b2b/admin/solicitudes?estado=${filtroEstado}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("No se pudo cargar");
      setSolicitudes(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function activar(sol: Solicitud, plan: "basico" | "pro" | "premium") {
    if (!confirm(`Activar "${sol.nombre_comercial}" en el plan ${plan.toUpperCase()}?`)) return;
    const token = getToken();
    setActivando(sol.id_solicitud);
    try {
      const res = await fetch(`${API}/b2b/admin/empresas`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          id_solicitud: sol.id_solicitud,
          nombre_comercial: sol.nombre_comercial,
          rif: sol.rif,
          sector: sol.sector,
          plan,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "No se pudo activar");
      }
      await cargar();
      alert("Empresa activada ✓");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error activando");
    } finally {
      setActivando(null);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa Admin</span>
        </Link>
        <Link href="/dashboard" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Dashboard
        </Link>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-10 space-y-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 mb-1">Solicitudes B2B</h1>
            <p className="text-sm text-slate-500">Gestión de solicitudes de acceso a Compi.</p>
          </div>
          <div className="flex gap-2">
            {(["pendiente", "contactado", "activada", "descartada"] as const).map((e) => (
              <button
                key={e}
                onClick={() => setFiltroEstado(e)}
                className={`text-xs font-bold uppercase px-3 py-2 rounded-full transition-colors ${
                  filtroEstado === e
                    ? "bg-[#3C5ACB] text-white"
                    : "bg-white border border-slate-200 text-slate-500 hover:bg-slate-100"
                }`}
              >
                {e}
              </button>
            ))}
          </div>
        </div>

        {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}

        {loading ? (
          <div className="text-center py-20 text-slate-400">Cargando…</div>
        ) : solicitudes.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-100 p-10 text-center text-slate-400">
            No hay solicitudes en estado <strong>{filtroEstado}</strong>.
          </div>
        ) : (
          <div className="space-y-3">
            {solicitudes.map((s) => (
              <div key={s.id_solicitud} className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
                <div className="flex items-start justify-between gap-4 flex-wrap mb-3">
                  <div>
                    <p className="font-extrabold text-slate-900 text-lg">{s.nombre_comercial}</p>
                    <p className="text-xs text-slate-400">
                      {s.sector || "sin sector"}
                      {s.rif && ` · RIF ${s.rif}`}
                      {s.plan_interes && ` · Interés: ${s.plan_interes.toUpperCase()}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs font-bold uppercase px-3 py-1 rounded-full ${
                      s.estado === "pendiente"  ? "bg-amber-100 text-amber-800" :
                      s.estado === "contactado" ? "bg-blue-100 text-blue-800" :
                      s.estado === "activada"   ? "bg-green-100 text-green-800" :
                                                  "bg-slate-100 text-slate-500"
                    }`}>
                      {s.estado}
                    </span>
                    <p className="text-xs text-slate-400 mt-1">
                      {new Date(s.creado_en).toLocaleDateString("es-VE", { day: "numeric", month: "short", year: "numeric" })}
                    </p>
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-3 text-sm bg-slate-50 rounded-xl p-4 mb-3">
                  <div><strong className="text-slate-500">Contacto:</strong> {s.contacto_nombre}</div>
                  <div><strong className="text-slate-500">Email:</strong> <a href={`mailto:${s.contacto_email}`} className="text-[#3C5ACB] hover:underline">{s.contacto_email}</a></div>
                  {s.contacto_telefono && (
                    <div className="sm:col-span-2"><strong className="text-slate-500">Teléfono:</strong> {s.contacto_telefono}</div>
                  )}
                  {s.mensaje && (
                    <div className="sm:col-span-2 mt-2 pt-2 border-t border-slate-200">
                      <strong className="text-slate-500 block text-xs mb-1">Mensaje:</strong>
                      <p className="text-slate-700 whitespace-pre-wrap">{s.mensaje}</p>
                    </div>
                  )}
                </div>

                {s.estado === "pendiente" && (
                  <div className="flex flex-wrap gap-2 items-center">
                    <span className="text-xs font-bold text-slate-500 uppercase">Activar como:</span>
                    {(["basico", "pro", "premium"] as const).map((plan) => (
                      <button
                        key={plan}
                        onClick={() => activar(s, plan)}
                        disabled={activando === s.id_solicitud}
                        className="bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:bg-slate-300 text-white font-bold text-sm px-4 py-2 rounded-full transition-colors"
                      >
                        {plan.toUpperCase()}
                      </button>
                    ))}
                  </div>
                )}

                {s.id_empresa_creada && (
                  <p className="text-xs text-green-700 font-medium mt-2">
                    ✓ Empresa activa (ID: {s.id_empresa_creada})
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
