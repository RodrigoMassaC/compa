"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface PagoEstado {
  concepto: string;
  status: "pending" | "approved" | "rejected" | "expired";
  motivo_rechazo: string | null;
  monto_bs: number;
  monto_usd: number;
  tipo_producto: string;
  aprobado_en: string | null;
  creado_en: string | null;
}

interface PagoDatos {
  concepto: string;
  monto_bs: number;
  monto_usd: number;
  tasa_bcv: number;
  destino: {
    telefono: string;
    banco: string;
    rif: string;
  };
  producto: {
    nombre: string;
    descripcion: string;
  };
  ttl_minutos: number;
}

const BANCOS: Record<string, string> = {
  "0169": "Mibanco",
  "0102": "Banco de Venezuela",
  "0105": "Mercantil",
  "0108": "BBVA Provincial",
  "0134": "Banesco",
  "0151": "BFC",
  "0156": "100% Banco",
  "0157": "DelSur",
  "0163": "Banco del Tesoro",
};

export default function ComprarPage({ params }: { params: { concepto: string } }) {
  const { concepto } = params;
  const router = useRouter();
  const [datos, setDatos] = useState<PagoDatos | null>(null);
  const [estado, setEstado] = useState<PagoEstado | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiado, setCopiado] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Carga inicial del estado
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/auth");
      return;
    }

    fetch(`${API}/payments/pago-movil/estado/${concepto}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("No se encontró el pago");
        return r.json();
      })
      .then((s: PagoEstado) => {
        setEstado(s);
        // Reconstruir "datos" desde el estado (RIF y teléfono son del comercio,
        // los pedimos a /pago-movil/crear pero acá solo tenemos el estado;
        // hacemos una reconstrucción usando datos públicos):
        // En realidad necesitamos otra fuente para destino — lo dejamos en el endpoint
        // Por ahora pedimos /crear es la única forma de obtener los datos del destino.
        // Solución: extender el endpoint /estado para incluirlos.
        // Por ahora, los pedimos en useEffect aparte.
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [concepto, router]);

  // 2. Polling cada 3 seg mientras esté pending
  useEffect(() => {
    if (!estado || estado.status !== "pending") {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    const token = getToken();
    if (!token) return;

    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/payments/pago-movil/estado/${concepto}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) {
          const s: PagoEstado = await r.json();
          setEstado(s);
          if (s.status !== "pending" && pollRef.current) {
            clearInterval(pollRef.current);
          }
        }
      } catch {
        /* silent */
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [estado, concepto]);

  // 3. Pide los datos del destino al endpoint crear (solo si pending)
  useEffect(() => {
    if (!estado || estado.status !== "pending" || datos) return;
    const token = getToken();
    if (!token) return;

    // Llamamos a /crear con el mismo tipo_producto: si hay pending reciente lo reutiliza.
    fetch(`${API}/payments/pago-movil/crear`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ tipo_producto: estado.tipo_producto }),
    })
      .then(async (r) => {
        if (!r.ok) return null;
        return r.json();
      })
      .then((d: PagoDatos | null) => {
        if (d && d.concepto === concepto) setDatos(d);
      });
  }, [estado, concepto, datos]);

  function copiar(texto: string, etiqueta: string) {
    navigator.clipboard.writeText(texto);
    setCopiado(etiqueta);
    setTimeout(() => setCopiado(null), 1500);
  }

  const montoBsFormatted = estado
    ? estado.monto_bs.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "";

  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/chat" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <Link href="/consultas" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Mis consultas
        </Link>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-12">
        {loading ? (
          <div className="text-center py-20 text-slate-400">Cargando...</div>
        ) : error ? (
          <div className="bg-white rounded-3xl border border-red-200 p-8 text-center">
            <p className="text-red-700 font-bold mb-2">{error}</p>
            <Link href="/consultas" className="text-[#3C5ACB] font-bold hover:underline">
              Volver
            </Link>
          </div>
        ) : !estado ? null : estado.status === "approved" ? (
          // ── PAGO APROBADO ──
          <div className="bg-white rounded-3xl border-2 border-green-200 p-8 text-center">
            <div className="text-6xl mb-4">✅</div>
            <h1 className="text-2xl font-extrabold text-green-700 mb-2">¡Pago confirmado!</h1>
            <p className="text-slate-600 mb-6">
              Tu compra de <span className="font-bold">${estado.monto_usd.toFixed(2)} USD</span> fue acreditada.
            </p>
            <div className="bg-green-50 rounded-2xl p-5 mb-6 text-left">
              <p className="text-sm text-slate-700">
                <span className="font-bold">Producto:</span> {productoLabel(estado.tipo_producto)}
              </p>
              {estado.aprobado_en && (
                <p className="text-sm text-slate-700 mt-1">
                  <span className="font-bold">Fecha:</span> {new Date(estado.aprobado_en).toLocaleString("es-VE")}
                </p>
              )}
            </div>
            <Link
              href="/chat"
              className="inline-block bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-8 py-3 rounded-full transition-colors"
            >
              Empezar a buscar precios
            </Link>
          </div>
        ) : estado.status === "rejected" ? (
          // ── PAGO RECHAZADO ──
          <div className="bg-white rounded-3xl border-2 border-red-200 p-8 text-center">
            <div className="text-6xl mb-4">❌</div>
            <h1 className="text-2xl font-extrabold text-red-700 mb-2">Pago rechazado</h1>
            {estado.motivo_rechazo && (
              <p className="text-sm text-slate-600 mb-4">{estado.motivo_rechazo}</p>
            )}
            <Link
              href="/consultas"
              className="inline-block bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-8 py-3 rounded-full transition-colors"
            >
              Volver e intentar de nuevo
            </Link>
          </div>
        ) : estado.status === "expired" ? (
          // ── PAGO EXPIRADO ──
          <div className="bg-white rounded-3xl border-2 border-amber-200 p-8 text-center">
            <div className="text-6xl mb-4">⏱️</div>
            <h1 className="text-2xl font-extrabold text-amber-700 mb-2">Tiempo expirado</h1>
            <p className="text-sm text-slate-600 mb-4">
              El pago se canceló porque pasó demasiado tiempo. Vuelve a generar uno.
            </p>
            <Link
              href="/consultas"
              className="inline-block bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-8 py-3 rounded-full transition-colors"
            >
              Generar nuevo pago
            </Link>
          </div>
        ) : (
          // ── PAGO PENDING — instrucciones ──
          <div className="space-y-4">
            <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8">
              <div className="flex items-center gap-3 mb-4">
                <div className="animate-pulse h-3 w-3 rounded-full bg-amber-400"></div>
                <h1 className="text-xl font-extrabold text-slate-900">Esperando tu pago…</h1>
              </div>
              <p className="text-sm text-slate-500 mb-6">
                Haz el Pago Móvil desde tu banco usando estos datos. Se confirmará automáticamente.
              </p>

              {/* Monto destacado */}
              <div className="bg-[#3C5ACB] text-white rounded-2xl p-6 mb-6 text-center">
                <p className="text-sm uppercase font-bold opacity-80 mb-1">Monto a pagar</p>
                <p className="text-4xl font-extrabold">Bs. {montoBsFormatted}</p>
                <p className="text-sm opacity-80 mt-1">
                  (${estado.monto_usd.toFixed(2)} USD)
                </p>
              </div>

              {/* Datos del destino */}
              <div className="space-y-3">
                <DataRow
                  label="Teléfono"
                  value={datos?.destino.telefono || "Cargando..."}
                  onCopy={() => datos && copiar(datos.destino.telefono, "telefono")}
                  copiado={copiado === "telefono"}
                />
                <DataRow
                  label="Banco"
                  value={datos ? `${datos.destino.banco} — ${BANCOS[datos.destino.banco] || ""}` : "Cargando..."}
                  onCopy={() => datos && copiar(datos.destino.banco, "banco")}
                  copiado={copiado === "banco"}
                />
                <DataRow
                  label="Cédula / RIF"
                  value={datos?.destino.rif || "Cargando..."}
                  onCopy={() => datos && copiar(datos.destino.rif, "rif")}
                  copiado={copiado === "rif"}
                />
                <DataRow
                  label="Monto exacto (Bs)"
                  value={montoBsFormatted}
                  onCopy={() => copiar(estado.monto_bs.toFixed(2), "monto")}
                  copiado={copiado === "monto"}
                  destacado
                />
                <DataRow
                  label="Concepto / Referencia"
                  value={estado.concepto}
                  onCopy={() => copiar(estado.concepto, "concepto")}
                  copiado={copiado === "concepto"}
                  destacado
                />
              </div>

              <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-4">
                <p className="text-sm text-amber-800">
                  <span className="font-bold">⚠️ Importante:</span> coloca el concepto{" "}
                  <span className="font-mono font-bold">{estado.concepto}</span>{" "}
                  exactamente igual. Sin él, no podemos confirmar tu pago.
                </p>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-100 p-6 text-sm text-slate-500 space-y-2">
              <p className="font-bold text-slate-700">Pasos:</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Abre la app de tu banco</li>
                <li>Selecciona Pago Móvil / P2P</li>
                <li>Ingresa los datos de arriba</li>
                <li>Usa <span className="font-mono font-bold">{estado.concepto}</span> como concepto</li>
                <li>Envía el pago — la confirmación es automática</li>
              </ol>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function DataRow({
  label,
  value,
  onCopy,
  copiado,
  destacado,
}: {
  label: string;
  value: string;
  onCopy: () => void;
  copiado: boolean;
  destacado?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between rounded-xl p-3 ${destacado ? "bg-[#3C5ACB]/5 border border-[#3C5ACB]/20" : "bg-slate-50"}`}>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-400 uppercase font-bold">{label}</p>
        <p className={`font-bold ${destacado ? "text-[#3C5ACB] font-mono" : "text-slate-700"} truncate`}>{value}</p>
      </div>
      <button
        onClick={onCopy}
        className="ml-3 text-xs font-bold text-[#3C5ACB] hover:bg-[#3C5ACB]/10 px-3 py-2 rounded-lg transition-colors"
      >
        {copiado ? "✓ Copiado" : "Copiar"}
      </button>
    </div>
  );
}

function productoLabel(tipo: string): string {
  if (tipo === "consultas_pack_30") return "Pack de 30 consultas";
  if (tipo === "plan_ilimitado_mensual") return "Plan Ilimitado (30 días)";
  return tipo;
}
