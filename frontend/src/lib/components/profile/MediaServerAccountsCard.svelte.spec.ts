import { page } from '@vitest/browser/context';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';

import type { ProfileServiceConnection } from '$lib/queries/profile/types';

const h = vi.hoisted(() => ({
	connections: [] as Array<{ service: string; enabled: boolean; username: string }>,
	isPending: false,
	connectNavidrome: vi.fn().mockResolvedValue({}),
	disconnect: vi.fn().mockResolvedValue({})
}));

vi.mock('$lib/queries/connections/ConnectionsQuery.svelte', () => ({
	getConnectionsQuery: () => ({
		get data() {
			return { connections: h.connections };
		},
		get isPending() {
			return h.isPending;
		}
	})
}));

vi.mock('$lib/queries/connections/ConnectionsMutations.svelte', () => ({
	createConnectNavidromeMutation: () => ({ mutateAsync: h.connectNavidrome, isPending: false }),
	createDisconnectMutation: () => ({ mutateAsync: h.disconnect, isPending: false })
}));

import MediaServerAccountsCard from './MediaServerAccountsCard.svelte';

const ALL_SERVICES: ProfileServiceConnection[] = [
	{ name: 'Navidrome', enabled: true, username: 'admin', url: 'http://nd.local' }
];

beforeEach(() => {
	h.connections = [];
	h.isPending = false;
	vi.clearAllMocks();
});

describe('MediaServerAccountsCard.svelte', () => {
	it('renders a row per admin-enabled server with the shared-account caption', async () => {
		render(MediaServerAccountsCard, { services: ALL_SERVICES });
		await expect
			.element(page.getByRole('heading', { name: 'Media Server Accounts', level: 2 }))
			.toBeInTheDocument();
		await expect.element(page.getByText('Navidrome', { exact: true })).toBeInTheDocument();
		expect(page.getByText('Plays use the shared account').elements().length).toBe(1);
	});

	it('renders nothing when no media server is enabled', async () => {
		const { container } = render(MediaServerAccountsCard, {
			services: ALL_SERVICES.map((s) => ({ ...s, enabled: false }))
		});
		expect(container.querySelector('section')).toBeNull();
	});

	it('links a Navidrome account through the credentials form', async () => {
		render(MediaServerAccountsCard, { services: ALL_SERVICES });
		await page.getByRole('button', { name: 'Connect' }).click();
		await page.getByPlaceholder('Navidrome username').fill('alice');
		await page.getByPlaceholder('Password').fill('pw-1');
		await page.getByRole('button', { name: 'Link account' }).click();
		expect(h.connectNavidrome).toHaveBeenCalledWith({ username: 'alice', password: 'pw-1' });
	});

	it('shows the linked identity and disconnects', async () => {
		h.connections = [{ service: 'navidrome', enabled: true, username: 'alice_nd' }];
		render(MediaServerAccountsCard, { services: ALL_SERVICES });
		await expect.element(page.getByText('Plays count as @alice_nd')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Disconnect' }).click();
		expect(h.disconnect).toHaveBeenCalledWith('navidrome');
	});

	it('surfaces a link error inline', async () => {
		h.connectNavidrome.mockRejectedValueOnce(new Error('boom'));
		render(MediaServerAccountsCard, { services: ALL_SERVICES });
		await page.getByRole('button', { name: 'Connect' }).click();
		await page.getByPlaceholder('Navidrome username').fill('alice');
		await page.getByPlaceholder('Password').fill('bad');
		await page.getByRole('button', { name: 'Link account' }).click();
		await expect.element(page.getByText('Could not sign in to Navidrome.')).toBeInTheDocument();
	});
});
