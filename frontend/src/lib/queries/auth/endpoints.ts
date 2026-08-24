/** Auth endpoints. Login/setup happen before a session exists, so those are
 * called via the unauthenticated `api.global` client. */
export const AUTH_ENDPOINTS = {
	providers: '/api/v1/auth/providers',
	login: '/api/v1/auth/login',
	setup: '/api/v1/auth/setup',
	oidcAuthorize: '/api/v1/auth/oidc/authorize',
	oidcExchange: '/api/v1/auth/oidc/exchange'
} as const;
