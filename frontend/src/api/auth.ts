import { http } from "./client";
import { setAccessToken } from "./token";
import type { TokenResponse, UserCreate, UserResponse } from "../types/api";

/** Builds the OAuth2 form-urlencoded body for the login endpoint. */
function loginBody(email: string, password: string): URLSearchParams {
  const params = new URLSearchParams();
  params.set("grant_type", "password");
  params.set("username", email);
  params.set("password", password);
  return params;
}

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const token = await http.post<TokenResponse>(
    "/api/v1/auth/login",
    undefined,
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      rawBody: loginBody(email, password),
    },
  );
  setAccessToken(token.access_token);
  return token;
}

export async function register(user: UserCreate): Promise<UserResponse> {
  return http.post<UserResponse>("/api/v1/auth/register", user);
}

export async function fetchMe(): Promise<UserResponse> {
  return http.get<UserResponse>("/api/v1/auth/me");
}

export function logout(): void {
  setAccessToken(null);
}