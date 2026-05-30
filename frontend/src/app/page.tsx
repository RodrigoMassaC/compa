import Link from "next/link";
import Image from "next/image";

export default function LandingPage() {
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
            <Link href="#compradores" className="hover:text-[#3C5ACB] transition-colors">Para Compradores</Link>
            <Link href="/planes" className="hover:text-[#3C5ACB] transition-colors">Planes</Link>
            <Link href="/empresas" className="hover:text-[#3C5ACB] transition-colors">Compi (Empresas)</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/auth" className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors">
              Iniciar sesión
            </Link>
            <Link href="/auth?mode=register" className="bg-[#3C5ACB] text-white hover:bg-[#2F47A8] px-6 py-2.5 rounded-full text-sm font-bold transition-colors">
              Registrarse gratis
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* ── HERO ── */}
        <section className="pt-16 pb-28 bg-[#F5F7FF]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white text-[#3C5ACB] text-xs font-bold border border-[#DDE4FA]">
              <span className="flex h-2 w-2 rounded-full bg-[#DDDD4A]"></span>
              Impulsado por IA
            </div>
            <h1 className="text-5xl lg:text-7xl font-extrabold text-slate-900 tracking-tight leading-tight">
              Encuentra siempre el{" "}
              <span className="text-[#3C5ACB]">precio más bajo</span>,{" "}
              sin caminar de más.
            </h1>
            <p className="text-lg text-slate-500 max-w-xl mx-auto">
              Tu asistente personal de compras. Compa compara precios en supermercados y farmacias en tiempo real con tasa BCV.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-2">
              <Link
                href="/chat"
                className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-full bg-[#3C5ACB] text-white hover:bg-[#2F47A8] font-bold text-sm transition-colors"
              >
                Buscar precios ahora →
              </Link>
              <Link
                href="https://wa.me/"
                className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-full bg-[#DDDD4A] text-[#1E2E7A] hover:bg-[#C8C830] font-bold text-sm transition-colors"
              >
                Hablar por WhatsApp
              </Link>
            </div>
          </div>
        </section>

        {/* ── TIENDAS ── */}
        <section className="bg-white py-12 border-y border-slate-100">
          <div className="max-w-7xl mx-auto px-4 text-center">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-8">Comparamos precios en</p>
            <div className="flex flex-wrap justify-center items-center gap-10 opacity-40">
              <span className="font-bold text-xl text-slate-800">Farmatodo</span>
              <span className="font-bold text-xl text-slate-800">Farmago</span>
              <span className="font-bold text-xl text-slate-800">Locatel</span>
              <span className="font-bold text-xl text-slate-800">C. Madeirense</span>
              <span className="font-bold text-xl text-slate-800">Excelsior Gama</span>
            </div>
          </div>
        </section>

        {/* ── FEATURES B2C ── */}
        <section className="py-24 bg-white" id="compradores">
          <div className="max-w-7xl mx-auto px-4 text-center">
            <h2 className="text-4xl font-extrabold text-slate-900 mb-4">Tu asistente de ahorro inteligente</h2>
            <p className="text-slate-500 max-w-2xl mx-auto mb-16">Herramientas gratuitas diseñadas para maximizar tu presupuesto diario.</p>
            <div className="grid md:grid-cols-3 gap-8 text-left">
              <div className="p-8 rounded-3xl border border-[#DDE4FA] bg-[#F5F7FF]">
                <div className="w-10 h-10 bg-[#DDDD4A] rounded-xl mb-4 flex items-center justify-center text-lg">💱</div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Tasa BCV en tiempo real</h3>
                <p className="text-sm text-slate-500">Todos los precios en USD y Bolívares actualizados con la tasa oficial del BCV.</p>
              </div>
              <div className="p-8 rounded-3xl border border-[#DDE4FA] bg-[#F5F7FF]">
                <div className="w-10 h-10 bg-[#DDDD4A] rounded-xl mb-4 flex items-center justify-center text-lg">🛒</div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Carrito Óptimo</h3>
                <p className="text-sm text-slate-500">Nuestra IA calcula en qué tienda te sale más barata tu lista de compras completa.</p>
              </div>
              <div className="p-8 rounded-3xl border border-[#DDE4FA] bg-[#F5F7FF]">
                <div className="w-10 h-10 bg-[#DDDD4A] rounded-xl mb-4 flex items-center justify-center text-lg">💬</div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Chat con IA</h3>
                <p className="text-sm text-slate-500">Pregunta en lenguaje natural: &ldquo;¿Dónde consigo leche más barata?&rdquo; y obtén respuesta inmediata.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── B2B ── */}
        <section className="bg-[#3C5ACB] text-white py-24" id="empresas">
          <div className="max-w-7xl mx-auto px-4 grid lg:grid-cols-2 gap-16 items-center">
            <div className="bg-white/10 border border-white/20 rounded-3xl p-8">
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div><div className="text-xs text-blue-200">Data Points</div><div className="text-2xl font-bold">12,405</div></div>
                <div><div className="text-xs text-blue-200">Cambio de Precio</div><div className="text-2xl font-bold text-[#DDDD4A]">+8.2%</div></div>
                <div><div className="text-xs text-blue-200">Oportunidades</div><div className="text-2xl font-bold">45</div></div>
              </div>
              <div className="flex items-end justify-between h-40 gap-3">
                <div className="w-full bg-white/20 rounded-t-lg h-1/4"></div>
                <div className="w-full bg-white/20 rounded-t-lg h-2/4"></div>
                <div className="w-full bg-white/20 rounded-t-lg h-1/3"></div>
                <div className="w-full bg-[#DDDD4A] rounded-t-lg h-5/6"></div>
                <div className="w-full bg-white/20 rounded-t-lg h-2/5"></div>
              </div>
            </div>
            <div className="space-y-6">
              <div className="text-xs font-bold tracking-widest text-[#DDDD4A] uppercase">Para Retailers y Marcas</div>
              <h2 className="text-4xl font-extrabold">Inteligencia de mercado a tu alcance.</h2>
              <p className="text-blue-100">Monitorea a tu competencia, detecta oportunidades de precio y optimiza tus márgenes con datos en tiempo real.</p>
              <Link href="/empresas" className="inline-flex px-6 py-3 bg-[#DDDD4A] text-[#1E2E7A] rounded-full font-bold text-sm hover:bg-[#C8C830] transition-colors">
                Ver Planes para Empresas →
              </Link>
            </div>
          </div>
        </section>

        {/* ── CTA FINAL ── */}
        <section className="py-24 bg-white">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <div className="bg-[#F5F7FF] border border-[#DDE4FA] rounded-[3rem] p-12 sm:p-20">
              <Image src="/logo-blue.png" alt="Compa" width={72} height={72} className="mx-auto mb-6 rounded-2xl" />
              <h2 className="text-4xl font-extrabold text-slate-900 mb-6">¿Listo para empezar a ahorrar?</h2>
              <p className="text-lg text-slate-500 mb-10">Únete a miles de compradores inteligentes en Venezuela. Es gratis y fácil de usar.</p>
              <Link href="/chat" className="inline-block px-10 py-4 bg-[#3C5ACB] text-white rounded-full font-bold text-lg hover:bg-[#2F47A8] transition-colors">
                Probar Gratis Ahora →
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* ── FOOTER ── */}
      <footer className="bg-white border-t border-slate-100 pt-16 pb-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-16">
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="flex items-center gap-2 mb-3">
                <Image src="/logo-blue.png" alt="Compa" width={32} height={32} className="rounded-lg" />
                <span className="font-bold text-slate-800 text-lg">Compa</span>
              </Link>
              <p className="text-xs text-slate-400">Democratizando la información de precios en Venezuela.</p>
            </div>
            <div>
              <h4 className="font-bold text-slate-800 mb-4 text-sm">Producto</h4>
              <ul className="space-y-3 text-sm text-slate-500">
                <li><a href="#compradores" className="hover:text-[#3C5ACB]">Para Compradores</a></li>
                <li><Link href="/planes" className="hover:text-[#3C5ACB]">Planes Compa</Link></li>
                <li><Link href="/empresas" className="hover:text-[#3C5ACB]">Compi (Empresas)</Link></li>
                <li><Link href="/empresas/solicitar" className="hover:text-[#3C5ACB]">Solicitar acceso</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-slate-800 mb-4 text-sm">Compañía</h4>
              <ul className="space-y-3 text-sm text-slate-500">
                <li><a href="#" className="hover:text-[#3C5ACB]">Sobre Nosotros</a></li>
                <li><a href="#" className="hover:text-[#3C5ACB]">Blog</a></li>
                <li><a href="#" className="hover:text-[#3C5ACB]">Contacto</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-slate-800 mb-4 text-sm">Legal</h4>
              <ul className="space-y-3 text-sm text-slate-500">
                <li><Link href="/privacidad" className="hover:text-[#3C5ACB]">Privacidad</Link></li>
                <li><Link href="/terminos" className="hover:text-[#3C5ACB]">Términos de Uso</Link></li>
                <li><Link href="/privacidad#cookies" className="hover:text-[#3C5ACB]">Cookies</Link></li>
              </ul>
            </div>
          </div>
          <div className="flex justify-between items-center pt-8 border-t border-slate-100 text-xs text-slate-400">
            <div>© 2026 Compa. Todos los derechos reservados.</div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#DDDD4A]"></span>
              Sistemas operativos
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
