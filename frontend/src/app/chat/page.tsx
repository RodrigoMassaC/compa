"use client";
import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { getUser, getToken, planLabel, type AuthUser } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Historial en localStorage ──────────────────────────────────────────────
const HISTORY_KEY = "compa_historial";

interface Conversacion {
  id: string;
  titulo: string;
  fecha: string; // ISO
  messages: ChatMessage[];
}

function cargarHistorial(): Conversacion[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function guardarHistorial(lista: Conversacion[]): void {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(lista.slice(0, 30)));
}

function agruparPorFecha(lista: Conversacion[]): { hoy: Conversacion[]; ayer: Conversacion[]; anterior: Conversacion[] } {
  const ahora = new Date();
  const hoy = ahora.toDateString();
  const ayer = new Date(ahora.setDate(ahora.getDate() - 1)).toDateString();
  return {
    hoy:      lista.filter(c => new Date(c.fecha).toDateString() === hoy),
    ayer:     lista.filter(c => new Date(c.fecha).toDateString() === ayer),
    anterior: lista.filter(c => {
      const d = new Date(c.fecha).toDateString();
      return d !== hoy && d !== ayer;
    }),
  };
}

// ── Icons ──────────────────────────────────────────────────────────────────
const ChatIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
);
const PinIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);
const RefreshIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);
const ImageIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);
const MicIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);
const SendIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);
const SettingsIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);
const UserIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
);
const RobotIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);
const TagIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
  </svg>
);

// ── Markdown renderer simple ───────────────────────────────────────────────
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const result: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    // Procesar negritas **texto** dentro de cada línea
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const rendered = parts.map((part, j) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={j} className="font-bold text-slate-800">{part.slice(2, -2)}</strong>;
      }
      return part;
    });

    if (line.trim() === "") {
      result.push(<br key={i} />);
    } else if (line.startsWith("- ")) {
      result.push(
        <li key={i} className="ml-4 list-disc text-slate-600">{rendered.map((p, j) =>
          typeof p === "string" ? p.slice(j === 0 ? 2 : 0) : p
        )}</li>
      );
    } else {
      result.push(<span key={i} className="block">{rendered}</span>);
    }
  });

  return result;
}

// ── Tipos ──────────────────────────────────────────────────────────────────
interface Oferta {
  tienda: string;
  precio_usd?: number;
  precio_ves?: number;
}

interface ChatProduct {
  nombre?: string;
  marca?: string;
  presentacion?: string;
  ofertas?: Oferta[];
}

interface CarritoItem {
  buscado: string;
  nombre: string | null;
  marca?: string;
  presentacion?: string;
  precio_usd?: number;
  precio_ves?: number;
  disponible: boolean;
}

interface CarritoTienda {
  tienda: string;
  total_usd: number;
  total_ves: number;
  items_encontrados: number;
  items: CarritoItem[];
}

interface CarritoResult {
  items_buscados: string[];
  tiendas: CarritoTienda[];
  ahorro_maximo_usd: number | null;
  total_items: number;
}

interface ChatMessage {
  role: "user" | "agent";
  type?: "text" | "results" | "carrito";
  content: string;
  products?: ChatProduct[];
  carrito?: CarritoResult;
}

