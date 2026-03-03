"use client";

import { useState } from "react";
import SearchBar from "@/components/SearchBar";
import ProductCard from "@/components/ProductCard";
import { buscarProductos, Producto } from "@/lib/api";

export default function Home() {
  const [productos, setProductos] = useState<Producto[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (query: string) => {
    setIsSearching(true);
    setHasSearched(true);

    try {
      const resultados = await buscarProductos(query);
      setProductos(resultados);
    } catch (error) {
      console.error("Failed to search", error);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-4 md:p-8">
      <div className="max-w-3xl mx-auto pt-10 md:pt-20">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-extrabold text-blue-600 dark:text-blue-500 mb-2 tracking-tight">Compa</h1>
          <p className="text-zinc-600 dark:text-zinc-400 text-lg">Compara precios en Venezuela, fácil y rápido.</p>
        </div>

        <SearchBar onSearch={handleSearch} isSearching={isSearching} />

        <div className="mt-8">
          {isSearching && (
            <div className="flex justify-center items-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          )}

          {!isSearching && hasSearched && productos.length === 0 && (
            <div className="text-center py-16 text-zinc-500">
              <p className="text-lg">No encontramos productos con ese nombre.</p>
              <p className="text-sm mt-2">Intenta con otro término o marca.</p>
            </div>
          )}

          {!isSearching && productos.length > 0 && (
            <div className="space-y-4">
              <p className="text-sm font-medium text-zinc-500 mb-4 px-1">
                Encontramos {productos.length} producto{productos.length !== 1 ? 's' : ''}
              </p>
              {productos.map((producto) => (
                <ProductCard key={producto.id} producto={producto} />
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
