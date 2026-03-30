import Link from "next/link";
import Image from "next/image";

export const metadata = { title: "Términos y Condiciones — Compa" };

export default function TerminosPage() {
  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <Link href="/auth" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Volver
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 md:p-12">

          <h1 className="text-3xl font-extrabold text-slate-900 mb-2">
            Política de Privacidad y Protección de Datos
          </h1>
          <p className="text-sm text-slate-400 mb-8">Última actualización: marzo 2026</p>

          <div className="prose prose-slate max-w-none space-y-6 text-sm leading-relaxed text-slate-600">

            <p>
              En <strong className="text-slate-800">Compa</strong>, reafirmamos nuestro compromiso con la privacidad
              y la seguridad de la información de nuestros usuarios. En cumplimiento con lo establecido en la
              Constitución de la República Bolivariana de Venezuela, la Ley Orgánica de Protección de Datos
              Personales y su Reglamento, así como demás normativas aplicables en la materia, informamos lo siguiente:
            </p>

            <div className="border-l-4 border-[#3C5ACB] pl-5 space-y-5">

              <div>
                <h2 className="text-base font-bold text-slate-800 mb-1">
                  1. No difusión de datos
                </h2>
                <p>
                  Garantizamos que los datos personales aportados por los usuarios serán tratados con estricta
                  confidencialidad. Bajo ninguna circunstancia serán difundidos, comercializados, transferidos
                  ni compartidos con terceros sin el consentimiento expreso, previo e informado del titular,
                  salvo en los casos expresamente autorizados por la ley.
                </p>
              </div>

              <div>
                <h2 className="text-base font-bold text-slate-800 mb-1">
                  2. Finalidad del tratamiento
                </h2>
                <p>
                  La recolección de datos tiene como única finalidad el funcionamiento óptimo de la aplicación,
                  la mejora continua de nuestros servicios y la atención de los requerimientos de los usuarios,
                  siempre dentro del marco legal vigente.
                </p>
              </div>

              <div>
                <h2 className="text-base font-bold text-slate-800 mb-1">
                  3. Medidas de seguridad
                </h2>
                <p>
                  Implementamos las medidas técnicas, organizativas y administrativas necesarias para salvaguardar
                  la integridad, disponibilidad y confidencialidad de los datos personales frente a cualquier
                  acceso no autorizado, pérdida o alteración.
                </p>
              </div>

              <div>
                <h2 className="text-base font-bold text-slate-800 mb-1">
                  4. Ejercicio de los derechos (ARCO)
                </h2>
                <p>
                  Los titulares de los datos podrán ejercer sus derechos de acceso, rectificación, actualización,
                  cancelación y oposición conforme al procedimiento establecido en la normativa nacional,
                  comunicándose a través de{" "}
                  <a href="mailto:privacidad@compa.com.ve" className="text-[#3C5ACB] font-medium hover:underline">
                    privacidad@compa.com.ve
                  </a>.
                </p>
              </div>

            </div>

            <p className="text-slate-500 border-t border-slate-100 pt-6">
              Esta política refleja nuestro compromiso con la transparencia y la protección de los datos personales,
              actuando siempre bajo los principios de licitud, lealtad y responsabilidad.
            </p>

          </div>

          <div className="mt-10 flex gap-4">
            <Link
              href="/auth?mode=register"
              className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold text-sm px-6 py-3 rounded-full transition-colors"
            >
              Crear cuenta gratis
            </Link>
            <Link
              href="/"
              className="border border-slate-200 text-slate-600 font-bold text-sm px-6 py-3 rounded-full hover:bg-slate-50 transition-colors"
            >
              Volver al inicio
            </Link>
          </div>

        </div>
      </main>
    </div>
  );
}
