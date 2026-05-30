"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken, getUser, type AuthUser } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type TipoProducto = "consultas_pack_30" | "plan_ilimitado_mensual";

export default function PlanesPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [comprando, setComprando] = useState<TipoProducto | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  async function comprar(tipo: TipoProducto) {
    setError(null);
    const token = getToken();
    if (!token) {
      router.push("/auth?next=/planes");
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
      router.push(`/comprar/${data.concepto}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al crear el pago");
      setComprando(null);
    }
  }

  function ctaEmpezar() {
    if (user) router.push("/chat");
    else router.push("/auth?mode=register");
  }

  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans">
      {/* ── HEADER ── */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <Image src="/logo-blue.png" alt="Compa" width={40} height={40} className="rounded-xl" />
            <span className="font-extrabold text-2xl tracking-tight text-slate-800">Compa</span>
          </Link>
          <nav className="hidden md:flex items-center gap-10 text-sm font-semibold text-slate-600">
            <Link href="/chat" className="hover:text-[#3C5ACB] transition-colors">Buscar precios</Link>
            <Link href="/planes" className="text-[#3C5ACB]">Planes</Link>
            {user && (
              <Link href="/consultas" className="hover:text-[#3C5ACB] transition-colors">Mi cuenta</Link>
            )}
          </nav>
          <div className="flex items-center gap-3">
            {user ? (
              <Link href="/perfil" className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors">
                {user.nombre_completo?.split(" ")[0] || "Mi perfil"}
              </Link>
            ) : (
              <>
                <Link href="/auth" className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors">
                  Iniciar sesión
                </Link>
                <Link href="/auth?mode=register" className="bg-[#3C5ACB] text-white hover:bg-[#2F47A8] px-6 py-2.5 rounded-full text-sm font-bold transition-colors">
                  Registrarse gratis
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        {/* ── HERO ── */}
        <section className="pt-16 pb-12 bg-[#F5F7FF]">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white text-[#3C5ACB] text-xs font-bold border border-[#DDE4FA]">
              <span className="flex h-2 w-2 rounded-full bg-[#DDDD4A]"></span>
              Pago Móvil venezolano · Conciliación automática
            </div>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900">
              Empieza gratis.{" "}
              <span className="text-[#3C5ACB]">Mejora cuando lo necesites.</span>
            </h1>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              Compara precios en supermercados y farmacias de toda Venezuela.
              Compra consultas adicionales con Pago Móvil — sin tarjetas, sin salir de tu banco.
            </p>
          </div>
        </section>

        {/* ── PRICING CARDS ── */}
        <section className="py-16 bg-[#F5F7FF]">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            {error && (
              <div className="max-w-md mx-auto mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 text-center">
                {error}
              </div>
            )}
            <div className="grid gap-6 md:grid-cols-3 items-stretch">
              {/* ── Plan Gratis ── */}
              <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 flex flex-col">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Para empezar</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mb-1">Gratis</h3>
                <p className="text-sm text-slate-500 mb-6">Perfecto para probar Compa.</p>
                <div className="mb-6">
                  <span className="text-5xl font-extrabold text-slate-900">$0</span>
                  <span className="text-sm text-slate-400 ml-2">/ siempre</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-600 flex-1 mb-8">
                  <Feature>20 consultas al mes</Feature>
                  <Feature>Se reinicia cada mes</Feature>
                  <Feature>Compara todos los supermercados y farmacias</Feature>
                  <Feature>Precios en USD y Bolívares (tasa BCV)</Feature>
                  <Feature>Sin tarjeta de crédito</Feature>
                </ul>
                <button
                  onClick={ctaEmpezar}
                  className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-6 py-3 rounded-full transition-colors"
                >
                  {user ? "Estás en el plan Gratis" : "Empezar gratis"}
                </button>
              </div>

              {/* ── Pack +30 ── */}
              <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 flex flex-col">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Compra única</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mb-1">Pack +30 consultas</h3>
                <p className="text-sm text-slate-500 mb-6">Cuando necesitas un poco más este mes.</p>
                <div className="mb-6">
                  <span className="text-5xl font-extrabold text-slate-900">$1.50</span>
                  <span className="text-sm text-slate-400 ml-2">una vez</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-600 flex-1 mb-8">
                  <Feature>+30 consultas que se suman a tu cuenta</Feature>
                  <Feature>No expiran nunca</Feature>
                  <Feature>Acumulables (puedes comprar varios)</Feature>
                  <Feature>Activación inmediata por Pago Móvil</Feature>
                  <Feature>Sin compromiso, sin renovación</Feature>
                </ul>
                <button
                  onClick={() => comprar("consultas_pack_30")}
                  disabled={comprando !== null}
                  className="w-full bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:bg-slate-300 text-white font-bold px-6 py-3 rounded-full transition-colors"
                >
                  {comprando === "consultas_pack_30" ? "Procesando…" : "Comprar Pack"}
                </button>
              </div>

              {/* ── Plan Ilimitado (DESTACADO) ── */}
              <div className="bg-white rounded-3xl border-2 border-[#3C5ACB] shadow-lg p-8 flex flex-col relative">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#DDDD4A] text-[#1E2E7A] text-xs font-extrabold px-4 py-1 rounded-full">
                  ⭐ Más popular
                </div>
                <p className="text-xs font-bold text-[#3C5ACB] uppercase tracking-widest mb-2">Para uso intensivo</p>
                <h3 className="text-2xl font-extrabold text-slate-900 mb-1">Plan Ilimitado</h3>
                <p className="text-sm text-slate-500 mb-6">Sin contar consultas durante 30 días.</p>
                <div className="mb-6">
                  <span className="text-5xl font-extrabold text-slate-900">$5</span>
                  <span className="text-sm text-slate-400 ml-2">/ mes</span>
                </div>
                <ul className="space-y-3 text-sm text-slate-600 flex-1 mb-8">
                  <Feature highlight>Consultas ilimitadas por 30 días</Feature>
                  <Feature>Renovación opcional, no automática</Feature>
                  <Feature>Combinable con Packs (los packs no se gastan mientras esté activo)</Feature>
                  <Feature>Ideal para hacer la lista del mes completa</Feature>
                  <Feature>Activación inmediata por Pago Móvil</Feature>
                </ul>
                <button
                  onClick={() => comprar("plan_ilimitado_mensual")}
                  disabled={comprando !== null}
                  className="w-full bg-[#DDDD4A] hover:bg-[#C8C830] disabled:bg-slate-300 text-[#1E2E7A] font-bold px-6 py-3 rounded-full transition-colors"
                >
                  {comprando === "plan_ilimitado_mensual" ? "Procesando…" : "Activar Plan"}
                </button>
              </div>
            </div>

            <p className="text-center text-xs text-slate-400 mt-8">
              Todos los pagos procesados por <span className="font-semibold">Mibanco (R4 Conecta)</span>.
              Tu cuenta se acredita automáticamente en segundos.
            </p>
          </div>
        </section>

        {/* ── CÓMO FUNCIONA EL PAGO ── */}
        <section className="py-20 bg-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">
                Cómo funciona el pago
              </h2>
              <p className="text-lg text-slate-500 max-w-2xl mx-auto">
                100% Pago Móvil venezolano. Sin tarjetas. Sin salir de tu banco.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-4">
              <Step n={1} icon="🛒" title="Eliges tu plan">
                Pack +30 ($1.50) o Plan Ilimitado ($5/mes) desde esta página.
              </Step>
              <Step n={2} icon="🔢" title="Te damos un código">
                Generamos un concepto único tipo <span className="font-mono font-bold">CR123456</span> y te mostramos los datos exactos.
              </Step>
              <Step n={3} icon="📱" title="Haces Pago Móvil normal">
                Desde tu app del banco (cualquiera) al teléfono que te damos, con ese concepto.
              </Step>
              <Step n={4} icon="✅" title="Activación automática">
                En segundos tu cuenta se acredita. No necesitas confirmar nada.
              </Step>
            </div>

            <div className="mt-12 bg-[#F5F7FF] rounded-2xl p-6 max-w-3xl mx-auto text-center">
              <p className="text-sm text-slate-600">
                <span className="font-bold text-slate-800">¿Por qué Pago Móvil?</span>{" "}
                Porque ya lo usas todos los días para pagar todo en Venezuela.
                No te pedimos tarjeta, no tienes que crear cuenta en otra plataforma,
                y la conciliación es instantánea gracias a la integración con Mibanco.
              </p>
            </div>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section className="py-20 bg-[#F5F7FF]">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">
                Preguntas frecuentes
              </h2>
              <p className="text-lg text-slate-500">Lo que la gente nos pregunta antes de pagar.</p>
            </div>

            <div className="space-y-4">
              <FAQ q="¿Es seguro pagar por aquí?">
                Sí. El pago lo procesa <span className="font-bold">Mibanco</span> a través de{" "}
                <span className="font-bold">R4 Conecta</span>, un servicio regulado en Venezuela.
                Compa nunca ve ni guarda tus datos bancarios — tú pagas desde tu propia app del banco.
              </FAQ>
              <FAQ q="¿Cuánto tarda en activarse mi compra?">
                Generalmente <span className="font-bold">segundos</span>. Apenas Mibanco recibe tu Pago
                Móvil, nos notifica automáticamente y tu cuenta se acredita. Verás el cambio en tiempo real
                en la pantalla de confirmación.
              </FAQ>
              <FAQ q="¿Qué pasa si me equivoco con el concepto?">
                Si pones un concepto distinto al que te dimos, el pago{" "}
                <span className="font-bold">no se podrá conciliar automáticamente</span>. El pendiente
                queda activo por 30 minutos; si no llega a tiempo, lo cancelas y generas otro.
                Sin riesgo de perder tu plata: el dinero está en tu banco hasta que tú lo envíes.
              </FAQ>
              <FAQ q="¿Puedo combinar Pack +30 con el Plan Ilimitado?">
                Sí. Si tienes Plan Ilimitado activo, los packs no se consumen — se guardan para cuando
                expire el plan. Si compras packs sin tener plan, se suman directo a tu cupo mensual.
              </FAQ>
              <FAQ q="¿Desde qué banco puedo pagar?">
                Desde <span className="font-bold">cualquier banco venezolano</span> con Pago Móvil:
                Banco de Venezuela, Mercantil, Banesco, BBVA Provincial, Banco del Tesoro, BFC, 100% Banco
                y todos los demás de la red Pago Móvil.
              </FAQ>
            </div>
          </div>
        </section>

        {/* ── CTA FINAL ── */}
        <section className="py-20 bg-[#3C5ACB] text-white">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">
              Listo para ahorrar en cada compra
            </h2>
            <p className="text-lg text-blue-100 mb-8">
              Únete a miles de venezolanos que ya comparan precios antes de salir al supermercado.
            </p>
            <button
              onClick={ctaEmpezar}
              className="bg-white hover:bg-blue-50 text-[#3C5ACB] font-bold px-8 py-4 rounded-full text-lg transition-colors"
            >
              {user ? "Ir al chat →" : "Empezar gratis →"}
            </button>
          </div>
        </section>

        {/* ── FOOTER simple ── */}
        <footer className="bg-white border-t border-slate-100 py-10">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-blue.png" alt="Compa" width={32} height={32} className="rounded-lg" />
              <span className="font-extrabold text-slate-800">Compa</span>
            </Link>
            <p className="text-xs text-slate-400">
              © {new Date().getFullYear()} Compa · Democratizando los precios en Venezuela.
            </p>
            <div className="flex gap-6 text-sm text-slate-500">
              <Link href="/terminos" className="hover:text-[#3C5ACB]">Términos</Link>
              <Link href="/privacidad" className="hover:text-[#3C5ACB]">Privacidad</Link>
              <Link href="/chat" className="hover:text-[#3C5ACB]">Chat</Link>
              {user && <Link href="/consultas" className="hover:text-[#3C5ACB]">Mi cuenta</Link>}
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

/* ── Componentes auxiliares ───────────────────────────────────────────────── */

function Feature({ children, highlight }: { children: React.ReactNode; highlight?: boolean }) {
  return (
    <li className="flex items-start gap-2">
      <span className={`flex-shrink-0 w-5 h-5 rounded-full ${highlight ? "bg-[#DDDD4A]" : "bg-[#3C5ACB]/10"} flex items-center justify-center mt-0.5`}>
        <svg className={`w-3 h-3 ${highlight ? "text-[#1E2E7A]" : "text-[#3C5ACB]"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </span>
      <span className={highlight ? "font-bold text-slate-800" : ""}>{children}</span>
    </li>
  );
}

function Step({
  n,
  icon,
  title,
  children,
}: {
  n: number;
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 bg-[#3C5ACB]/10 text-[#3C5ACB] rounded-full flex items-center justify-center text-sm font-extrabold">
          {n}
        </div>
        <div className="text-2xl">{icon}</div>
      </div>
      <h3 className="font-extrabold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 leading-relaxed">{children}</p>
    </div>
  );
}

function FAQ({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <details className="group bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">
      <summary className="font-bold text-slate-800 cursor-pointer flex items-center justify-between list-none">
        <span>{q}</span>
        <span className="text-[#3C5ACB] text-xl group-open:rotate-45 transition-transform">+</span>
      </summary>
      <div className="mt-3 text-sm text-slate-600 leading-relaxed">{children}</div>
    </details>
  );
}
