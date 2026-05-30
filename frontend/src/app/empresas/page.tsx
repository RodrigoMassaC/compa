"use client";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { getUser, type AuthUser } from "@/lib/auth";

export default function EmpresasPage() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

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
            <Link href="/chat" className="hover:text-[#3C5ACB] transition-colors">Para Compradores</Link>
            <Link href="/empresas" className="text-[#3C5ACB]">Compi (Empresas)</Link>
            <Link href="/planes" className="hover:text-[#3C5ACB] transition-colors">Planes</Link>
          </nav>
          <div className="flex items-center gap-3">
            {user ? (
              <Link href="/dashboard" className="bg-[#3C5ACB] text-white hover:bg-[#2F47A8] px-5 py-2 rounded-full text-sm font-bold transition-colors">
                Mi panel
              </Link>
            ) : (
              <Link href="/auth" className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors">
                Iniciar sesión
              </Link>
            )}
            <Link href="/empresas/solicitar" className="bg-[#DDDD4A] hover:bg-[#C8C830] text-[#1E2E7A] px-6 py-2.5 rounded-full text-sm font-extrabold transition-colors">
              Solicitar acceso
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* ── HERO ── */}
        <section className="py-20 bg-gradient-to-b from-[#F5F7FF] to-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-7">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white text-[#3C5ACB] text-xs font-extrabold border border-[#DDE4FA]">
              <span className="flex h-2 w-2 rounded-full bg-[#DDDD4A]"></span>
              Compi · Inteligencia de mercado para retail venezolano
            </div>
            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-900 leading-tight">
              Sabes <span className="text-[#3C5ACB]">cómo está el mercado</span>,<br />
              decides con datos.
            </h1>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto leading-relaxed">
              <strong className="text-slate-700">Compi</strong> es el producto de inteligencia comercial de Compa para
              supermercados, farmacias y bodegas en Venezuela. Saca insights de cómo se compara tu cadena vs.
              el mercado en tiempo real — sin instalar nada, sin equipos de pricing.
            </p>
            <div className="flex flex-wrap justify-center gap-3 pt-4">
              <Link
                href="/empresas/solicitar"
                className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-extrabold px-8 py-4 rounded-full text-lg transition-colors"
              >
                Solicitar acceso
              </Link>
              <a
                href="#planes"
                className="border-2 border-slate-200 hover:border-[#3C5ACB] text-slate-700 font-bold px-8 py-4 rounded-full text-lg transition-colors"
              >
                Ver planes ↓
              </a>
            </div>
          </div>
        </section>

        {/* ── VALOR ── */}
        <section className="py-20 bg-white">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-14">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Qué ves con Compi</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900">
                Inteligencia que no tenías antes
              </h2>
            </div>
            <div className="grid gap-6 md:grid-cols-3">
              <ValueCard icon="📊" title="Posición de precio" texto="Si estás por encima, debajo o en línea con el promedio del mercado. Por rubro y por producto." />
              <ValueCard icon="📍" title="Análisis por zona" texto="En qué regiones se compara más tu cadena. Cuáles concentran más consultas." />
              <ValueCard icon="👥" title="Quiénes te buscan" texto="Distribución por sexo, ciudad y estado de quienes consultan productos relacionados con tu rubro." />
              <ValueCard icon="📈" title="Tendencias de mercado" texto="Qué rubros están subiendo en interés. Variaciones mensuales. Estacionalidad real." />
              <ValueCard icon="🔔" title="Alertas inteligentes" texto="Cuando un competidor baja precio, sube tráfico de tu rubro o tus precios se desalinean entre sucursales." />
              <ValueCard icon="📑" title="Reportes accionables" texto="Mensual ejecutivo + descargas Excel cuando quieras. Premium incluye recomendaciones estratégicas." />
            </div>
          </div>
        </section>

        {/* ── PLANES ── */}
        <section className="py-20 bg-[#F5F7FF]" id="planes">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-14">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Planes Compi</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">
                Elige el nivel de profundidad
              </h2>
              <p className="text-slate-500">Precios bajo solicitud — adaptados al tamaño y necesidad de tu cadena.</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-3 items-start">
              {/* BÁSICO */}
              <PlanCard
                nombre="Básico"
                titulo="Para arrancar con inteligencia de mercado"
                cta="Solicitar Básico"
                ctaUrl="/empresas/solicitar?plan=basico"
                incluye={[
                  "Análisis de precios por rubro: mínimo, máximo, promedio",
                  "Tu posición en el rango del mercado",
                  "Distribución demográfica de quien consulta (sexo, edad, zona)",
                  "Regiones donde tu cadena es más comparada",
                  "Rubros top del mes + variaciones",
                  "Evolución de búsquedas de tu cadena",
                  "Clicks generados hacia tu web/WhatsApp",
                  "Dashboard dinámico personalizable",
                  "Reporte mensual PDF + Excel",
                ]}
                noIncluye={[
                  "Información a nivel producto o SKU",
                  "Análisis por sucursal",
                  "Alertas automáticas",
                  "Recomendaciones accionables",
                ]}
              />

              {/* PRO — destacado */}
              <PlanCard
                nombre="Pro"
                titulo="Para tomar decisiones con detalle"
                cta="Solicitar Pro"
                ctaUrl="/empresas/solicitar?plan=pro"
                destacado
                incluye={[
                  "Todo lo del Básico, más:",
                  "Análisis de precios por sucursal",
                  "Comparación interna entre sucursales",
                  "Segmentación de clientela por zona (edad, sexo)",
                  "Listado detallado de productos",
                  "Productos destacados por zona y sucursal",
                  "Cruce dinámico de variables (rubro × zona × precio)",
                  "Alertas inteligentes (caídas/subidas de interés, desalineaciones)",
                  "Posición de precio vs. promedio",
                  "Históricos ampliados",
                  "Tablas Excel exportables ilimitadas",
                ]}
              />

              {/* PREMIUM */}
              <PlanCard
                nombre="Premium"
                titulo="Cuando lo quieres a tu medida"
                cta="Solicitar Premium"
                ctaUrl="/empresas/solicitar?plan=premium"
                incluye={[
                  "Todo lo del Pro, más:",
                  "Selección de módulos según tu necesidad",
                  "Elige foco: ventas / tráfico / margen / posicionamiento",
                  "Sensibilidad de alertas configurable",
                  "Insights estratégicos con contexto (no fórmulas opacas)",
                  "Recomendaciones tipo: \"tu precio es bajo pero el volumen no acompaña\"",
                  "Identificación de productos sub/sobre-valorados",
                  "Reportes personalizados visuales",
                  "Frecuencia: mensual, trimestral o a demanda",
                  "Acompañamiento light: sesiones de lectura de resultados",
                  "Ajuste continuo del enfoque",
                ]}
              />
            </div>

            <p className="text-center text-sm text-slate-400 mt-10">
              Solicitas → Te contactamos → Activamos tu cuenta. <strong className="text-slate-600">Sin instalación ni integraciones técnicas</strong>.
            </p>
          </div>
        </section>

        {/* ── CÓMO FUNCIONA ── */}
        <section className="py-20 bg-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">Cómo funciona</h2>
              <p className="text-slate-500">4 pasos, todos gestionados por nosotros.</p>
            </div>
            <div className="grid gap-6 md:grid-cols-4">
              <Step n={1} titulo="Solicitas acceso" texto="Form de 30 segundos. Nos dices qué cadena eres y qué plan te interesa." />
              <Step n={2} titulo="Te contactamos" texto="Validamos tu cadena, definimos foco, confirmamos plan. 24-48 horas." />
              <Step n={3} titulo="Activamos tu panel" texto="Tu dashboard queda listo. Sin instalación. Acceso desde el navegador." />
              <Step n={4} titulo="Tomas decisiones" texto="Revisas insights, exportas reportes. Premium incluye sesiones con nosotros." />
            </div>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section className="py-20 bg-[#F5F7FF]">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">Preguntas frecuentes</h2>
            </div>
            <div className="space-y-3">
              <FAQ q="¿Cómo obtienen los datos?">
                Compa monitorea precios públicos de las principales cadenas de Venezuela (Farmatodo, Farmago,
                Locatel, Central Madeirense, Excelsior Gama, etc.) en tiempo real. Además agregamos
                comportamiento anonimizado de cómo los compradores buscan y comparan productos.
              </FAQ>
              <FAQ q="¿Mi competencia ve mis precios o que estoy registrado?">
                <strong className="text-slate-800">No.</strong> Las cuentas Compi son confidenciales.
                Ninguna otra cadena ve tu actividad ni tus configuraciones. Los datos comparativos siempre
                son agregados — nunca identificamos a un cliente específico.
              </FAQ>
              <FAQ q="¿Por qué los precios no están publicados?">
                Cada cadena tiene necesidades distintas (tamaño, sucursales, profundidad, foco). Trabajamos los
                precios bajo solicitud para asegurarnos de que pagues por lo que realmente vas a usar.
              </FAQ>
              <FAQ q="¿Cuánto demora la activación?">
                Entre 24 y 48 horas después de tu solicitud. Te contactamos para validar y configurar el foco
                del panel antes de activar.
              </FAQ>
              <FAQ q="¿Puedo subir de plan después?">
                Sí, en cualquier momento. Si empiezas con Básico y necesitas Pro, lo activamos sin perder
                el histórico ni la configuración.
              </FAQ>
              <FAQ q="¿Tienen integraciones por API?">
                El plan Premium incluye acceso a API REST para integrar los datos con tu ERP, e-commerce o
                BI interno. Los planes Básico y Pro usan el dashboard web.
              </FAQ>
            </div>
          </div>
        </section>

        {/* ── CTA FINAL ── */}
        <section className="py-20 bg-[#3C5ACB] text-white">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">
              Empieza a decidir con datos
            </h2>
            <p className="text-lg text-blue-100 mb-8">
              Cuéntanos sobre tu cadena. Te contactamos para activar tu Compi en menos de 48h.
            </p>
            <Link
              href="/empresas/solicitar"
              className="inline-block bg-[#DDDD4A] hover:bg-[#C8C830] text-[#1E2E7A] font-extrabold px-10 py-4 rounded-full text-lg transition-colors"
            >
              Solicitar acceso →
            </Link>
          </div>
        </section>

        {/* ── FOOTER ── */}
        <footer className="bg-white border-t border-slate-100 py-10">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-blue.png" alt="Compa" width={32} height={32} className="rounded-lg" />
              <span className="font-extrabold text-slate-800">Compa</span>
            </Link>
            <p className="text-xs text-slate-400">
              © {new Date().getFullYear()} Compa · Compi es el producto B2B de Compa.
            </p>
            <div className="flex gap-6 text-sm text-slate-500">
              <Link href="/terminos" className="hover:text-[#3C5ACB]">Términos</Link>
              <Link href="/privacidad" className="hover:text-[#3C5ACB]">Privacidad</Link>
              <Link href="/chat" className="hover:text-[#3C5ACB]">Para compradores</Link>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

/* ── Componentes ────────────────────────────────────────────────────────── */

function ValueCard({ icon, title, texto }: { icon: string; title: string; texto: string }) {
  return (
    <div className="bg-[#F5F7FF] rounded-3xl p-6 border border-slate-100">
      <div className="text-3xl mb-3">{icon}</div>
      <h3 className="font-extrabold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 leading-relaxed">{texto}</p>
    </div>
  );
}

function PlanCard({
  nombre,
  titulo,
  cta,
  ctaUrl,
  incluye,
  noIncluye,
  destacado,
}: {
  nombre: string;
  titulo: string;
  cta: string;
  ctaUrl: string;
  incluye: string[];
  noIncluye?: string[];
  destacado?: boolean;
}) {
  return (
    <div className={`bg-white rounded-3xl p-8 shadow-sm flex flex-col ${destacado ? "border-2 border-[#3C5ACB] shadow-xl relative" : "border border-slate-100"}`}>
      {destacado && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#DDDD4A] text-[#1E2E7A] text-xs font-extrabold px-4 py-1 rounded-full">
          ⭐ Más popular
        </div>
      )}
      <p className={`text-xs font-bold uppercase tracking-widest mb-2 ${destacado ? "text-[#3C5ACB]" : "text-slate-400"}`}>
        Plan {nombre}
      </p>
      <h3 className="text-2xl font-extrabold text-slate-900 mb-2">Compi {nombre}</h3>
      <p className="text-sm text-slate-500 mb-6 min-h-[40px]">{titulo}</p>

      <div className="mb-6 py-4 border-y border-slate-100">
        <p className="text-3xl font-extrabold text-slate-900">Bajo solicitud</p>
        <p className="text-xs text-slate-400 mt-1">Adaptado a tu cadena</p>
      </div>

      <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Incluye</p>
      <ul className="space-y-2 text-sm text-slate-600 flex-1 mb-6">
        {incluye.map((f, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="text-[#3C5ACB] font-bold mt-0.5 flex-shrink-0">✓</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {noIncluye && (
        <>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 mt-2">No incluye</p>
          <ul className="space-y-1 text-xs text-slate-400 mb-6">
            {noIncluye.map((f, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-slate-300 mt-0.5 flex-shrink-0">✕</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <Link
        href={ctaUrl}
        className={`block text-center font-extrabold px-6 py-3 rounded-full transition-colors ${
          destacado
            ? "bg-[#3C5ACB] hover:bg-[#2F47A8] text-white"
            : "bg-slate-100 hover:bg-slate-200 text-slate-700"
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}

function Step({ n, titulo, texto }: { n: number; titulo: string; texto: string }) {
  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-6 text-center shadow-sm">
      <div className="w-10 h-10 mx-auto bg-[#3C5ACB] text-white rounded-full flex items-center justify-center text-base font-extrabold mb-4">
        {n}
      </div>
      <h3 className="font-extrabold text-slate-800 text-sm mb-2">{titulo}</h3>
      <p className="text-xs text-slate-500 leading-relaxed">{texto}</p>
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
