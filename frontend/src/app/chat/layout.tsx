import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chat",
  description: "Pregunta sobre precios, compara tiendas y calcula tu carrito óptimo con la IA de Compa.",
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
