import Link from "next/link";
import Image from "next/image";

export const metadata = { title: "Política de Privacidad — Compa" };

export default function PrivacidadPage() {
  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <Link href="/" className="text-sm font-bold text-[#3C5ACB] hover:underline">
          ← Volver al inicio
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 md:p-12">
          <h1 className="text-3xl font-extrabold text-slate-900 mb-2">
            Política de Privacidad
          </h1>
          <p className="text-sm text-slate-400 mb-8">Última actualización: mayo 2026</p>

          <div className="space-y-7 text-sm leading-relaxed text-slate-600">
            <p>
              En <strong className="text-slate-800">Compa</strong> nos tomamos en serio tu privacidad.
              Esta política describe qué información recolectamos, cómo la usamos y los derechos que tienes
              sobre tus datos, en cumplimiento con la legislación venezolana de protección de datos personales.
            </p>

            <Section title="1. Información que recolectamos">
              <p>Cuando usas Compa podemos recolectar:</p>
              <ul className="list-disc list-inside space-y-1 mt-2">
                <li><strong>Datos de cuenta:</strong> nombre, email, contraseña (encriptada), teléfono, ciudad, sexo y estado.</li>
                <li><strong>Datos de uso:</strong> tus consultas al chat, búsquedas de precios, listas guardadas y carritos consultados.</li>
                <li><strong>Datos de pago:</strong> conceptos, montos y referencias de tus Pago Móvil. <strong className="text-slate-800">Nunca tenemos acceso a tus credenciales bancarias</strong> — el pago lo procesa Mibanco/R4 Conecta directamente.</li>
                <li><strong>Datos técnicos:</strong> dirección IP, navegador, ciudad aproximada y eventos básicos para diagnóstico.</li>
                <li><strong>Si usas WhatsApp:</strong> tu número de teléfono y los mensajes que nos envías al bot.</li>
              </ul>
            </Section>

            <Section title="2. Cómo usamos esa información">
              <ul className="list-disc list-inside space-y-1">
                <li>Para responder tus consultas de precios y mostrarte resultados relevantes.</li>
                <li>Para procesar tus pagos y activar las consultas/planes que compras.</li>
                <li>Para mejorar la calidad del servicio (estadísticas agregadas, anti-abuso, rate limiting).</li>
                <li>Para enviarte notificaciones operacionales (confirmación de pago, recuperación de contraseña).</li>
              </ul>
              <p className="mt-3">
                <strong className="text-slate-800">No vendemos ni alquilamos tus datos a terceros.</strong>
                {" "}Nunca usamos tus datos para enviarte publicidad de marcas externas.
              </p>
            </Section>

            <Section title="3. Compartir con terceros">
              <p>Solo compartimos datos cuando es estrictamente necesario para que el servicio funcione:</p>
              <ul className="list-disc list-inside space-y-1 mt-2">
                <li><strong>Mibanco / R4 Conecta:</strong> para procesar tus pagos. Reciben solo el concepto, monto y referencia bancaria, no tu información personal.</li>
                <li><strong>Meta (WhatsApp Business):</strong> si usas el bot por WhatsApp, los mensajes pasan por su infraestructura conforme a su propia política de privacidad.</li>
                <li><strong>Anthropic (Claude AI):</strong> tus consultas se procesan por su API para generar respuestas. Anthropic no entrena modelos con datos vía API y los retiene por períodos limitados según su política.</li>
                <li><strong>Cuando lo exija la ley:</strong> ante requerimientos formales de autoridades venezolanas competentes.</li>
              </ul>
            </Section>

            <Section title="4. Cookies y tecnologías similares">
              <p>
                Usamos almacenamiento local del navegador (localStorage) para mantener tu sesión iniciada
                y guardar preferencias. No usamos cookies de seguimiento ni publicidad de terceros.
                Puedes borrar este almacenamiento desde tu navegador en cualquier momento (cerrarás la sesión).
              </p>
            </Section>

            <Section title="5. Retención de datos">
              <p>
                Mantenemos tu información mientras tu cuenta esté activa. Si decides eliminarla
                (desde <Link href="/perfil" className="text-[#3C5ACB] font-medium hover:underline">tu perfil</Link>),
                borramos tus datos personales en un máximo de 30 días. Los registros de transacciones
                (pagos) se conservan por el tiempo que exija la normativa contable y fiscal venezolana.
              </p>
            </Section>

            <Section title="6. Tus derechos (ARCO)">
              <p>Tienes derecho a en cualquier momento:</p>
              <ul className="list-disc list-inside space-y-1 mt-2">
                <li><strong>Acceder</strong> a los datos que tenemos sobre ti.</li>
                <li><strong>Rectificar</strong> los que estén incorrectos o desactualizados (puedes editarlos directamente en tu perfil).</li>
                <li><strong>Cancelar</strong> tu cuenta y solicitar la eliminación de tus datos.</li>
                <li><strong>Oponerte</strong> al tratamiento para fines específicos.</li>
              </ul>
              <p className="mt-3">
                Para ejercer cualquiera de estos derechos, escríbenos a{" "}
                <a href="mailto:privacidad@compa-ra.com" className="text-[#3C5ACB] font-medium hover:underline">
                  privacidad@compa-ra.com
                </a>.
              </p>
            </Section>

            <Section title="7. Seguridad">
              <p>
                Implementamos cifrado en tránsito (HTTPS/TLS) y en reposo para contraseñas (hash con salt).
                Acceso al sistema con autenticación JWT. Sin embargo, ningún sistema en Internet es 100%
                infalible: te recomendamos usar contraseñas únicas y no compartir tu cuenta.
              </p>
            </Section>

            <Section title="8. Menores de edad">
              <p>
                Compa no está dirigido a menores de 13 años. Si descubres que un menor ha creado una cuenta
                sin consentimiento de su representante legal, escríbenos y procederemos a eliminarla.
              </p>
            </Section>

            <Section title="9. Cambios a esta política">
              <p>
                Podemos actualizar esta política. Cualquier cambio significativo será comunicado en la
                aplicación o por email a la dirección registrada en tu cuenta.
              </p>
            </Section>

            <Section title="10. Contacto">
              <p>
                Si tienes preguntas sobre esta política o sobre el tratamiento de tus datos, escríbenos a{" "}
                <a href="mailto:privacidad@compa-ra.com" className="text-[#3C5ACB] font-medium hover:underline">
                  privacidad@compa-ra.com
                </a>.
              </p>
            </Section>

            <p className="text-slate-500 border-t border-slate-100 pt-6">
              <strong className="text-slate-700">Compa</strong> · Democratizando la información de precios en Venezuela.
            </p>
          </div>

          <div className="mt-10 flex gap-4 flex-wrap">
            <Link
              href="/auth?mode=register"
              className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold text-sm px-6 py-3 rounded-full transition-colors"
            >
              Crear cuenta gratis
            </Link>
            <Link
              href="/terminos"
              className="border border-slate-200 text-slate-600 font-bold text-sm px-6 py-3 rounded-full hover:bg-slate-50 transition-colors"
            >
              Ver términos
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-base font-bold text-slate-800 mb-2">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
