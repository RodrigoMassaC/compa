"use client";
import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { saveAuth, type AuthUser } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Estados venezolanos ───────────────────────────────────────────────────────
const ESTADOS_VEN = [
  "Amazonas","Anzoátegui","Apure","Aragua","Barinas","Bolívar","Carabobo",
  "Cojedes","Delta Amacuro","Distrito Capital","Falcón","Guárico","Lara",
  "Mérida","Miranda","Monagas","Nueva Esparta","Portuguesa","Sucre","Táchira",
  "Trujillo","Vargas","Yaracuy","Zulia",
];

// ── Componente interno que usa useSearchParams ────────────────────────────────
function AuthForm() {
  const router        = useRouter();
  const searchParams  = useSearchParams();
  const [tab, setTab] = useState<"login" | "register">(
    searchParams.get("mode") === "register" ? "register" : "login"
  );

  // Formulario compartido
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");

  // Solo registro
  const [nombre,         setNombre]         = useState("");
  const [ciudad,         setCiudad]         = useState("");
  const [estadoVen,      setEstadoVen]      = useState("");
  const [sexo,           setSexo]           = useState("");
  const [fechaNac,       setFechaNac]       = useState("");
  const [telefonoWa,     setTelefonoWa]     = useState("");
  const [showOptional,   setShowOptional]   = useState(false);

  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // Limpiar error al cambiar de tab
  useEffect(() => { setError(null); }, [tab]);

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const endpoint = tab === "login" ? "/auth/login" : "/auth/register";
      const body =
        tab === "login"
          ? { email, password }
          : {
              email,
              password,
              nombre_completo: nombre,
              ciudad:          ciudad   || undefined,
              estado_ven:      estadoVen || undefined,
              sexo:            sexo     || undefined,
              fecha_nacimiento: fechaNac || undefined,
              telefono_wa:     telefonoWa ? telefonoWa.replace(/^0/, "58") : undefined,
            };

      const res = await fetch(`${API}${endpoint}`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Error al procesar la solicitud");
        return;
      }

      // Guardar token + user y redirigir al chat
      saveAuth(data.access_token, data.user as AuthUser);
      router.push("/chat");

    } catch {
      setError("No se pudo conectar con el servidor");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F5F7FF] flex flex-col items-center justify-center px-4">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-3 mb-8">
        <Image src="/logo-blue.png" alt="Compa" width={48} height={48} className="rounded-2xl" />
        <div>
          <h1 className="font-extrabold text-2xl leading-tight text-slate-800 tracking-tight">Compa</h1>
          <p className="text-xs text-slate-400 font-medium">Tu Asistente de Ahorro</p>
        </div>
      </Link>

      {/* Card */}
      <div className="bg-white rounded-3xl shadow-sm border border-[#eaecf0] w-full max-w-md p-8">
        {/* Tabs */}
        <div className="flex bg-[#f4f5f7] rounded-full p-1 mb-8">
          {(["login", "register"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 rounded-full text-sm font-bold transition-all ${
                tab === t
                  ? "bg-white shadow-sm text-slate-800"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {t === "login" ? "Iniciar sesión" : "Crear cuenta"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Nombre (solo registro) */}
          {tab === "register" && (
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">
                Nombre completo <span className="text-[#3C5ACB]">*</span>
              </label>
              <input
                type="text"
                required
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej: María González"
                className="w-full border border-[#e5e7eb] rounded-xl px-4 py-3 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors placeholder:text-slate-400"
              />
            </div>
          )}

          {/* Email */}
          <div>
            <label className="block text-xs font-bold text-slate-600 mb-1.5">
              Correo electrónico <span className="text-[#3C5ACB]">*</span>
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tucorreo@email.com"
              className="w-full border border-[#e5e7eb] rounded-xl px-4 py-3 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors placeholder:text-slate-400"
            />
          </div>

          {/* Contraseña */}
          <div>
            <label className="block text-xs font-bold text-slate-600 mb-1.5">
              Contraseña <span className="text-[#3C5ACB]">*</span>
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === "register" ? "Mínimo 8 caracteres" : "Tu contraseña"}
              className="w-full border border-[#e5e7eb] rounded-xl px-4 py-3 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors placeholder:text-slate-400"
            />
          </div>

          {/* WhatsApp obligatorio (solo registro) */}
          {tab === "register" && (
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5">
                Número de WhatsApp <span className="text-[#3C5ACB]">*</span>
              </label>
              <input
                type="tel"
                required
                value={telefonoWa}
                onChange={(e) => setTelefonoWa(e.target.value)}
                placeholder="Ej: 04121234567"
                className="w-full border border-[#e5e7eb] rounded-xl px-4 py-3 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors placeholder:text-slate-400"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                Necesario para usar Compa por WhatsApp y recuperar tu cuenta
              </p>
            </div>
          )}

          {/* Campos opcionales (solo registro) */}
          {tab === "register" && (
            <div>
              <button
                type="button"
                onClick={() => setShowOptional(!showOptional)}
                className="text-xs font-bold text-[#3C5ACB] hover:text-[#3C5ACB] flex items-center gap-1 mt-1"
              >
                {showOptional ? "▲" : "▼"} Datos adicionales (opcional)
              </button>

              {showOptional && (
                <div className="mt-4 space-y-4 border-t border-[#f0f0f0] pt-4">
                  {/* Ciudad + Estado */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1.5">Ciudad</label>
                      <input
                        type="text"
                        value={ciudad}
                        onChange={(e) => setCiudad(e.target.value)}
                        placeholder="Ej: Maracay"
                        className="w-full border border-[#e5e7eb] rounded-xl px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors placeholder:text-slate-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1.5">Estado</label>
                      <select
                        value={estadoVen}
                        onChange={(e) => setEstadoVen(e.target.value)}
                        className="w-full border border-[#e5e7eb] rounded-xl px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors bg-white"
                      >
                        <option value="">Seleccionar</option>
                        {ESTADOS_VEN.map((est) => (
                          <option key={est} value={est}>{est}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Sexo + Fecha de nacimiento */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1.5">Sexo</label>
                      <select
                        value={sexo}
                        onChange={(e) => setSexo(e.target.value)}
                        className="w-full border border-[#e5e7eb] rounded-xl px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors bg-white"
                      >
                        <option value="">Seleccionar</option>
                        <option value="M">Masculino</option>
                        <option value="F">Femenino</option>
                        <option value="OTRO">Prefiero no decir</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1.5">Fecha de nacimiento</label>
                      <input
                        type="date"
                        value={fechaNac}
                        max={new Date().toISOString().split("T")[0]}
                        onChange={(e) => setFechaNac(e.target.value)}
                        className="w-full border border-[#e5e7eb] rounded-xl px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-[#3C5ACB] transition-colors"
                      />
                    </div>
                  </div>

                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-100 text-red-600 text-xs font-medium px-4 py-3 rounded-xl">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:opacity-60 text-white font-bold py-3.5 rounded-full transition-colors text-sm mt-2"
          >
            {loading
              ? "Procesando..."
              : tab === "login"
              ? "Iniciar sesión"
              : "Crear cuenta gratis"}
          </button>
        </form>

        {/* Footer del card */}
        <p className="text-center text-xs text-slate-400 mt-6">
          {tab === "login" ? (
            <>¿No tienes cuenta?{" "}
              <button onClick={() => setTab("register")} className="text-[#3C5ACB] font-bold hover:underline">
                Regístrate gratis
              </button>
            </>
          ) : (
            <>¿Ya tienes cuenta?{" "}
              <button onClick={() => setTab("login")} className="text-[#3C5ACB] font-bold hover:underline">
                Inicia sesión
              </button>
            </>
          )}
        </p>
      </div>

      {/* Link volver */}
      <Link href="/" className="mt-6 text-xs text-slate-400 hover:text-slate-600 font-medium">
        ← Volver al inicio
      </Link>
    </div>
  );
}

// ── Página con Suspense (requerido por useSearchParams en Next.js 14) ─────────
export default function AuthPage() {
  return (
    <Suspense>
      <AuthForm />
    </Suspense>
  );
}
