import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mi perfil",
  description: "Gestiona tu cuenta y datos personales en Compa.",
};

export default function PerfilLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
