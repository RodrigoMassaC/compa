"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken, getUser, planLabel, type AuthUser } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface QuotaData {
  plan: string;
  mes: string;
  uso: number;
  bonus_comprado: number;
  limite: number | null;
  restantes: number | null;
  porcentaje: number;
  ilimitado?: boolean;
  ilimitado_hasta?: string;
}

export default function ConsultasPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [comprando, setComprando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const u = getUser();
    setUser(u);
    const token = getToken();
    if (!token) { setLoading(false); return; }

    fetch(`${API}/payments/quota`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setQuota(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function comprar(tipo: "consultas_pack_30" | "plan_ilimitado_mensual") {
    setError(null);
    const token = getToken();
    if (!token) {
      router.push("/auth");
      return;
    }

    setComprando(tipo);
    try {
      const res = await fetch(`${API}/payments/pago-movil/crear`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tipo_producto: tipo }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Error al crear el pago");
      }
      const data = await res.json();
      // Redirige a la página de pago con el concepto generado
      router.push(`/comprar/${data.concepto}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al crear el pago");
      setComprando(null);
    }
  }

  const mesLabel = quota?.mes
    ? new Date(quota.mes + "-01").toLocaleString("es-VE", { month: "long", year: "numeric" })
    : "";

  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      {/* Header */}
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/chat" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <Link href="/chat" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Volver al chat
        </Link>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-12 space-y-6">

        {/* Estado actual */}
        <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8">
          <h1 className="text-2xl font-extrabold text-slate-900 mb-1">Mis consultas</h1>
          {user && (
            <p className="text-sm text-slate-400 mb-6">
              Plan actual: <span className="font-bold text-slate-600">{planLabel(user.plan || "FREE")}</span>
            </p>
          )}

          {loading ? (
            <div className="h-24 flex items-center justify-center text-slate-400 text-sm">Cargando...</div>
          ) : !user ? (
            <div className="text-center py-6">
              <p className="text-slate-500 mb-4">Inicia sesión para ver tu estado de consultas.</p>
              <Link href="/auth" className="bg-[#3C5ACB] text-white font-bold px-6 py-3 rounded-full hover:bg-[#2F47A8] transition-colors">
                Iniciar sesión
              </Link>
            </div>
          ) : quota?.ilimitado ? (
            <div className="bg-[#3C5ACB]/5 border border-[#3C5ACB]/20 rounded-2xl p-6 text-center">
              <p className="text-3xl mb-2">♾️</p>
              <p className="text-xl font-extrabold text-[#3C5ACB] mb-1">Plan Ilimitado activo</p>
              <p className="text-sm text-slate-500">
                Consultas sin límite. Llevas {quota.uso} este mes.
              </p>
              {quota.ilimitado_hasta && (
                <p className="text-xs text-slate-400 mt-2">
                  Válido hasta {new Date(quota.ilimitado_hasta).toLocaleDateString("es-VE", { day: "numeric", month: "long", year: "numeric" })}
                </p>
              )}
            </div>
          ) : quota ? (
            <div className="space-y-4">
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-4xl font-extrabold text-slate-900">{quota.restantes}</p>
                  <p className="text-sm text-slate-400">consultas restantes en {mesLabel}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-slate-500">Usadas: <span className="font-bold text-slate-700">{quota.uso}</span></p>
                  <p className="text-sm text-slate-500">Límite: <span className="font-bold text-slate-700">{quota.limite}</span></p>
                  {quota.bonus_comprado > 0 && (
                    <p className="text-xs text-[#3C5ACB] font-medium">+{quota.bonus_comprado} bonus</p>
                  )}
                </div>
              </div>

              {/* Barra de progreso */}
              <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-3 rounded-full transition-all ${quota.porcentaje >= 90 ? "bg-red-500" : quota.porcentaje >= 70 ? "bg-amber-400" : "bg-[#3C5ACB]"}`}
                  style={{ width: `${quota.porcentaje}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 text-right">{quota.porcentaje}% utilizado</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">No se pudo cargar la información.</p>
          )}
        </div>

        {/* Comprar más consultas */}
        {user && (
          <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8">
            <h2 className="text-lg font-extrabold text-slate-900 mb-1">Agregar consultas</h2>
            <p className="text-sm text-slate-400 mb-6">
              Paga con Pago Móvil desde cualquier banco venezolano. Conciliación automática.
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="grid gap-4">
              {/* Pack 30 consultas */}
              <div className="border border-slate-200 rounded-2xl p-5 flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-800">Pack +30 consultas</p>
                  <p className="text-sm text-slate-400">Compra única. No expiran.</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-extrabold text-slate-900">$1.50</p>
                  <button
                    onClick={() => comprar("consultas_pack_30")}
                    disabled={comprando !== null}
                    className="mt-2 bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:bg-slate-300 text-white font-bold text-sm px-5 py-2 rounded-full transition-colors"
                  >
                    {comprando === "consultas_pack_30" ? "Procesando..." : "Comprar"}
                  </button>
                </div>
              </div>

              {/* Plan Ilimitado */}
              <div className="border-2 border-[#3C5ACB]/20 bg-[#3C5ACB]/5 rounded-2xl p-5 flex items-center justify-between">
                <div>
                  <p className="font-bold text-[#3C5ACB]">Plan Ilimitado</p>
                  <p className="text-sm text-slate-500">Consultas ilimitadas por 30 días</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-extrabold text-slate-900">$5<span className="text-sm font-normal text-slate-400">/mes</span></p>
                  <button
                    onClick={() => comprar("plan_ilimitado_mensual")}
                    disabled={comprando !== null}
                    className="mt-2 bg-[#DDDD4A] hover:bg-[#C8C830] disabled:bg-slate-300 text-[#1E2E7A] font-bold text-sm px-5 py-2 rounded-full transition-colors"
                  >
                    {comprando === "plan_ilimitado_mensual" ? "Procesando..." : "Activar"}
                  </button>
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-400 mt-4 text-center">
              Pagos procesados por Mibanco (R4 Conecta). Conciliación automática en segundos.
            </p>
          </div>
        )}

        {/* CTA volver */}
        <div className="text-center">
          <Link
            href="/chat"
            className="inline-block bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-8 py-3 rounded-full transition-colors"
          >
            Volver al chat
          </Link>
        </div>

      </main>
    </div>
  );
}
