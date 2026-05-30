"use client";
import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
import { useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function SolicitarForm() {
  const searchParams = useSearchParams();
  const planInicial = searchParams.get("plan") || "no_seguro";

  const [nombre, setNombre] = useState("");
  const [rif, setRif] = useState("");
  const [sector, setSector] = useState("");
  const [contactoNombre, setContactoNombre] = useState("");
  const [contactoEmail, setContactoEmail] = useState("");
  const [contactoTelefono, setContactoTelefono] = useState("");
  const [planInteres, setPlanInteres] = useState<string>(planInicial);
  const [mensaje, setMensaje] = useState("");

  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPlanInteres(planInicial);
  }, [planInicial]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const res = await fetch(`${API}/b2b/solicitar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre_comercial: nombre.trim(),
          rif: rif.trim() || null,
          sector: sector || null,
          contacto_nombre: contactoNombre.trim(),
          contacto_email: contactoEmail.trim(),
          contacto_telefono: contactoTelefono.trim() || null,
          plan_interes: planInteres,
          mensaje: mensaje.trim() || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "No se pudo enviar la solicitud");
      }
      setEnviado(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error inesperado");
    } finally {
      setEnviando(false);
    }
  }

  if (enviado) {
    return (
      <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-10 text-center">
        <div className="text-6xl mb-4">✅</div>
        <h2 className="text-2xl font-extrabold text-slate-900 mb-3">Solicitud enviada</h2>
        <p className="text-slate-500 mb-8 max-w-md mx-auto">
          Recibimos tu solicitud para <strong>{nombre}</strong>. Te contactamos en las próximas 24-48 horas
          al correo <strong className="text-slate-700">{contactoEmail}</strong> para validar y activar tu cuenta Compi.
        </p>
        <div className="flex justify-center gap-3 flex-wrap">
          <Link href="/" className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold px-6 py-3 rounded-full transition-colors">
            Volver al inicio
          </Link>
          <Link href="/empresas" className="border border-slate-200 text-slate-700 font-bold px-6 py-3 rounded-full hover:bg-slate-50 transition-colors">
            Ver planes Compi
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={enviar} className="bg-white rounded-3xl shadow-sm border border-slate-100 p-8 md:p-10 space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 mb-2">Solicitar acceso a Compi</h1>
        <p className="text-sm text-slate-500">
          Cuéntanos sobre tu cadena. Sin compromiso — solo tomamos contacto para validar tu plan.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="Nombre comercial *" required>
          <input
            type="text"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
            placeholder="Ej: Farmacia Bermúdez"
            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
          />
        </Field>
        <Field label="RIF (opcional)">
          <input
            type="text"
            value={rif}
            onChange={(e) => setRif(e.target.value)}
            placeholder="J-12345678-9"
            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
          />
        </Field>
      </div>

      <Field label="Sector *">
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          required
          className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB] bg-white"
        >
          <option value="">Elige una opción…</option>
          <option value="supermercado">Supermercado</option>
          <option value="farmacia">Farmacia</option>
          <option value="bodega">Bodega / abasto</option>
          <option value="licoreria">Licorería</option>
          <option value="otros">Otros</option>
        </select>
      </Field>

      <div className="border-t border-slate-100 pt-6 space-y-4">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Contacto</p>

        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Tu nombre *">
            <input
              type="text"
              value={contactoNombre}
              onChange={(e) => setContactoNombre(e.target.value)}
              required
              placeholder="Nombre y apellido"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
            />
          </Field>
          <Field label="Teléfono (opcional)">
            <input
              type="tel"
              value={contactoTelefono}
              onChange={(e) => setContactoTelefono(e.target.value)}
              placeholder="0414-1234567"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
            />
          </Field>
        </div>

        <Field label="Email *">
          <input
            type="email"
            value={contactoEmail}
            onChange={(e) => setContactoEmail(e.target.value)}
            required
            placeholder="tu@correo.com"
            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
          />
        </Field>
      </div>

      <div className="border-t border-slate-100 pt-6 space-y-4">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Plan de interés</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { value: "basico", label: "Básico" },
            { value: "pro", label: "Pro" },
            { value: "premium", label: "Premium" },
            { value: "no_seguro", label: "No estoy seguro" },
          ].map((p) => (
            <label
              key={p.value}
              className={`cursor-pointer border-2 rounded-xl py-2.5 px-3 text-center text-sm font-bold transition-colors ${
                planInteres === p.value
                  ? "border-[#3C5ACB] bg-[#3C5ACB]/5 text-[#3C5ACB]"
                  : "border-slate-200 text-slate-500 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="plan_interes"
                value={p.value}
                checked={planInteres === p.value}
                onChange={(e) => setPlanInteres(e.target.value)}
                className="sr-only"
              />
              {p.label}
            </label>
          ))}
        </div>
      </div>

      <Field label="Mensaje (opcional)">
        <textarea
          value={mensaje}
          onChange={(e) => setMensaje(e.target.value)}
          rows={4}
          placeholder="Cuéntanos cualquier cosa útil: cuántas sucursales tienes, qué te interesa más medir, etc."
          className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
        />
      </Field>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="flex items-center justify-between pt-2">
        <Link href="/empresas" className="text-sm text-slate-500 hover:text-slate-700 font-bold">
          ← Volver
        </Link>
        <button
          type="submit"
          disabled={enviando}
          className="bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:bg-slate-300 text-white font-extrabold px-8 py-3 rounded-full transition-colors"
        >
          {enviando ? "Enviando…" : "Enviar solicitud"}
        </button>
      </div>

      <p className="text-xs text-slate-400 text-center pt-2">
        Al enviar aceptas nuestra{" "}
        <Link href="/privacidad" className="text-[#3C5ACB] hover:underline">política de privacidad</Link>.
      </p>
    </form>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block">
      <span className="block text-xs font-bold text-slate-500 uppercase tracking-wide mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">{" "}</span>}
      </span>
      {children}
    </label>
  );
}

export default function SolicitarPage() {
  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <Link href="/empresas" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Compi
        </Link>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-10">
        <Suspense fallback={<div className="text-center py-20 text-slate-400">Cargando…</div>}>
          <SolicitarForm />
        </Suspense>
      </main>
    </div>
  );
}
