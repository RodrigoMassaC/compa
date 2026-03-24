import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Iniciar sesión",
  description: "Crea tu cuenta gratuita o inicia sesión en Compa para guardar tus listas y acceder a funciones avanzadas.",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
