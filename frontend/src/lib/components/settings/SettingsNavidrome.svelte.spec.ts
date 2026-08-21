import { page } from '@vitest/browser/context';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';

const h = vi.hoisted(() => ({
	load: vi.fn(),
	save: vi.fn(),
	test: vi.fn(),
	cleanup: vi.fn()
}));

vi.mock('$lib/utils/settingsForm.svelte', () => ({
	createSettingsForm: () => ({
		data: { navidrome_url: 'http://localhost:4533', username: '', password: '', enabled: false },
		loading: false,
		saving: false,
		testing: false,
		message: '',
		messageType: 'success',
		testResult: null,
		wasAlreadyEnabled: false,
		load: h.load,
		save: h.save,
		test: h.test,
		cleanup: h.cleanup
	})
}));

import SettingsNavidrome from './SettingsNavidrome.svelte';

describe('SettingsNavidrome', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('points admins to their profile to finish connecting their own account', async () => {
		// Regression: this form only sets the server-wide URL/enabled flag - it never
		// completes a connection by itself. Nothing told an operator that a second,
		// per-user step in Profile > Media Accounts was still required, so this was
		// found only by poking around after Settings appeared to succeed.
		render(SettingsNavidrome);

		const link = page.getByRole('link', { name: 'profile' });
		await expect.element(link).toBeVisible();
		await expect.element(link).toHaveAttribute('href', '/profile#media-accounts');
	});
});
