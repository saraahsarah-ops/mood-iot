import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL = Platform.select({
  android: 'http://10.0.2.2:8010/api/v1',
  ios: 'http://localhost:8010/api/v1',
  default: 'http://localhost:8010/api/v1',
});

const STORAGE_KEYS = {
  ACCESS_TOKEN: '@mood_iot_access_token',
  REFRESH_TOKEN: '@mood_iot_refresh_token',
  USER: '@mood_iot_user',
} as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  user: {
    id: string;
    role: string;
  };
}

interface UserInfo {
  id: string;
  role: string;
}

// ---------------------------------------------------------------------------
// Token management
// ---------------------------------------------------------------------------

async function getToken(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
  } catch {
    return null;
  }
}

async function setToken(accessToken: string, refreshToken?: string): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken);
    if (refreshToken) {
      await AsyncStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
    }
  } catch (error) {
    console.error('Erreur sauvegarde token:', error);
  }
}

async function getRefreshToken(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
  } catch {
    return null;
  }
}

async function setUser(user: UserInfo): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
  } catch (error) {
    console.error('Erreur sauvegarde user:', error);
  }
}

async function getUser(): Promise<UserInfo | null> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.USER);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Auth check
// ---------------------------------------------------------------------------

async function isAuthenticated(): Promise<boolean> {
  const token = await getToken();
  return token !== null;
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.detail || 'Identifiants incorrects';
    throw new Error(message);
  }

  const data: LoginResponse = await response.json();

  await setToken(data.access_token, data.refresh_token);
  await setUser(data.user);

  return data;
}

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) {
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();
    await setToken(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

async function logout(): Promise<void> {
  try {
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.ACCESS_TOKEN,
      STORAGE_KEYS.REFRESH_TOKEN,
      STORAGE_KEYS.USER,
    ]);
  } catch (error) {
    console.error('Erreur logout:', error);
  }
}

// ---------------------------------------------------------------------------
// Authenticated fetch helper
// ---------------------------------------------------------------------------

async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  // If 401, attempt token refresh once then retry
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const newToken = await getToken();
      headers.Authorization = `Bearer ${newToken}`;
      return fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    }
  }

  return response;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const authService = {
  login,
  logout,
  getToken,
  setToken,
  getUser,
  isAuthenticated,
  refreshAccessToken,
  authFetch,
  API_BASE_URL,
};
