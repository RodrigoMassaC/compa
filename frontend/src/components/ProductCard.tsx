import { Producto } from '@/lib/api';

export default function ProductCard({ producto }: { producto: Producto }) {
    const ofertasOrdenadas = [...producto.ofertas].sort((a, b) => {
        if (a.precio_usd === null) return 1;
        if (b.precio_usd === null) return -1;
        return a.precio_usd - b.precio_usd;
    });

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-4 mb-4 transition-all hover:shadow-md">
            <div className="flex justify-between items-start mb-3">
                <div>
                    <h3 className="font-bold text-lg text-zinc-900 dark:text-zinc-100">{producto.nombre}</h3>
                    <p className="text-zinc-500 text-sm">{producto.presentacion}</p>
                </div>
            </div>

            <div className="space-y-2 mt-4">
                {ofertasOrdenadas.map((oferta, idx) => (
                    <div key={idx} className={`flex justify-between items-center p-3 rounded-lg ${idx === 0 ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800/30' : 'bg-zinc-50 dark:bg-zinc-800/50'}`}>
                        <div className="flex flex-col">
                            <span className="font-semibold text-sm">{oferta.cadena}</span>
                            <span className="text-xs text-zinc-500">{oferta.sucursal}</span>
                        </div>
                        <div className="text-right flex flex-col items-end">
                            {oferta.precio_ves && (
                                <span className={`font-bold ${idx === 0 ? 'text-emerald-600 dark:text-emerald-400' : ''}`}>
                                    Bs {oferta.precio_ves.toFixed(2)}
                                </span>
                            )}
                            {oferta.precio_usd && (
                                <span className="text-xs text-zinc-500">
                                    Ref ${oferta.precio_usd.toFixed(2)}
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
