<script lang="ts">
	import '../../auth.css';
	import { goto } from '$app/navigation';
	import { authStore } from '$lib/stores/authStore.svelte';
	import { ApiError } from '$lib/api/client';
	import { getAuthProvidersQuery } from '$lib/queries/auth/AuthProvidersQuery.svelte';
	import {
		createLocalLoginMutation,
		createOidcAuthorizeMutation
	} from '$lib/queries/auth/AuthMutations.svelte';
	import {
		toAuthUser,
		type AuthProviders,
		type AuthSessionResponse
	} from '$lib/queries/auth/types';
	import { Eye, EyeOff } from 'lucide-svelte';

	type Tab = 'local' | 'oidc';

	const DEFAULT_PROVIDERS: AuthProviders = {
		local: true,
		oidc: false
	};

	const providersQuery = getAuthProvidersQuery();
	const providers = $derived(providersQuery.data ?? DEFAULT_PROVIDERS);

	let activeTab = $state<Tab>('local');
	// auto-select a tab once providers load, but never override a user's choice
	let tabInitialised = false;
	$effect(() => {
		if (tabInitialised || !providersQuery.isSuccess) return;
		tabInitialised = true;
		if (!providers.local && providers.oidc) activeTab = 'oidc';
	});

	let username = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let localError = $state<string | null>(null);
	const localLogin = createLocalLoginMutation();

	let oidcLoading = $state(false);
	let oidcError = $state<string | null>(null);
	const oidcAuthorize = createOidcAuthorizeMutation();

	function storeSession(data: AuthSessionResponse) {
		authStore.setUser(toAuthUser(data.user));
		goto('/');
	}

	async function handleLocalLogin() {
		localError = null;
		try {
			storeSession(await localLogin.mutateAsync({ username, password }));
		} catch (e) {
			localError = e instanceof ApiError ? e.message : 'Could not reach the server';
		}
	}

	async function handleOidcLogin() {
		oidcError = null;
		oidcLoading = true;
		try {
			const { redirect_url } = await oidcAuthorize.mutateAsync();
			window.location.href = redirect_url;
		} catch {
			oidcError = 'SSO is not configured';
			oidcLoading = false;
		}
	}

	const availableTabs = $derived((['local', 'oidc'] as Tab[]).filter((t) => providers[t]));
</script>

<svelte:head>
	<title>Sign in - DroppedNeedle</title>
</svelte:head>

<div class="login-wrap grain min-h-screen flex items-center justify-center p-4">
	<div class="w-full max-w-md">
		<div class="login-brand">
			<img src="/logo_icon.png" alt="" aria-hidden="true" class="login-mark" />
			<h1 class="login-wordmark">DroppedNeedle</h1>
			<div class="login-rule" aria-hidden="true"></div>
			<p class="login-sub">Sign in to continue</p>
		</div>

		<div class="bg-base-200 rounded-box shadow-lg border border-base-300">
			{#if availableTabs.length > 1}
				<div class="flex border-b border-base-300 px-2 pt-2">
					{#each availableTabs as tab (tab)}
						<button
							class="tab-btn"
							class:tab-btn-active={activeTab === tab}
							onclick={() => (activeTab = tab)}
						>
							{tab === 'local' ? 'Username' : 'SSO'}
						</button>
					{/each}
				</div>
			{/if}

			<div class="p-6">
				{#if activeTab === 'local'}
					<form
						onsubmit={(e) => {
							e.preventDefault();
							void handleLocalLogin();
						}}
						class="flex flex-col gap-4"
					>
						<fieldset class="fieldset">
							<legend class="fieldset-legend">Username</legend>
							<input
								type="text"
								class="input input-bordered w-full"
								placeholder="Username"
								bind:value={username}
								required
								autocomplete="username"
							/>
						</fieldset>
						<fieldset class="fieldset">
							<legend class="fieldset-legend">Password</legend>
							<label class="input input-bordered flex items-center gap-2 w-full">
								{#if showPassword}
									<input
										type="text"
										class="grow"
										placeholder="Password"
										bind:value={password}
										required
										autocomplete="current-password"
									/>
								{:else}
									<input
										type="password"
										class="grow"
										placeholder="Password"
										bind:value={password}
										required
										autocomplete="current-password"
									/>
								{/if}
								<button
									type="button"
									onclick={() => (showPassword = !showPassword)}
									class="opacity-50 hover:opacity-100 transition-opacity"
									aria-label="Toggle password visibility"
								>
									{#if showPassword}<EyeOff class="h-4 w-4" />{:else}<Eye class="h-4 w-4" />{/if}
								</button>
							</label>
							<div class="mt-1 flex justify-end">
								<a href="/recover-password" class="link link-primary text-xs font-medium">
									Forgot password?
								</a>
							</div>
						</fieldset>
						{#if localError}
							<div class="alert alert-error py-2 text-sm">{localError}</div>
						{/if}
						<button type="submit" class="btn btn-primary w-full" disabled={localLogin.isPending}>
							{#if localLogin.isPending}<span class="loading loading-spinner loading-sm"
								></span>{/if}
							Sign in
						</button>
					</form>
				{:else if activeTab === 'oidc'}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-base-content/60">
							Sign in using your organisation's single sign-on provider.
						</p>
						{#if oidcError}
							<div class="alert alert-error py-2 text-sm">{oidcError}</div>
						{/if}
						<button
							class="btn btn-primary w-full"
							onclick={() => void handleOidcLogin()}
							disabled={oidcLoading}
						>
							{#if oidcLoading}<span class="loading loading-spinner loading-sm"></span>{/if}
							Continue with SSO
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.tab-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.5rem 0.85rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: oklch(from var(--color-base-content) l c h / 0.45);
		border-bottom: 2px solid transparent;
		transition: all 0.15s ease;
		cursor: pointer;
		background: none;
		border-top: none;
		border-left: none;
		border-right: none;
		margin-bottom: -1px;
	}
	.tab-btn:hover {
		color: oklch(from var(--color-base-content) l c h / 0.7);
	}
	.tab-btn-active {
		color: oklch(from var(--color-primary) l c h / 1);
		border-bottom-color: oklch(from var(--color-primary) l c h / 1);
	}

	.login-wrap {
		--grain-opacity: 0.1;
		position: relative;
		isolation: isolate;
		background:
			radial-gradient(
				circle at 50% -8rem,
				oklch(from var(--color-primary) l c h / 0.08),
				transparent 22rem
			),
			var(--color-base-100);
	}

	.login-brand {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 2rem;
	}

	.login-mark {
		height: 3rem;
		width: auto;
		margin-bottom: 0.25rem;
		opacity: 0.9;
	}

	.login-wordmark {
		font-family: var(--font-display);
		font-weight: 800;
		font-size: clamp(2.75rem, 14vw, 4rem);
		line-height: 0.85;
		letter-spacing: 0.01em;
		color: oklch(from var(--color-base-content) l c h / 0.95);
		text-shadow: 0 2px 1px rgb(0 0 0 / 0.4);
	}

	.login-rule {
		height: 2px;
		width: 7rem;
		border-radius: 999px;
		background: linear-gradient(
			to right,
			transparent,
			oklch(from var(--color-primary) l c h / 0.6),
			oklch(from var(--color-accent) l c h / 0.6),
			transparent
		);
	}

	.login-sub {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: oklch(from var(--color-base-content) l c h / 0.5);
	}
</style>
