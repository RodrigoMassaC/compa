"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getUser, getToken, saveAuth, clearAuth, planLabel, type AuthUser } from "@/lib/auth";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const STATES_VEN = [
  "Amazonas","Anzoátegui","Apure","Aragua","Barinas","Bolívar","Carabobo",
  "Cojedes","Delta Amacuro","Distrito Capital","Falcón","Guárico","Lara",
  "Mérida","Miranda","Monagas","Nueva Esparta","Portuguesa","Sucre","Táchira",
  "Trujillo","Vargas","Yaracuy","Zulia",
];

const planColor: Record<string, string> = {
  FREE:       "bg-slate-100 text-slate-600",
  BASIC:      "bg-blue-100 text-blue-700",
  PRO:        "bg-purple-100 text-purple-700",
  ENTERPRISE: "bg-amber-100 text-amber-700",
};

export default function PerfilPage() {
  const router = useRouter();
  const [user, setUser]       = useState<AuthUser | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Campos editables
  const [nombre, setNombre]     = useState("");
  const [ciudad, setCiudad]     = useState("");
  const [estado, setEstado]     = useState("");
  const [sexo, setSexo]         = useState("");
  const [telefono, setTelefono] = useState("");

  useEffect(() => {
    const u = getUser();
    if (!u) { router.replace("/auth"); return; }
    setUser(u);
    setNombre(u.nombre_completo ?? "");
    setCiudad(u.ciudad ?? "");
    setEstado(u.estado_ven ?? "");
    setSexo(u.sexo ?? "");
    setTelefono(u.telefono_wa ?? "");
  }, [router]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/auth/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` },
        body: JSON.stringify({
          nombre_completo: nombre || undefined,
          ciudad: ciudad || undefined,
          estado_ven: estado || undefined,
          sexo: sexo || undefined,
          telefono_wa: telefono || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Error al guardar"); return; }

      // Actualizar localStorage
      const updated: AuthUser = { ...user, nombre_completo: data.nombre_completo, ciudad: data.ciudad, estado_ven: data.estado_ven, sexo: data.sexo, telefono_wa: data.telefono_wa };
      saveAuth(getToken()!, updated);
      setUser(updated);
      setEditing(false);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch {
      setError("Error de conexión");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (!user) return;
    setNombre(user.nombre_completo ?? "");
    setCiudad(user.ciudad ?? "");
    setEstado(user.estado_ven ?? "");
    setSexo(user.sexo ?? "");
    setTelefono(user.telefono_wa ?? "");
    setEditing(false);
    setError(null);
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-[#fbfcff] font-sans text-slate-800 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-[#ebecf0] px-6 py-4 flex items-center justify-between">
        <Link href="/chat" className="flex items-center gap-2 text-sm font-bold text-[#34a87a]">
          ← Volver al chat
        </Link>
        <span className="font-extrabold text-lg">Compa</span>
        <nav className="flex items-center gap-4 text-sm font-medium text-slate-500">
          <Link href="/" className="hover:text-slate-800">Inicio</Link>
          <Link href="/chat" className="hover:text-slate-800">Chat</Link>
        </nav>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-10 flex flex-col gap-6">

        {/* Notificación éxito */}
        {success && (
          <div className="bg-[#e8f8f1] border border-[#c8eadb] text-[#34a87a] text-sm font-bold px-4 py-3 rounded-xl">
            Perfil actualizado correctamente.
          </div>
        )}

        {/* Avatar + nombre */}
        <div className="bg-white border border-[#ebecf0] rounded-2xl p-6 flex items-center gap-5 shadow-sm">
          <div className="w-16 h-16 rounded-full bg-[#bdf0db] flex items-center justify-center text-2xl font-extrabold text-[#34a87a] flex-shrink-0">
            {user.nombre_completo?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-extrabold text-slate-800 truncate">{user.nombre_completo}</h1>
            <p className="text-sm text-slate-500">{user.email}</p>
            <span className={`inline-block mt-1 text-xs font-bold px-3 py-0.5 rounded-full ${planColor[user.plan] ?? "bg-slate-100 text-slate-600"}`}>
              {planLabel(user.plan)}
            </span>
          </div>
        </div>

        {/* Información personal */}
        <div className="bg-white border border-[#ebecf0] rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Información personal</h2>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="text-xs font-bold text-[#34a87a] hover:underline"
              >
                Editar
              </button>
            )}
          </div>

          {editing ? (
            <div className="flex flex-col gap-4">
              {error && <p className="text-xs text-red-500 font-medium">{error}</p>}

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wide block mb-1">Nombre completo</label>
                  <input
                    type="text"
                    value={nombre}
                    onChange={e => setNombre(e.target.value)}
                    className="w-full border border-[#e5e5e5] rounded-xl px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:border-[#6abf9a]"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wide block mb-1">Ciudad</label>
                  <input
                    type="text"
                    value={ciudad}
                    onChange={e => setCiudad(e.target.value)}
                    placeholder="Ej: Maracay"
                    className="w-full border border-[#e5e5e5] rounded-xl px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:border-[#6abf9a]"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wide block mb-1">Estado</label>
                  <select
                    value={estado}
                    onChange={e => setEstado(e.target.value)}
                    className="w-full border border-[#e5e5e5] rounded-xl px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:border-[#6abf9a] bg-white"
                  >
                    <option value="">— Seleccionar —</option>
                    {STATES_VEN.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wide block mb-1">Sexo</label>
                  <select
                    value={sexo}
                    onChange={e => setSexo(e.target.value)}
                    className="w-full border border-[#e5e5e5] rounded-xl px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:border-[#6abf9a] bg-white"
                  >
                    <option value="">— Seleccionar —</option>
                    <option value="M">Masculino</option>
                    <option value="F">Femenino</option>
                    <option value="OTRO">Otro</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wide block mb-1">WhatsApp</label>
                  <input
                    type="text"
                    value={telefono}
                    onChange={e => setTelefono(e.target.value)}
                    placeholder="584121234567"
                    className="w-full border border-[#e5e5e5] rounded-xl px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:border-[#6abf9a]"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-[#6abf9a] hover:bg-[#5aa987] text-white font-bold text-sm px-5 py-2 rounded-full transition-colors disabled:opacity-50"
                >
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>
                <button
                  onClick={handleCancel}
                  className="text-slate-500 hover:text-slate-700 font-bold text-sm px-5 py-2 rounded-full border border-[#e5e5e5] hover:bg-slate-50 transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
              <Field label="Ciudad"    value={user.ciudad} />
              <Field label="Estado"    value={user.estado_ven} />
              <Field label="Sexo"      value={user.sexo === "M" ? "Masculino" : user.sexo === "F" ? "Femenino" : user.sexo === "OTRO" ? "Otro" : null} />
              <Field label="WhatsApp"  value={user.telefono_wa} />
              <Field label="Rol"       value={user.rol_usuario} />
              <Field label="Suscripción" value={user.estado_suscripcion} />
            </dl>
          )}
        </div>

        {/* Acciones */}
        <div className="bg-white border border-[#ebecf0] rounded-2xl p-6 shadow-sm flex flex-col gap-3">
          <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Cuenta</h2>
          <Link
            href="/chat"
            className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#f0f9f5] border border-[#c8eadb] text-[#34a87a] font-bold text-sm hover:bg-[#e0f4ec] transition-colors"
          >
            <ChatIcon className="w-5 h-5" />
            Ir al chat
          </Link>
          <Link
            href="/"
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-[#ebecf0] text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors"
          >
            <HomeIcon className="w-5 h-5" />
            Página principal
          </Link>
          <button
            onClick={() => { clearAuth(); router.push("/"); }}
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-red-100 text-red-400 font-bold text-sm hover:bg-red-50 transition-colors text-left"
          >
            <LogoutIcon className="w-5 h-5" />
            Cerrar sesión
          </button>
        </div>

      </main>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-bold text-slate-400 uppercase tracking-wide">{label}</dt>
      <dd className="text-sm font-medium text-slate-700 mt-0.5">{value ?? <span className="text-slate-300">—</span>}</dd>
    </div>
  );
}

const ChatIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
);
const HomeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);
const LogoutIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
  </svg>
);
