"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import {
    LayoutDashboard,
    TrendingUp,
    Users,
    Download,
    FileText,
    LogOut,
    Search,
    Bell,
    User,
    Filter,
} from "lucide-react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";

// --- Mock Data ---

const mockChartData = [
    { date: "01/03", usd: 1.5, ves: 54.2 },
    { date: "05/03", usd: 1.52, ves: 54.9 },
    { date: "10/03", usd: 1.48, ves: 55.1 },
    { date: "15/03", usd: 1.55, ves: 56.0 },
    { date: "20/03", usd: 1.5, ves: 56.5 },
    { date: "25/03", usd: 1.49, ves: 56.8 },
    { date: "30/03", usd: 1.5, ves: 57.0 },
];
// --- Types ---
interface Oferta {
    cadena?: string;
    precio_usd?: number;
    precio_ves?: number;
}

interface Product {
    nombre?: string;
    marca?: string;
    tienda?: string;
    precio_usd?: number;
    precio_ves?: number;
    fecha?: string;
    imagen?: string;
    ofertas?: Oferta[];
    [key: string]: unknown;
}

export default function Dashboard() {
    const [searchQuery, setSearchQuery] = useState("");
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);

    // Fetch real data from backend
    useEffect(() => {
        const fetchProducts = async () => {
            try {
                setLoading(true);
                // Using "a" as the default search query based on requirements
                const res = await fetch(
                    "http://localhost:8000/api/v1/catalog/productos/buscar?q=ac"
                );
                if (res.ok) {
                    const data = await res.json();
                    setProducts(data.resultados || []);
                } else {
                    console.error("Failed to fetch products");
                }
            } catch (error) {
                console.error("Error fetching products:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchProducts();
    }, []);

    return (
        <div className="flex h-screen bg-gray-50 text-gray-900 font-sans">
            {/* Sidebar */}
            <aside className="w-64 bg-white border-r border-gray-200 flex flex-col justify-between hidden md:flex shrink-0">
                <div>
                    <div className="h-16 flex items-center px-6 border-b border-gray-200">
                        <span className="text-xl font-bold text-blue-600 mr-2">Compa</span>
                        <span className="text-sm text-gray-500 font-medium">
                            Market Intelligence
                        </span>
                    </div>
                    <nav className="p-4 space-y-1">
                        <a
                            href="#"
                            className="flex items-center px-3 py-2 text-sm font-medium bg-blue-50 text-blue-700 rounded-lg"
                        >
                            <LayoutDashboard className="w-5 h-5 mr-3" />
                            Resumen
                        </a>
                        <a
                            href="#"
                            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <TrendingUp className="w-5 h-5 mr-3 text-gray-400" />
                            Tendencias
                        </a>
                        <a
                            href="#"
                            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <Users className="w-5 h-5 mr-3 text-gray-400" />
                            Competencia
                        </a>
                        <a
                            href="#"
                            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <Download className="w-5 h-5 mr-3 text-gray-400" />
                            Exportar
                        </a>
                        <a
                            href="#"
                            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <FileText className="w-5 h-5 mr-3 text-gray-400" />
                            Facturación
                        </a>
                    </nav>
                </div>
                <div className="p-4 border-t border-gray-200">
                    <button className="flex items-center w-full px-3 py-2 text-sm font-medium text-gray-700 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors">
                        <LogOut className="w-5 h-5 mr-3 text-gray-400 group-hover:text-red-600" />
                        Cerrar sesión
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <header className="h-16 bg-white border-b border-gray-200 flex flex-col justify-center px-8 shrink-0 relative z-10 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-xl font-bold text-gray-900 leading-tight">
                                Resumen Analítico
                            </h1>
                            <p className="text-sm text-gray-500">Bienvenido de nuevo</p>
                        </div>

                        <div className="flex items-center space-x-4">
                            {/* Search Bar */}
                            <div className="relative hidden lg:block">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="Buscar productos, tiendas..."
                                    className="pl-9 pr-4 py-2 w-64 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>

                            {/* Date Selector */}
                            <select className="bg-gray-50 border border-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
                                <option>Últimos 7 días</option>
                                <option>Últimos 30 días</option>
                                <option>Este mes</option>
                            </select>

                            {/* Icons */}
                            <button className="relative p-2 text-gray-400 hover:text-gray-600 transition-colors">
                                <Bell className="w-5 h-5" />
                                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full"></span>
                            </button>
                            <button className="p-1 border-2 border-transparent hover:border-gray-200 rounded-full transition-all">
                                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                                    <User className="w-4 h-4" />
                                </div>
                            </button>
                        </div>
                    </div>
                </header>

                {/* Scrollable Content Area */}
                <div className="flex-1 overflow-auto p-8">
                    <div className="max-w-7xl mx-auto space-y-6">
                        {/* KPI Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {/* Card 1 */}
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                                <p className="text-sm font-medium text-gray-500 mb-1">
                                    Búsquedas Totales
                                </p>
                                <div className="flex items-baseline space-x-2">
                                    <h3 className="text-2xl font-bold text-gray-900">1,245</h3>
                                    <span className="text-sm font-medium text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                                        +12.5% vs sem. pasada
                                    </span>
                                </div>
                            </div>

                            {/* Card 2 */}
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                                <p className="text-sm font-medium text-gray-500 mb-1">
                                    Producto Top
                                </p>
                                <div className="flex flex-col">
                                    <h3 className="text-lg font-bold text-gray-900 truncate">
                                        Acetaminofén
                                    </h3>
                                    <span className="text-sm font-medium text-orange-600 mt-1">
                                        High Demand
                                    </span>
                                </div>
                            </div>

                            {/* Card 3 */}
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                                <p className="text-sm font-medium text-gray-500 mb-1">
                                    Precio Promedio
                                </p>
                                <div className="flex items-baseline space-x-2">
                                    <h3 className="text-2xl font-bold text-gray-900">$1.50</h3>
                                    <span className="text-sm font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                                        Estable
                                    </span>
                                </div>
                            </div>

                            {/* Card 4 */}
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                                <p className="text-sm font-medium text-gray-500 mb-1">
                                    Variación Semanal
                                </p>
                                <div className="flex items-baseline space-x-2">
                                    <h3 className="text-2xl font-bold text-green-600">+2.4%</h3>
                                    <span className="text-sm font-medium text-red-500 bg-red-50 px-1.5 py-0.5 rounded">
                                        -0.5% en margen
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Central Section: Charts & Map */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Line Chart */}
                            <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col">
                                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                    Evolución de Precios (últ. 30 días)
                                </h2>
                                <div className="flex-1 w-full min-h-[300px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={mockChartData}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                            <XAxis
                                                dataKey="date"
                                                axisLine={false}
                                                tickLine={false}
                                                tick={{ fill: "#6B7280", fontSize: 12 }}
                                                dy={10}
                                            />
                                            <YAxis
                                                yAxisId="left"
                                                axisLine={false}
                                                tickLine={false}
                                                tick={{ fill: "#6B7280", fontSize: 12 }}
                                                dx={-10}
                                                domain={["auto", "auto"]}
                                                unit="$"
                                            />
                                            <YAxis
                                                yAxisId="right"
                                                orientation="right"
                                                axisLine={false}
                                                tickLine={false}
                                                tick={{ fill: "#6B7280", fontSize: 12 }}
                                                dx={10}
                                                domain={["auto", "auto"]}
                                                unit="Bs"
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    borderRadius: "8px",
                                                    border: "none",
                                                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                                                }}
                                            />
                                            <Legend verticalAlign="top" height={36} />
                                            <Line
                                                yAxisId="left"
                                                type="monotone"
                                                dataKey="usd"
                                                name="Precio USD"
                                                stroke="#2563eb"
                                                strokeWidth={2}
                                                dot={{ r: 4, strokeWidth: 2 }}
                                                activeDot={{ r: 6 }}
                                            />
                                            <Line
                                                yAxisId="right"
                                                type="monotone"
                                                dataKey="ves"
                                                name="Precio VES"
                                                stroke="#16a34a"
                                                strokeWidth={2}
                                                dot={{ r: 4, strokeWidth: 2 }}
                                                activeDot={{ r: 6 }}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Heatmap Placeholder */}
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col">
                                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                    Mapa de Calor
                                </h2>
                                <div className="flex-1 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-indigo-100 flex flex-col items-center justify-center p-6 text-center min-h-[300px]">
                                    <div className="w-16 h-16 bg-white rounded-full shadow flex items-center justify-center mb-4">
                                        <svg
                                            className="w-8 h-8 text-indigo-500"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                            xmlns="http://www.w3.org/2000/svg"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                                            />
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                                            />
                                        </svg>
                                    </div>
                                    <h3 className="text-lg font-bold text-gray-800">
                                        Región Principal:
                                    </h3>
                                    <p className="text-2xl font-bold text-indigo-600 mt-1">Caracas</p>
                                    <p className="text-sm text-gray-500 mt-2">
                                        78% de la demanda actual
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Bottom Table */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                            <div className="p-5 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <h2 className="text-lg font-semibold text-gray-900">
                                    Detalle de Productos
                                </h2>
                                <div className="flex items-center space-x-3">
                                    <button className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-sm">
                                        <Filter className="w-4 h-4 mr-2" />
                                        Filtros
                                    </button>
                                    <button className="flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 transition-colors shadow-sm">
                                        <Download className="w-4 h-4 mr-2" />
                                        Exportar CSV
                                    </button>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Producto
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Tienda
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Precio USD
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Precio VES
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Fecha
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Estado
                                            </th>
                                            <th
                                                scope="col"
                                                className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                                            >
                                                Acción
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {loading ? (
                                            <tr>
                                                <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                                                    <div className="flex flex-col items-center justify-center">
                                                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
                                                        Cargando datos...
                                                    </div>
                                                </td>
                                            </tr>
                                        ) : products.length === 0 ? (
                                            <tr>
                                                <td colSpan={7} className="px-6 py-10 text-center text-gray-500">
                                                    No se encontraron productos.
                                                </td>
                                            </tr>
                                        ) : (
                                            products.map((item, idx) => (
                                                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex items-center">
                                                            <div className="flex-shrink-0 h-10 w-10 bg-gray-100 rounded-lg flex items-center justify-center text-gray-500 border border-gray-200">
                                                                {item.imagen ? (
                                                                    <Image src={item.imagen} alt={item.nombre || "Product"} width={40} height={40} className="h-full w-full object-cover rounded-lg" />
                                                                ) : (
                                                                    <FileText className="h-5 w-5" />
                                                                )}
                                                            </div>
                                                            <div className="ml-4">
                                                                <div className="text-sm font-medium text-gray-900 truncate max-w-[200px]" title={item.nombre}>
                                                                    {item.nombre || "Producto sin nombre"}
                                                                </div>
                                                                <div className="text-sm text-gray-500">
                                                                    {item.marca || "Sin marca"}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                                                        {item.ofertas?.[0]?.cadena || "Farmatodo"}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                                                        ${(item.ofertas?.[0]?.precio_usd || 0).toFixed(2)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                                                        Bs {(item.ofertas?.[0]?.precio_ves || 0).toFixed(2)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {item.fecha ? new Date(item.fecha).toLocaleDateString() : "24/03/2026"}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className="px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                                            Activo
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                        <button className="text-blue-600 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-3 py-1 rounded-md transition-colors">
                                                            Ver detalles
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
