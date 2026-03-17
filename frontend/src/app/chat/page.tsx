"use client";
import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";

const PiggyBankIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
  </svg>
);

const ChatIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
);

const ClockIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
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

const CheckIcon = ({ className }: { className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
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

interface ChatProduct {
  nombre?: string;
  marca?: string;
  presentacion?: string;
  ofertas?: { precio_usd?: number; precio_ves?: number }[];
  [key: string]: unknown;
}

interface ChatMessage {
  role: "user" | "agent";
  type?: "text" | "results";
  content: string;
  products?: ChatProduct[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const userMsg: ChatMessage = { role: "user", content: inputValue };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsTyping(true);

    // Construir historial para el agente
    const historial = messages.map((m) => ({
      role: m.role === "agent" ? "assistant" : "user",
      content: m.content,
    }));

    try {
      const response = await fetch("http://localhost:8000/api/v1/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: userMsg.content, historial }),
      });
      const data = await response.json();
      setIsTyping(false);

      if (data && data.respuesta) {
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            type: data.tipo === "productos" ? "results" : "text",
            content: data.respuesta,
            products: data.productos || [],
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            type: "text",
            content: "Lo siento, no pude procesar tu consulta en este momento.",
          },
        ]);
      }
    } catch {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          type: "text",
          content: "Hubo un error de conexión con el servidor. Verifica que el backend esté corriendo.",
        },
      ]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSend();
  };

  return (
    <div className="flex h-screen bg-[#fbfcff] font-sans text-slate-800">
      {/* SIDEBAR */}
      <aside className="w-[280px] border-r border-[#ebecf0] bg-white hidden md:flex flex-col justify-between">
        <div className="p-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="bg-[#bdf0db] text-[#34a87a] w-10 h-10 rounded-xl flex items-center justify-center">
              <PiggyBankIcon className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-extrabold text-xl leading-tight">Compa</h1>
              <p className="text-xs text-slate-400 font-medium">Tu Asistente de Ahorro</p>
            </div>
          </Link>

          <button
            className="w-full mt-8 bg-[#6abf9a] hover:bg-[#5aa987] text-white font-bold py-3 px-4 rounded-full flex items-center justify-center gap-2 transition-colors"
            onClick={() => setMessages([])}
          >
            <span className="text-xl leading-none">+</span> Nueva consulta
          </button>

          <div className="mt-8">
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Hoy</h3>
            <ul className="space-y-1">
              <li>
                <button className="w-full flex items-center gap-3 px-3 py-2 bg-[#f0f9f5] border border-[#e0f3eb] text-slate-700 rounded-xl text-sm font-medium">
                  <ChatIcon className="w-4 h-4 text-[#6abf9a]" />
                  Precios de Harina y Arroz
                </button>
              </li>
            </ul>
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-6 mb-3">Ayer</h3>
            <ul className="space-y-1">
              {["Medicinas de la abuela", "Artículos para fiestas", "Compras semanales"].map((item) => (
                <li key={item}>
                  <button className="w-full flex items-center gap-3 px-3 py-2 text-slate-500 hover:bg-slate-50 rounded-xl text-sm font-medium transition-colors">
                    <ClockIcon className="w-4 h-4 text-slate-300" />
                    {item}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="p-4">
          <div className="bg-[#f6f5ff] rounded-2xl p-4 flex items-center justify-between border border-[#efedfb]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#958afa]">
                <UserIcon className="w-6 h-6" />
              </div>
              <div>
                <div className="font-bold text-sm text-slate-800">Usuario Feliz</div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <span className="w-1.5 h-1.5 bg-[#6abf9a] rounded-full"></span> Plan Gratis
                </div>
                <a href="#pro" className="text-xs font-bold text-[#6abf9a] inline-block mt-0.5">
                  Mejorar a Pro ✨
                </a>
              </div>
            </div>
            <button className="text-slate-400 hover:text-slate-600">
              <SettingsIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL */}
      <main className="flex-1 flex flex-col relative h-full overflow-hidden">
        {/* Header */}
        <header className="absolute top-0 w-full p-4 flex justify-between z-10 pointer-events-none">
          <div className="bg-white/80 backdrop-blur-md border border-slate-100 shadow-sm rounded-full px-4 py-2 flex items-center gap-2 text-xs font-bold text-slate-600 pointer-events-auto">
            <PinIcon className="w-4 h-4 text-[#6abf9a]" />
            Maracay, Aragua
          </div>
          <div className="bg-white/80 backdrop-blur-md border border-slate-100 shadow-sm rounded-full px-4 py-2 flex items-center gap-2 text-xs font-bold text-slate-600 pointer-events-auto">
            <RefreshIcon className="w-4 h-4 text-slate-400" />
            Tasa BCV: 36.50 Bs/USD
          </div>
        </header>

        {/* Mensajes */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-32 pt-20 flex flex-col items-center">
          <div className="w-full max-w-3xl flex flex-col gap-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center mt-20 text-slate-400">
                <div className="bg-[#bdf0db] w-16 h-16 rounded-full flex items-center justify-center text-[#34a87a] mb-4">
                  <PiggyBankIcon className="w-8 h-8" />
                </div>
                <p className="font-medium text-lg">¿Qué vamos a comprar hoy?</p>
                <p className="text-sm mt-2">Pregúntame sobre precios en Farmatodo y más tiendas.</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "user" ? (
                  <div className="bg-white border border-[#efefef] shadow-sm text-slate-700 font-medium px-5 py-3.5 rounded-3xl rounded-tr-sm max-w-[85%] text-[15px] leading-relaxed">
                    {msg.content}
                  </div>
                ) : (
                  <div className="flex gap-4 w-full">
                    <div className="w-10 h-10 rounded-full bg-[#8bcab8] flex items-center justify-center text-white flex-shrink-0 mt-1 shadow-sm">
                      <RobotIcon className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      <div className="text-slate-700 text-[15px] leading-relaxed font-medium mb-3">
                        {msg.content}
                      </div>

                      {msg.type === "results" && msg.products && (
                        <div className="bg-white border border-[#f0f0f0] rounded-3xl p-6 shadow-sm mb-3">
                          <div className="flex justify-between items-center mb-5 pb-4 border-b border-slate-50">
                            <div className="flex items-center gap-2 font-bold text-[15px]">
                              <div className="bg-[#6abf9a] text-white w-5 h-5 rounded-full flex items-center justify-center">
                                <CheckIcon className="w-3.5 h-3.5" />
                              </div>
                              Opción A: Todo en un solo lugar
                            </div>
                            <div className="bg-[#7ec9ab] rounded-full text-white text-[10px] font-extrabold px-3 py-1 uppercase tracking-wider">
                              Mejor Valor
                            </div>
                          </div>

                          <div className="space-y-4 mb-6">
                            {msg.products.slice(0, 3).map((prod: ChatProduct, idx: number) => (
                              <div key={idx} className="flex justify-between items-start">
                                <div>
                                  <div className="font-bold text-slate-800 text-[15px]">{prod.nombre}</div>
                                  <div className="text-xs text-slate-400">{prod.marca} · {prod.presentacion}</div>
                                </div>
                                <div className="text-right">
                                  <div className="font-bold text-slate-800">${prod.ofertas?.[0]?.precio_usd?.toFixed(2) || "—"}</div>
                                  <div className="text-[11px] text-slate-400">{prod.ofertas?.[0]?.precio_ves?.toFixed(2)} Bs</div>
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="bg-[#fffdf5] border border-[#fef3d5] rounded-2xl p-4 flex justify-between items-center mb-5">
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Total Estimado</span>
                            <div className="font-extrabold text-xl text-slate-800">
                              ${msg.products.reduce((acc: number, p: ChatProduct) => acc + (p.ofertas?.[0]?.precio_usd || 0), 0).toFixed(2)}
                            </div>
                          </div>

                          <button className="w-full bg-[#6dbf9c] hover:bg-[#5aa987] text-white py-3.5 rounded-full font-bold text-sm flex items-center justify-center gap-2 transition-colors">
                            Ver Detalles y Disponibilidad
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        </div>
                      )}

                      {msg.type === "results" && (
                        <div className="flex flex-wrap gap-2">
                          <button className="bg-white border border-[#eaeaea] shadow-sm rounded-full px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors">
                            Comparar con otras tiendas
                          </button>
                          <button className="bg-white border border-[#eaeaea] shadow-sm rounded-full px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors">
                            Añadir a la lista
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-[#8bcab8] flex items-center justify-center text-white flex-shrink-0">
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

        {/* Input */}
        <div className="absolute bottom-0 w-full bg-gradient-to-t from-[#fbfcff] via-[#fbfcff] to-transparent pt-10 pb-4 px-4 flex flex-col items-center z-10">
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
              className="w-10 h-10 bg-[#6dbf9c] hover:bg-[#5aa987] rounded-full flex items-center justify-center text-white transition-colors disabled:opacity-50"
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
