<script lang="ts">
	import { Loader2, ServerCog } from 'lucide-svelte';
	import { ApiError } from '$lib/api/client';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';
	import { getConnectionsQuery } from '$lib/queries/connections/ConnectionsQuery.svelte';
	import {
		createConnectNavidromeMutation,
		createDisconnectMutation
	} from '$lib/queries/connections/ConnectionsMutations.svelte';
	import type { ProfileServiceConnection } from '$lib/queries/profile/types';

	interface Props {
		services: ProfileServiceConnection[];
	}

	const { services }: Props = $props();

	const connectionsQuery = getConnectionsQuery();
	const connections = $derived(connectionsQuery.data?.connections ?? []);

	const navidromeEnabled = $derived(services.some((s) => s.name === 'Navidrome' && s.enabled));
	const anyEnabled = $derived(navidromeEnabled);

	const connectNavidromeMutation = createConnectNavidromeMutation();
	const disconnectMutation = createDisconnectMutation();

	interface CredentialFormState {
		open: boolean;
		username: string;
		password: string;
		error: string | null;
	}

	function emptyForm(): CredentialFormState {
		return { open: false, username: '', password: '', error: null };
	}

	let navidromeForm = $state(emptyForm());

	function errorMessage(e: unknown, fallback: string): string {
		return e instanceof ApiError ? e.message : fallback;
	}

	async function linkNavidrome() {
		navidromeForm.error = null;
		try {
			await connectNavidromeMutation.mutateAsync({
				username: navidromeForm.username.trim(),
				password: navidromeForm.password
			});
			navidromeForm = emptyForm();
		} catch (e) {
			navidromeForm.error = errorMessage(e, 'Could not sign in to Navidrome.');
		}
	}

	async function disconnect(service: string) {
		await disconnectMutation.mutateAsync(service);
	}

	interface Row {
		service: string;
		label: string;
		icon: typeof NavidromeIcon;
		tint: string;
	}

	const rows = $derived(
		[
			navidromeEnabled && {
				service: 'navidrome',
				label: 'Navidrome',
				icon: NavidromeIcon,
				tint: 'bg-green-500/10 text-green-400 ring-green-500/20'
			}
		].filter(Boolean) as Row[]
	);

	function linkedConnection(service: string) {
		return connections.find((c) => c.service === service);
	}
</script>

{#if anyEnabled}
	<section>
		<h2
			class="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-base-content/50"
		>
			<ServerCog class="h-4 w-4 text-accent" />
			Media Server Accounts
		</h2>

		<div
			class="glow-primary-soft space-y-3 rounded-2xl border border-base-300/50 bg-base-200/40 p-4 backdrop-blur-sm sm:p-5"
		>
			<p class="text-xs text-base-content/60">
				Link your own account on each server so plays and scrobbles count as you rather than the
				shared account.
			</p>

			{#if connectionsQuery.isPending}
				<div class="flex items-center justify-center py-10">
					<Loader2 class="h-5 w-5 animate-spin text-base-content/40" />
				</div>
			{:else}
				{#each rows as row (row.service)}
					{@const linked = linkedConnection(row.service)}
					{@const Icon = row.icon}
					<div>
						<div
							class="crate-card flex items-center justify-between gap-3 rounded-xl border border-base-300/40 bg-base-300/20 p-3"
						>
							<div class="flex min-w-0 items-center gap-3">
								<div
									class="flex h-10 w-10 items-center justify-center rounded-xl ring-1 {row.tint}"
								>
									<Icon class="h-[1.15rem] w-[1.15rem]" />
								</div>
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<span class="text-sm font-semibold">{row.label}</span>
										<span class="status {linked ? 'status-success' : 'status-error'} status-sm"
										></span>
									</div>
									{#if linked}
										<p class="truncate text-xs text-base-content/50">
											Plays count as @{linked.username || 'your account'}
										</p>
									{:else}
										<p class="text-xs text-base-content/30">Plays use the shared account</p>
									{/if}
								</div>
							</div>
							<div class="shrink-0">
								{#if linked}
									<button
										type="button"
										class="btn btn-ghost btn-xs rounded-full"
										onclick={() => disconnect(row.service)}
										disabled={disconnectMutation.isPending}
									>
										Disconnect
									</button>
								{:else if row.service === 'navidrome'}
									<button
										type="button"
										class="btn btn-primary btn-xs gap-1 rounded-full px-3 shadow-sm transition-transform hover:scale-[1.03]"
										onclick={() => (navidromeForm.open = !navidromeForm.open)}
									>
										Connect
									</button>
								{/if}
							</div>
						</div>

						{#if row.service === 'navidrome' && !linked && navidromeForm.open}
							<div
								class="mt-2 space-y-2 rounded-xl border border-base-300/40 bg-base-100/40 p-3 animate-fade-in-up"
							>
								<p class="text-xs text-base-content/60">
									Sign in with your own Navidrome username and password.
								</p>
								<input
									type="text"
									class="input input-sm input-soft w-full"
									placeholder="Navidrome username"
									bind:value={navidromeForm.username}
									autocomplete="off"
								/>
								<input
									type="password"
									class="input input-sm input-soft w-full"
									placeholder="Password"
									bind:value={navidromeForm.password}
									autocomplete="off"
								/>
								{#if navidromeForm.error}
									<p class="text-xs text-error">{navidromeForm.error}</p>
								{/if}
								<div class="flex justify-end gap-2">
									<button
										type="button"
										class="btn btn-ghost btn-xs rounded-full"
										onclick={() => (navidromeForm = emptyForm())}
									>
										Cancel
									</button>
									<button
										type="button"
										class="btn btn-primary btn-xs gap-1 rounded-full"
										onclick={linkNavidrome}
										disabled={connectNavidromeMutation.isPending ||
											!navidromeForm.username.trim() ||
											!navidromeForm.password}
									>
										{#if connectNavidromeMutation.isPending}
											<Loader2 class="h-3.5 w-3.5 animate-spin" />
										{/if}
										Link account
									</button>
								</div>
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	</section>
{/if}
