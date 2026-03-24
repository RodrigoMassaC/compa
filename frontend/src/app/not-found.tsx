import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#fbfcff] flex flex-col items-center justify-center font-sans text-slate-800 px-4">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 bg-[#bdf0db] rounded-full flex items-center justify-center mx-auto mb-6">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-[#34a87a]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h1 className="text-6xl font-extrabold text-slate-200 mb-2">404</h1>
        <h2 className="text-2xl font-bold text-slate-800 mb-3">Página no encontrada</h2>
        <p className="text-slate-500 mb-8">
          Esta página no existe. Quizás el producto que buscas sí está disponible en Compa.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/chat"
            className="bg-[#6abf9a] hover:bg-[#5aa987] text-white font-bold py-3 px-6 rounded-full transition-colors"
          >
            Buscar precios →
          </Link>
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
