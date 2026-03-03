const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface Oferta {
  cadena: string;
  sucursal: string;
  tipo_comercio: string;
  precio_usd: number | null;
  precio_ves: number | null;
  es_promocion: boolean;
  ultima_actualizacion: string | null;
}

export interface Producto {
  id: string;
  nombre: string;
  presentacion: string;
  ofertas: Oferta[];
}

export async function buscarProductos(query: string): Promise<Producto[]> {
  try {
    const res = await fetch(`${API_URL}/catalog/productos/buscar?q=${encodeURIComponent(query)}`);
    if (!res.ok) {
      throw new Error('Error buscando productos');
    }
    const data = await res.json();
    return data.resultados || [];
  } catch (error) {
    console.error(error);
    return [];
  }
}
