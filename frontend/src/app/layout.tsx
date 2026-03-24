import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Compa — Compara precios en Venezuela", template: "%s | Compa" },
  description: "Encuentra siempre el precio más bajo en supermercados y farmacias de Venezuela. Compara precios en tiempo real con tasa BCV.",
  keywords: ["precios Venezuela", "supermercados Venezuela", "comparar precios", "BCV", "ahorro"],
  openGraph: {
    siteName: "Compa",
    locale: "es_VE",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body
        className={`${montserrat.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
