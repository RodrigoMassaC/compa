/**
 * Utilidades de autenticación para Compa.
 * Gestiona el token JWT y los datos del usuario en localStorage.
 */

const TOKEN_KEY = "compa_token";
const USER_KEY  = "compa_user";

export interface AuthUser {
  id_usuario:        string;
  email:             string;
  nombre_completo:   string;
  rol_usuario:       string;
  plan:              string;   // FREE | BASIC | PRO | ENTERPRISE
  estado_suscripcion: string;
  telefono_wa?:      string | null;
  ciudad?:           string | null;
  estado_ven?:       string | null;
  sexo?:             string | null;
}

// ── Leer ─────────────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ── Escribir / Borrar ─────────────────────────────────────────────────────────

export function saveAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── Headers con Bearer ────────────────────────────────────────────────────────

export function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

// ── Nombre de plan legible ────────────────────────────────────────────────────

export function planLabel(plan: string): string {
  const labels: Record<string, string> = {
    FREE:       "Plan Gratis",
    BASIC:      "Plan Básico",
    PRO:        "Plan Pro",
    ENTERPRISE: "Enterprise",
  };
  return labels[plan] ?? plan;
}
