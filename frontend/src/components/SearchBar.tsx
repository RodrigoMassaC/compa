"use client";

import { useState } from 'react';

export default function SearchBar({ onSearch, isSearching }: { onSearch: (query: string) => void, isSearching: boolean }) {
    const [query, setQuery] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.trim().length >= 2) {
            onSearch(query.trim());
        }
    };

    return (
        <form onSubmit={handleSubmit} className="w-full relative max-w-xl mx-auto mb-8">
            <div className="relative flex items-center w-full h-14 rounded-full focus-within:shadow-lg bg-white overflow-hidden border border-zinc-300 dark:border-zinc-700 dark:bg-zinc-800 transition-shadow">
                <div className="grid place-items-center h-full w-12 text-zinc-400">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
                <input
                    className="peer h-full w-full outline-none text-sm text-zinc-700 dark:text-zinc-200 dark:bg-zinc-800 pr-2"
                    type="text"
                    id="search"
                    placeholder="Busca harina, arroz, medicinas..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    disabled={isSearching}
                />
                <button
                    type="submit"
                    disabled={isSearching || query.trim().length < 2}
                    className="h-full px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:bg-blue-400 group flex items-center justify-center gap-2"
                >
                    {isSearching ? 'Buscando...' : 'Buscar'}
                </button>
            </div>
        </form>
    );
}
