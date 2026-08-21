import { page } from '@vitest/browser/context';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';

const h = vi.hoisted(() => ({
	load: vi.fn(),
	save: vi.fn(),
	cleanup: vi.fn()
}));

vi.mock('$lib/utils/settingsForm.svelte', () => ({
	createSettingsForm: () => ({
		data: { api_key: '', shared_secret: '', session_key: '', username: '', enabled: false },
		loading: false,
		saving: false,
		message: '',
		messageType: 'success',
		load: h.load,
		save: h.save,
		cleanup: h.cleanup
	})
}));

import SettingsLastFmApp from './SettingsLastFmApp.svelte';

describe('SettingsLastFmApp', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('links straight to the profile section that finishes the per-user connection', async () => {
		// These are app-level credentials only; the per-user OAuth step lives in the
		// profile's Scrobbling & Discovery card. The link used to land on the bare
		// profile page, leaving the operator to find that card themselves.
		render(SettingsLastFmApp);

		const link = page.getByRole('link', { name: 'profile' });
		await expect.element(link).toBeVisible();
		await expect.element(link).toHaveAttribute('href', '/profile#scrobbling');
	});
});
