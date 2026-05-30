"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface Item {
  id_item: string;
  nombre_item: string;
  cantidad: number;
}

interface Lista {
  id_lista: string;
  nombre: string;
  creado_en: string;
  actualizado_en: string;
  items: Item[];
}

export default function ListasPage() {
  const router = useRouter();
  const [listas, setListas] = useState<Lista[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [creando, setCreando] = useState(false);
  const [activa, setActiva] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/auth?next=/listas");
      return;
    }
    cargar(token);
  }, [router]);

  async function cargar(token: string) {
    setLoading(true);
    try {
      const res = await fetch(`${API}/listas`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("No se pudieron cargar las listas");
      const data: Lista[] = await res.json();
      setListas(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error cargando listas");
    } finally {
      setLoading(false);
    }
  }

  async function crearLista() {
    const token = getToken();
    if (!token || !nuevoNombre.trim()) return;
    setCreando(true);
    try {
      const res = await fetch(`${API}/listas`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ nombre: nuevoNombre.trim() }),
      });
      if (!res.ok) throw new Error("No se pudo crear la lista");
      const nueva: Lista = await res.json();
      setListas([nueva, ...listas]);
      setNuevoNombre("");
      setActiva(nueva.id_lista);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error creando lista");
    } finally {
      setCreando(false);
    }
  }

  async function eliminarLista(id: string) {
    if (!confirm("¿Eliminar esta lista y todos sus ítems?")) return;
    const token = getToken();
    if (!token) return;
    try {
      const res = await fetch(`${API}/listas/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) throw new Error("No se pudo eliminar");
      setListas(listas.filter((l) => l.id_lista !== id));
      if (activa === id) setActiva(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error eliminando lista");
    }
  }

  async function agregarItem(listaId: string, nombre: string, cantidad: number) {
    const token = getToken();
    if (!token || !nombre.trim()) return;
    try {
      const res = await fetch(`${API}/listas/${listaId}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ nombre_item: nombre.trim(), cantidad }),
      });
      if (!res.ok) throw new Error("No se pudo añadir el ítem");
      const nuevoItem: Item = await res.json();
      setListas((prev) =>
        prev.map((l) =>
          l.id_lista === listaId ? { ...l, items: [...l.items, nuevoItem] } : l
        )
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error añadiendo ítem");
    }
  }

  async function eliminarItem(listaId: string, itemId: string) {
    const token = getToken();
    if (!token) return;
    try {
      const res = await fetch(`${API}/listas/${listaId}/items/${itemId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) throw new Error("No se pudo eliminar el ítem");
      setListas((prev) =>
        prev.map((l) =>
          l.id_lista === listaId
            ? { ...l, items: l.items.filter((i) => i.id_item !== itemId) }
            : l
        )
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error eliminando ítem");
    }
  }

  function buscarEnChat(lista: Lista) {
    if (lista.items.length === 0) {
      alert("La lista está vacía. Agrega ítems primero.");
      return;
    }
    const items = lista.items
      .map((i) => (i.cantidad > 1 ? `${i.cantidad} ${i.nombre_item}` : i.nombre_item))
      .join(", ");
    const prompt = `Calcular carrito de: ${items}`;
    sessionStorage.setItem("compa_prompt_inicial", prompt);
    router.push("/chat");
  }

  return (
    <div className="min-h-screen bg-[#F5F7FF] font-sans text-slate-800">
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href="/chat" className="flex items-center gap-2">
          <Image src="/logo-blue.png" alt="Compa" width={36} height={36} className="rounded-xl" />
          <span className="font-extrabold text-xl text-slate-800">Compa</span>
        </Link>
        <div className="flex items-center gap-4 text-sm font-bold">
          <Link href="/chat" className="text-[#3C5ACB] hover:underline">← Volver al chat</Link>
          <Link href="/perfil" className="text-slate-500 hover:text-slate-700">Perfil</Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 mb-1">Mis listas de compras</h1>
          <p className="text-sm text-slate-500">
            Guarda lo que sueles comprar y compara precios en todas las tiendas con un click.
          </p>
        </div>

        {/* Crear lista */}
        <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Nueva lista</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={nuevoNombre}
              onChange={(e) => setNuevoNombre(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && crearLista()}
              placeholder="Ej: Mercado semanal"
              className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#3C5ACB]"
              disabled={creando}
            />
            <button
              onClick={crearLista}
              disabled={creando || !nuevoNombre.trim()}
              className="bg-[#3C5ACB] hover:bg-[#2F47A8] disabled:bg-slate-300 text-white font-bold text-sm px-5 rounded-xl transition-colors"
            >
              {creando ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-700">
            {error}
            <button onClick={() => setError(null)} className="ml-2 font-bold underline">
              Cerrar
            </button>
          </div>
        )}

        {/* Listado */}
        {loading ? (
          <div className="text-center py-16 text-slate-400 text-sm">Cargando…</div>
        ) : listas.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-10 text-center">
            <div className="text-5xl mb-4">📋</div>
            <p className="font-bold text-slate-800 mb-2">Aún no tienes listas</p>
            <p className="text-sm text-slate-500 mb-6">
              Crea tu primera lista arriba para empezar a comparar precios de tus compras habituales.
            </p>
            <Link
              href="/chat"
              className="inline-block text-sm font-bold text-[#3C5ACB] hover:underline"
            >
              O pregúntale al chat directamente →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {listas.map((lista) => (
              <ListaCard
                key={lista.id_lista}
                lista={lista}
                expandida={activa === lista.id_lista}
                onToggle={() => setActiva(activa === lista.id_lista ? null : lista.id_lista)}
                onAgregarItem={(nombre, cantidad) => agregarItem(lista.id_lista, nombre, cantidad)}
                onEliminarItem={(itemId) => eliminarItem(lista.id_lista, itemId)}
                onEliminarLista={() => eliminarLista(lista.id_lista)}
                onBuscar={() => buscarEnChat(lista)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

/* ── Componente Card de lista (con expand/collapse) ─────────────────────────── */

function ListaCard({
  lista,
  expandida,
  onToggle,
  onAgregarItem,
  onEliminarItem,
  onEliminarLista,
  onBuscar,
}: {
  lista: Lista;
  expandida: boolean;
  onToggle: () => void;
  onAgregarItem: (nombre: string, cantidad: number) => void;
  onEliminarItem: (itemId: string) => void;
  onEliminarLista: () => void;
  onBuscar: () => void;
}) {
  const [nuevoItem, setNuevoItem] = useState("");
  const [cantidad, setCantidad] = useState(1);

  const fecha = new Date(lista.actualizado_en).toLocaleDateString("es-VE", {
    day: "numeric",
    month: "short",
  });

  return (
    <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
      {/* Cabecera clickable */}
      <button
        onClick={onToggle}
        className="w-full p-5 flex items-center justify-between hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <p className="font-bold text-slate-800 truncate">{lista.nombre}</p>
          <p className="text-xs text-slate-400">
            {lista.items.length} {lista.items.length === 1 ? "ítem" : "ítems"} · actualizada {fecha}
          </p>
        </div>
        <span className={`text-[#3C5ACB] text-xl transition-transform ${expandida ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>

      {expandida && (
        <div className="border-t border-slate-100 p-5 space-y-4 bg-slate-50/50">
          {/* Items */}
          {lista.items.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">
              Esta lista está vacía. Añade ítems abajo.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {lista.items.map((item) => (
                <li
                  key={item.id_item}
                  className="flex items-center justify-between bg-white rounded-xl px-4 py-2.5 border border-slate-100"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {item.cantidad > 1 && (
                      <span className="bg-[#3C5ACB]/10 text-[#3C5ACB] text-xs font-extrabold rounded-full px-2.5 py-0.5">
                        ×{item.cantidad}
                      </span>
                    )}
                    <span className="text-sm text-slate-700 truncate">{item.nombre_item}</span>
                  </div>
                  <button
                    onClick={() => onEliminarItem(item.id_item)}
                    className="text-slate-300 hover:text-red-500 ml-3 text-lg leading-none"
                    title="Quitar"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Añadir ítem */}
          <div className="flex gap-2">
            <input
              type="text"
              value={nuevoItem}
              onChange={(e) => setNuevoItem(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && nuevoItem.trim()) {
                  onAgregarItem(nuevoItem, cantidad);
                  setNuevoItem("");
                  setCantidad(1);
                }
              }}
              placeholder="Ej: Aceite de maíz 1L"
              className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#3C5ACB] bg-white"
            />
            <input
              type="number"
              min={1}
              value={cantidad}
              onChange={(e) => setCantidad(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-16 border border-slate-200 rounded-xl px-3 py-2 text-sm text-center focus:outline-none focus:border-[#3C5ACB] bg-white"
            />
            <button
              onClick={() => {
                if (nuevoItem.trim()) {
                  onAgregarItem(nuevoItem, cantidad);
                  setNuevoItem("");
                  setCantidad(1);
                }
              }}
              disabled={!nuevoItem.trim()}
              className="bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-bold text-sm px-4 rounded-xl transition-colors"
            >
              + Añadir
            </button>
          </div>

          {/* Acciones */}
          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <button
              onClick={onEliminarLista}
              className="text-xs font-bold text-slate-400 hover:text-red-500 transition-colors"
            >
              Eliminar lista
            </button>
            <button
              onClick={onBuscar}
              className="bg-[#DDDD4A] hover:bg-[#C8C830] text-[#1E2E7A] font-bold text-sm px-5 py-2.5 rounded-full transition-colors"
            >
              Buscar precios en el chat →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
