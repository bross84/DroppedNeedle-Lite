import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toastStore } from './toast';

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
	toastStore.hide();
	vi.useRealTimers();
});

describe('toastStore', () => {
	it('clears a message once its duration elapses', () => {
		toastStore.show({ message: 'Saved', type: 'success', duration: 2000 });
		vi.advanceTimersByTime(1999);
		expect(get(toastStore)?.message).toBe('Saved');
		vi.advanceTimersByTime(1);
		expect(get(toastStore)).toBeNull();
	});

	it('does not let an earlier toast cut a later one short', () => {
		// Regression: show() armed a timer per call and never cancelled the
		// previous one, so the first toast's timer fired while the second was on
		// screen and blanked it early - here, after 500ms of its own 2000ms.
		toastStore.show({ message: 'FIRST', type: 'success', duration: 2000 });
		vi.advanceTimersByTime(1500);
		toastStore.show({ message: 'SECOND', type: 'error', duration: 2000 });

		vi.advanceTimersByTime(500); // FIRST's original timer would fire here
		expect(get(toastStore)?.message).toBe('SECOND');

		vi.advanceTimersByTime(1499);
		expect(get(toastStore)?.message).toBe('SECOND');
		vi.advanceTimersByTime(1);
		expect(get(toastStore)).toBeNull();
	});

	it('cancels the timer of a toast that was hidden early', () => {
		// hide() has to cancel the timer too, not just clear the value: otherwise
		// the dismissed toast's timer is still armed and fires on top of whatever
		// is on screen when it comes due.
		toastStore.show({ message: 'Dismissed early', type: 'info', duration: 2000 });
		vi.advanceTimersByTime(1000);
		toastStore.hide();
		toastStore.show({ message: 'Still here', type: 'success', duration: 2000 });

		vi.advanceTimersByTime(1000); // the dismissed toast's timer comes due here
		expect(get(toastStore)?.message).toBe('Still here');
	});

	it('keeps a zero-duration message up until it is replaced or hidden', () => {
		toastStore.show({ message: 'Persistent', type: 'error', duration: 0 });
		vi.advanceTimersByTime(60_000);
		expect(get(toastStore)?.message).toBe('Persistent');
		toastStore.hide();
		expect(get(toastStore)).toBeNull();
	});
});
