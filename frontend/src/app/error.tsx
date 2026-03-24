"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[#fbfcff] flex flex-col items-center justify-center font-sans text-slate-800 px-4">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-slate-800 mb-3">Algo salió mal</h2>
        <p className="text-slate-500 mb-8">
          Ocurrió un error inesperado. Puedes intentar de nuevo o volver al inicio.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={reset}
            className="bg-[#6abf9a] hover:bg-[#5aa987] text-white font-bold py-3 px-6 rounded-full transition-colors"
          >
            Intentar de nuevo
          </button>
          <Link
            href="/"
            className="bg-white border border-[#e5e5e5] text-slate-600 font-bold py-3 px-6 rounded-full hover:bg-slate-50 transition-colors"
          >
            Volver al inicio
          </Link>
        </div>
      </div>
    </div>
  );
}
