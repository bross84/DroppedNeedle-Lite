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
		data: { store_region: 'GB' },
		loading: false,
		saving: false,
		message: '',
		messageType: 'success',
		load: h.load,
		save: h.save,
		cleanup: h.cleanup
	})
}));

import SettingsGetIt from './SettingsGetIt.svelte';

describe('SettingsGetIt', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('keeps the regional storefront setting', async () => {
		render(SettingsGetIt);

		await expect.element(page.getByRole('combobox', { name: 'Store region' })).toHaveValue('GB');
		await page.getByRole('button', { name: 'Save' }).click();
		expect(h.save).toHaveBeenCalledOnce();
	});

});
