import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';

vi.stubGlobal('window', globalThis);

describe('serviceStatusStore', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	it('starts empty', async () => {
		expect.assertions(1);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		expect(get(serviceStatusStore)).toEqual({});
	});

	it('records degradation from response body', async () => {
		expect.assertions(1);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.clear();

		serviceStatusStore.recordFromResponse({ musicbrainz: 'error', audiodb: 'degraded' });
		expect(get(serviceStatusStore)).toEqual({ musicbrainz: 'error', audiodb: 'degraded' });
	});

	it('records degradation from header string', async () => {
		expect.assertions(1);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.clear();

		serviceStatusStore.recordFromHeader('lastfm, musicbrainz');
		expect(get(serviceStatusStore)).toEqual({ lastfm: 'error', musicbrainz: 'error' });
	});

	it('ignores null/empty header', async () => {
		expect.assertions(2);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.clear();

		serviceStatusStore.recordFromHeader(null);
		expect(get(serviceStatusStore)).toEqual({});

		serviceStatusStore.recordFromHeader('');
		expect(get(serviceStatusStore)).toEqual({});
	});

	it('ignores null/empty response', async () => {
		expect.assertions(2);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.clear();

		serviceStatusStore.recordFromResponse(null);
		expect(get(serviceStatusStore)).toEqual({});

		serviceStatusStore.recordFromResponse({});
		expect(get(serviceStatusStore)).toEqual({});
	});

	it('merges multiple degradation signals', async () => {
		expect.assertions(1);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.clear();

		serviceStatusStore.recordFromResponse({ musicbrainz: 'error' });
		serviceStatusStore.recordFromHeader('lastfm');
		expect(get(serviceStatusStore)).toEqual({ musicbrainz: 'error', lastfm: 'error' });
	});

	it('clear resets store to empty', async () => {
		expect.assertions(1);
		const { serviceStatusStore } = await import('$lib/stores/serviceStatus');
		serviceStatusStore.recordFromResponse({ musicbrainz: 'error' });
		serviceStatusStore.clear();
		expect(get(serviceStatusStore)).toEqual({});
	});
});
