"use client";
import React, { useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("La contraseña debe tener al menos 8 caracteres"); return; }
    if (password !== confirm) { setError("Las contraseñas no coinciden"); return; }
    if (!token) { setError("Token inválido. Solicita un nuevo enlace."); return; }

    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al restablecer contraseña");
      setSuccess(true);
      setTimeout(() => router.push("/auth"), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="text-center">
        <p className="text-red-500 font-medium mb-4">Enlace inválido o expirado.</p>
        <Link href="/auth" className="text-[#6abf9a] font-bold hover:underline">
          Solicitar nuevo enlace →
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="text-center">
        <div className="w-16 h-16 bg-[#bdf0db] rounded-full flex items-center justify-center mx-auto mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-[#34a87a]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 className="font-bold text-slate-800 text-lg mb-2">¡Contraseña actualizada!</h3>
        <p className="text-slate-500 text-sm">Redirigiendo al inicio de sesión...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1">Nueva contraseña</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mínimo 8 caracteres"
          required
          className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6abf9a] transition-colors"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-600 mb-1">Confirmar contraseña</label>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Repite la contraseña"
          required
          className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6abf9a] transition-colors"
        />
      </div>
      {error && <p className="text-red-500 text-sm font-medium">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-[#6abf9a] hover:bg-[#5aa987] disabled:opacity-60 text-white font-bold py-3 rounded-full transition-colors"
      >
        {loading ? "Actualizando..." : "Restablecer contraseña"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-[#fbfcff] flex items-center justify-center px-4 font-sans">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-sm border border-[#f0f0f0] p-8">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-[#bdf0db] rounded-2xl flex items-center justify-center mx-auto mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-[#34a87a]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-800">Nueva contraseña</h1>
          <p className="text-slate-500 text-sm mt-1">Ingresa tu nueva contraseña para Compa</p>
        </div>
        <Suspense fallback={<div className="text-center text-slate-400 text-sm">Cargando...</div>}>
          <ResetPasswordForm />
        </Suspense>
        <div className="mt-6 text-center">
          <Link href="/auth" className="text-sm text-slate-400 hover:text-slate-600 transition-colors">
            ← Volver al inicio de sesión
          </Link>
        </div>
      </div>
    </div>
  );
}