// ── Componente tarjeta de producto ─────────────────────────────────────────
function ProductCard({ product, isFirst }: { product: ChatProduct; isFirst: boolean }) {
  const [verTiendas, setVerTiendas] = React.useState(false);
  const ofertas = product.ofertas || [];
  const precioMin = ofertas.reduce((min, o) =>
    (o.precio_usd ?? 9999) < (min.precio_usd ?? 9999) ? o : min,
    ofertas[0] || {}
  );
  const otrasTiendas = ofertas.filter((o) => o.tienda !== precioMin.tienda);

  return (
    <div className={`bg-white border rounded-2xl p-4 shadow-sm ${isFirst ? "border-[#3C5ACB]" : "border-[#f0f0f0]"}`}>
      {/* Encabezado del producto */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {isFirst && (
              <span className="bg-[#DDDD4A] text-[#1E2E7A] text-[10px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wide">
                Mejor precio
              </span>
            )}
          </div>
          <div className="font-bold text-slate-800 text-[15px] mt-1">{product.nombre}</div>
          <div className="text-xs text-slate-400 mt-0.5">
            {[product.marca, product.presentacion].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="text-right ml-4">
          <div className="font-extrabold text-slate-800 text-lg">
            ${precioMin.precio_usd?.toFixed(2) ?? "—"}
          </div>
          <div className="text-[11px] text-slate-400">
            {precioMin.precio_ves?.toLocaleString("es-VE", { minimumFractionDigits: 2 }) ?? "—"} Bs
          </div>
          {precioMin.tienda && (
            <div className="text-[10px] text-[#3C5ACB] font-bold mt-0.5">{precioMin.tienda}</div>
          )}
        </div>
      </div>

      {/* Botón para ver otras tiendas */}
      {otrasTiendas.length > 0 && (
        <div className="border-t border-slate-50 pt-2 mt-1">
          <button
            onClick={() => setVerTiendas((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400 hover:text-slate-600 transition-colors w-full"
          >
            <TagIcon className="w-3 h-3" />
            {verTiendas
              ? "Ocultar otras tiendas"
              : `Ver en otras ${otrasTiendas.length} ${otrasTiendas.length === 1 ? "tienda" : "tiendas"}`}
            <span className="ml-auto">{verTiendas ? "▲" : "▼"}</span>
          </button>

          {verTiendas && (
            <div className="mt-2 space-y-1.5">
              {otrasTiendas.map((oferta, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <TagIcon className="w-3 h-3 text-slate-300" />
                    <span className="text-xs text-slate-600 font-medium">{oferta.tienda}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-bold text-slate-600">
                      ${oferta.precio_usd?.toFixed(2) ?? "—"}
                    </span>
                    <span className="text-[10px] text-slate-400 ml-1">
                      ({oferta.precio_ves?.toLocaleString("es-VE", { minimumFractionDigits: 0 }) ?? "—"} Bs)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Componente tarjeta de tienda (Carrito Óptimo) ──────────────────────────
function CartOptimalCard({
  tienda,
  isFirst,
  totalItems,
  ahorroMaximo,
}: {
  tienda: CarritoTienda;
  isFirst: boolean;
  totalItems: number;
  ahorroMaximo: number | null;
}) {
  const incompleto = tienda.items_encontrados < totalItems;

  return (
    <div className={`bg-white border rounded-2xl p-4 shadow-sm ${isFirst && !incompleto ? "border-[#3C5ACB]" : "border-[#f0f0f0]"}`}>
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {isFirst && !incompleto && (
              <span className="bg-[#DDDD4A] text-[#1E2E7A] text-[10px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wide">
                Mejor precio
              </span>
            )}
            {incompleto && (
              <span className="bg-[#fff8e1] text-[#e6a817] text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
                Lista incompleta
              </span>
            )}
          </div>
          <div className="font-bold text-slate-800 text-[15px] mt-1">{tienda.tienda}</div>
          <div className="text-xs text-slate-400 mt-0.5">
            {tienda.items_encontrados}/{totalItems} productos disponibles
          </div>
        </div>
        <div className="text-right ml-4">
          <div className="font-extrabold text-slate-800 text-lg">
            ${tienda.total_usd.toFixed(2)}
          </div>
          <div className="text-[11px] text-slate-400">
            {tienda.total_ves.toLocaleString("es-VE", { minimumFractionDigits: 2 })} Bs
          </div>
          {isFirst && !incompleto && ahorroMaximo && ahorroMaximo > 0 && (
            <div className="text-[10px] text-[#3C5ACB] font-bold mt-0.5">
              Ahorra ${ahorroMaximo.toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* Desglose de items */}
      <div className="border-t border-slate-50 pt-3 space-y-2">
        {tienda.items.map((item, idx) => (
          <div key={idx} className="flex justify-between items-start gap-2">
            <div className="flex items-start gap-2 flex-1 min-w-0">
              <span className={`text-xs mt-0.5 font-bold flex-shrink-0 ${item.disponible ? "text-[#3C5ACB]" : "text-slate-300"}`}>
                {item.disponible ? "✓" : "✗"}
              </span>
              <div className="min-w-0">
                <div className={`text-xs font-bold capitalize ${item.disponible ? "text-slate-700" : "text-slate-400"}`}>
                  {item.buscado}
                </div>
                {item.disponible && item.nombre && (
                  <div className="text-[10px] text-slate-400 truncate">{item.nombre}</div>
                )}
                {!item.disponible && (
                  <div className="text-[10px] text-slate-400">No disponible</div>
                )}
              </div>
            </div>
            {item.disponible && item.precio_usd !== undefined && (
              <div className="text-right flex-shrink-0">
                <span className="text-xs font-bold text-slate-700">${item.precio_usd.toFixed(2)}</span>
                {item.precio_ves !== undefined && (
                  <div className="text-[10px] text-slate-400">
                    {item.precio_ves.toLocaleString("es-VE", { minimumFractionDigits: 0 })} Bs
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


// ── Página principal ───────────────────────────────────────────────────────
export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [tasaBCV, setTasaBCV] = useState<string>("...");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [historial, setHistorial] = useState<Conversacion[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [listaCompras, setListaCompras] = useState<string[]>([]);
  const [showLimitModal, setShowLimitModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const addToLista = (nombre: string) => {
    const clave = nombre.toLowerCase().trim();
    setListaCompras((prev) => prev.includes(clave) ? prev : [...prev, clave]);
  };

  const handleCalcCarrito = () => {
    const query = `Carrito: ${listaCompras.join(", ")}`;
    setInputValue(query);
    setListaCompras([]);
  };

  // Cargar usuario e historial desde localStorage al montar
  useEffect(() => {
    setCurrentUser(getUser());
    setHistorial(cargarHistorial());
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    fetch(`${API}/catalog/tasa`)
      .then((r) => r.json())
      .then((d) => {
        if (d?.tasa_usd) setTasaBCV(Number(d.tasa_usd).toLocaleString("es-VE", { minimumFractionDigits: 2 }));
      })
      .catch(() => setTasaBCV("N/D"));
  }, []);

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const userMsg: ChatMessage = { role: "user", content: inputValue };
    const esNuevaConv = messages.length === 0;
    const nuevoConvId = esNuevaConv ? crypto.randomUUID() : convId;

    // Si es la primera pregunta de la conversación → crear entrada en historial
    if (esNuevaConv && nuevoConvId) {
      const nueva: Conversacion = {
        id: nuevoConvId,
        titulo: inputValue.slice(0, 40),
        fecha: new Date().toISOString(),
        messages: [userMsg],
      };
      const actualizado = [nueva, ...historial];
      setHistorial(actualizado);
      guardarHistorial(actualizado);
      setConvId(nuevoConvId);
    }

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsTyping(true);

    const historialAPI = messages.map((m) => ({
      role: m.role === "agent" ? "assistant" : "user",
      content: m.content,
    }));

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const token = getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(`${API}/agent/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ mensaje: userMsg.content, historial: historialAPI }),
      });
      setIsTyping(false);

      if (response.status === 429) {
        setShowLimitModal(true);
        return;
      }

      const data = await response.json();

      if (data?.respuesta) {
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            type: data.tipo === "productos" ? "results" : data.tipo === "carrito" ? "carrito" : "text",
            content: data.respuesta,
            products: data.productos || [],
            carrito: data.carrito || undefined,
          },
        ]);
      } else {
        setMessages((prev) => [...prev, {
          role: "agent", type: "text",
          content: "Lo siento, no pude procesar tu consulta en este momento.",
        }]);
      }
    } catch {
      setIsTyping(false);
      setMessages((prev) => [...prev, {
        role: "agent", type: "text",
        content: "Hubo un error de conexión con el servidor. Verifica que el backend esté corriendo.",
      }]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSend();
  };

  return (
    <div className="flex h-screen bg-[#F5F7FF] font-sans text-slate-800">

      {/* Modal límite mensual */}
      {showLimitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full mx-4 text-center">
            <div className="text-5xl mb-4">⚡</div>
            <h2 className="text-xl font-extrabold text-slate-900 mb-2">Límite mensual alcanzado</h2>
            <p className="text-sm text-slate-500 mb-6">
              Agotaste tus consultas de este mes. Puedes esperar al próximo mes o agregar más consultas a tu cuenta.
            </p>
            <div className="flex flex-col gap-3">
              <Link
                href="/consultas"
                className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold py-3 px-6 rounded-full transition-colors"
                onClick={() => setShowLimitModal(false)}
              >
                Ver opciones de consultas
              </Link>
              <button
                onClick={() => setShowLimitModal(false)}
                className="text-slate-500 hover:text-slate-700 font-medium text-sm py-2"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SIDEBAR */}
      <aside className="w-[280px] border-r border-[#ebecf0] bg-white hidden md:flex flex-col justify-between">
        <div className="p-6">
          <Link href="/" className="flex items-center gap-3">
            <Image src="/logo-blue.png" alt="Compa" width={44} height={44} className="rounded-xl" />
            <div>
              <h1 className="font-extrabold text-xl leading-tight tracking-tight">Compa</h1>
              <p className="text-xs text-slate-400 font-medium">Tu Asistente de Ahorro</p>
            </div>
          </Link>

          <button
            className="w-full mt-8 bg-[#3C5ACB] hover:bg-[#2F47A8] text-white font-bold py-3 px-4 rounded-full flex items-center justify-center gap-2 transition-colors"
            onClick={() => { setMessages([]); setConvId(null); }}
          >
            <span className="text-xl leading-none">+</span> Nueva consulta
          </button>

          <div className="mt-8 overflow-y-auto max-h-[340px]">
            {(() => {
              const { hoy, ayer, anterior } = agruparPorFecha(historial);
              const GrupoHistorial = ({ titulo, items }: { titulo: string; items: Conversacion[] }) =>
                items.length === 0 ? null : (
                  <>
                    <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 mt-5 first:mt-0">{titulo}</h3>
                    <ul className="space-y-1">
                      {items.map((conv) => (
                        <li key={conv.id}>
                          <button
                            onClick={() => { setMessages(conv.messages); setConvId(conv.id); }}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors text-left truncate ${
                              conv.id === convId
                                ? "bg-[#EEF1FD] border border-[#DDE4FA] text-slate-700"
                                : "text-slate-500 hover:bg-slate-50"
                            }`}
                          >
                            <ChatIcon className={`w-4 h-4 flex-shrink-0 ${conv.id === convId ? "text-[#3C5ACB]" : "text-slate-300"}`} />
                            <span className="truncate">{conv.titulo}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                );
              return historial.length === 0 ? (
                <p className="text-xs text-slate-400 text-center mt-8">Tus consultas aparecerán aquí</p>
              ) : (
                <>
                  <GrupoHistorial titulo="Hoy" items={hoy} />
                  <GrupoHistorial titulo="Ayer" items={ayer} />
                  <GrupoHistorial titulo="Anterior" items={anterior} />
                </>
              );
            })()}
          </div>
        </div>

        <div className="p-4">
          <div className="bg-[#EEF1FD] rounded-2xl p-4 flex items-center justify-between border border-[#DDE4FA]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#3C5ACB]">
                <UserIcon className="w-6 h-6" />
              </div>
              <div>
                <div className="font-bold text-sm text-slate-800">
                  {currentUser?.nombre_completo ?? "Invitado"}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <span className="w-1.5 h-1.5 bg-[#3C5ACB] rounded-full"></span>
                  {currentUser ? planLabel(currentUser.plan) : "Sin cuenta"}
                </div>
                {currentUser ? (
                  <a href="#pro" className="text-xs font-bold text-[#3C5ACB] inline-block mt-0.5">
                    Mejorar a Pro ✨
                  </a>
                ) : (
                  <Link href="/auth" className="text-xs font-bold text-[#3C5ACB] inline-block mt-0.5">
                    Iniciar sesión →
                  </Link>
                )}
              </div>
            </div>
            {currentUser ? (
              <Link href="/perfil" title="Ver perfil">
                <SettingsIcon className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </Link>
            ) : (
              <Link href="/auth?mode=register">
                <SettingsIcon className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </Link>
            )}
          </div>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL */}
      <main className="flex-1 flex flex-col relative h-full overflow-hidden">

        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-[#ebecf0] z-20 flex-shrink-0">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo-blue.png" alt="Compa" width={32} height={32} className="rounded-lg" />
            <span className="font-extrabold text-base tracking-tight">Compa</span>
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setMessages([]); setConvId(null); }}
              className="text-xs font-bold text-[#3C5ACB] bg-[#EEF1FD] border border-[#BCC8F5] px-3 py-1.5 rounded-full"
            >
              + Nueva
            </button>
            <Link href={currentUser ? "/perfil" : "/auth"}>
              <UserIcon className="w-6 h-6 text-slate-400" />
            </Link>
          </div>
        </div>

        {/* Header (desktop gradient) */}
        <header className="absolute top-0 w-full pt-4 px-4 pb-10 hidden md:flex justify-between z-10 pointer-events-none bg-gradient-to-b from-[#F5F7FF] via-[#F5F7FF] to-transparent">
          <div className="bg-white/80 backdrop-blur-md border border-slate-100 shadow-sm rounded-full px-4 py-2 flex items-center gap-2 text-xs font-bold text-slate-600 pointer-events-auto">
            <PinIcon className="w-4 h-4 text-[#3C5ACB]" />
            Maracay, Aragua
          </div>
          <div className="bg-white/80 backdrop-blur-md border border-slate-100 shadow-sm rounded-full px-4 py-2 flex items-center gap-2 text-xs font-bold text-slate-600 pointer-events-auto">
            <RefreshIcon className="w-4 h-4 text-slate-400" />
            Tasa BCV: {tasaBCV} Bs/$
          </div>
        </header>

        {/* Mensajes */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-32 pt-4 md:pt-24 flex flex-col items-center">
          <div className="w-full max-w-3xl flex flex-col gap-6">

            {/* Estado vacío */}
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center mt-20 text-slate-400">
                <div className="mb-4">
                  <Image src="/logo-blue.png" alt="Compa" width={64} height={64} className="rounded-2xl" />
                </div>
                <p className="font-medium text-lg">¿Qué vamos a comprar hoy?</p>
                <p className="text-sm mt-2">Pregúntame sobre precios en supermercados y farmacias.</p>
                <div className="flex flex-wrap gap-2 mt-6 justify-center">
                  {["¿Dónde consigo leche más barata?", "Precio del arroz", "Carrito: leche, arroz, aceite, jabón", "Medicamentos para la gripe"].map((s) => (
                    <button
                      key={s}
                      onClick={() => setInputValue(s)}
                      className="bg-white border border-[#e5e5e5] shadow-sm rounded-full px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Mensajes */}
            {messages.map((msg, i) => (
              <div key={i} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "user" ? (
                  <div className="bg-white border border-[#efefef] shadow-sm text-slate-700 font-medium px-5 py-3.5 rounded-3xl rounded-tr-sm max-w-[85%] text-[15px] leading-relaxed">
                    {msg.content}
                  </div>
                ) : (
                  <div className="flex gap-4 w-full">
                    <div className="w-10 h-10 rounded-full bg-[#6B7FD7] flex items-center justify-center text-white flex-shrink-0 mt-1 shadow-sm">
                      <RobotIcon className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      {/* Texto con markdown renderizado */}
                      <div className="text-slate-700 text-[15px] leading-relaxed font-medium mb-3">
                        {renderMarkdown(msg.content)}
                      </div>

                      {/* Tarjetas de productos — una por producto */}
                      {msg.type === "results" && msg.products && msg.products.length > 0 && (
                        <div className="space-y-3 mb-3">
                          {msg.products.map((prod, idx) => (
                            <ProductCard key={idx} product={prod} isFirst={idx === 0} />
                          ))}
                        </div>
                      )}

                      {/* Tarjetas de carrito óptimo */}
                      {msg.type === "carrito" && msg.carrito && msg.carrito.tiendas.length > 0 && (
                        <div className="space-y-3 mb-3">
                          {msg.carrito.tiendas.map((t, idx) => (
                            <CartOptimalCard
                              key={idx}
                              tienda={t}
                              isFirst={idx === 0}
                              totalItems={msg.carrito!.total_items}
                              ahorroMaximo={msg.carrito!.ahorro_maximo_usd}
                            />
                          ))}
                        </div>
                      )}

                      {/* Acciones */}
                      {msg.type === "results" && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          <button
                            onClick={() => setInputValue("hay otra marca?")}
                            className="bg-white border border-[#eaeaea] shadow-sm rounded-full px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors"
                          >
                            Ver otra marca
                          </button>
                          {msg.products && msg.products[0]?.nombre && (
                            <button
                              onClick={() => addToLista(msg.products![0].nombre!)}
                              className="bg-[#EEF1FD] border border-[#BCC8F5] shadow-sm rounded-full px-4 py-2 text-xs font-bold text-[#3C5ACB] hover:bg-[#e0f4ec] transition-colors"
                            >
                              + Añadir a la lista
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {isTyping && (
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-[#6B7FD7] flex items-center justify-center text-white flex-shrink-0">
                  <RobotIcon className="w-6 h-6" />
                </div>
                <div className="flex gap-1 items-center mt-3">
                  <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce"></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Widget flotante de lista de compras */}
        {listaCompras.length > 0 && (
          <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 bg-white border border-[#BCC8F5] shadow-lg rounded-2xl px-4 py-3 flex items-center gap-3 max-w-sm w-auto">
            <span className="text-lg">🛒</span>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-slate-700">
                {listaCompras.length} {listaCompras.length === 1 ? "producto" : "productos"} en lista
              </div>
              <div className="text-[10px] text-slate-400 truncate">
                {listaCompras.join(", ")}
              </div>
            </div>
            <button
              onClick={handleCalcCarrito}
              className="bg-[#3C5ACB] hover:bg-[#2F47A8] text-white text-xs font-bold px-3 py-1.5 rounded-full transition-colors whitespace-nowrap"
            >
              Calcular carrito
            </button>
            <button
              onClick={() => setListaCompras([])}
              className="text-slate-300 hover:text-slate-500 text-sm font-bold"
              title="Limpiar lista"
            >
              ✕
            </button>
          </div>
        )}

        {/* Input */}
        <div className="absolute bottom-0 w-full bg-gradient-to-t from-[#F5F7FF] via-[#F5F7FF] to-transparent pt-10 pb-4 px-4 flex flex-col items-center z-10">
          <div className="w-full max-w-3xl flex items-center bg-white border border-[#e5e5e5] shadow-sm rounded-full p-2 gap-3 focus-within:border-slate-300 transition-all">
            <button className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-50 ml-1">
              <ImageIcon className="w-5 h-5" />
            </button>
            <input
              type="text"
              className="flex-1 bg-transparent border-none outline-none text-[15px] font-medium placeholder:text-slate-400 text-slate-700"
              placeholder="Pregunta sobre precios, productos o disponibilidad..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isTyping}
            />
            <button className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-50">
              <MicIcon className="w-5 h-5" />
            </button>
            <button
              className="w-10 h-10 bg-[#3C5ACB] hover:bg-[#2F47A8] rounded-full flex items-center justify-center text-white transition-colors disabled:opacity-50"
              onClick={handleSend}
              disabled={isTyping || !inputValue.trim()}
            >
              <SendIcon className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[10px] text-slate-400 font-medium mt-3">
            La IA puede cometer errores. Verifica información importante.
          </p>
        </div>
      </main>
    </div>
  );
}
