import { page } from '@vitest/browser/context';
import { afterEach, describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { toastStore } from '$lib/stores/toast';
import ToastHost from './ToastHost.svelte';

afterEach(() => toastStore.hide());

describe('ToastHost', () => {
	it('renders nothing until a message is shown', () => {
		// Toast.svelte carries no role, so query the container class directly
		// rather than a role that would make this assertion vacuous.
		const { container } = render(ToastHost);
		expect(container.querySelector('.toast')).toBeNull();
	});

	it('shows a message pushed through toastStore', async () => {
		// Regression: ~60 modules call toastStore.show(), but nothing in the app
		// subscribed to the store, so every success and failure message was
		// silently discarded - including "Could not queue library work".
		render(ToastHost);
		toastStore.show({ message: 'Library work started', type: 'success', duration: 0 });
		await expect.element(page.getByText('Library work started')).toBeVisible();
	});

	it('shows an error message', async () => {
		render(ToastHost);
		toastStore.show({ message: 'Select at least one library scope.', type: 'error', duration: 0 });
		await expect.element(page.getByText('Select at least one library scope.')).toBeVisible();
	});

	it('clears the message when the store is emptied', async () => {
		render(ToastHost);
		toastStore.show({ message: 'Storage cap saved', type: 'success', duration: 0 });
		await expect.element(page.getByText('Storage cap saved')).toBeVisible();
		toastStore.hide();
		await expect.element(page.getByText('Storage cap saved')).not.toBeInTheDocument();
	});
});
