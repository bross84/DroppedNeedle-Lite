import { describe, it, expect, vi, beforeEach } from 'vitest';

class FakeEventSource {
	static instances: FakeEventSource[] = [];
	url: string;
	listeners: Record<string, (e: Event) => void> = {};
	constructor(url: string) {
		this.url = url;
		FakeEventSource.instances.push(this);
	}
	addEventListener(type: string, cb: (e: Event) => void) {
		this.listeners[type] = cb;
	}
	close() {}
	emit(type: string, data: unknown) {
		this.listeners[type]?.({ data: JSON.stringify(data) } as MessageEvent);
	}
}

vi.stubGlobal('EventSource', FakeEventSource);
vi.mock('$lib/stores/toast', () => ({ toastStore: { show: vi.fn() } }));
vi.mock('$lib/queries/QueryClient', () => ({ invalidateQueriesWithPersister: vi.fn() }));
vi.mock('$lib/stores/authStore.svelte', () => ({
	authStore: { user: { id: 'userA' } }
}));

import { toastStore } from '$lib/stores/toast';
import { invalidateQueriesWithPersister } from '$lib/queries/QueryClient';
import { FollowQueryKeyFactory } from './FollowQueryKeyFactory';
import { createFollowingEvents } from './FollowingEvents';

const mockShow = vi.mocked(toastStore.show);
const mockInvalidate = vi.mocked(invalidateQueriesWithPersister);

beforeEach(() => {
	vi.clearAllMocks();
	FakeEventSource.instances = [];
	// FollowingEvents persists its seen-id de-dupe sets to sessionStorage; in
	// environments where a real (non-jsdom) sessionStorage global is present
	// (e.g. Node's built-in Web Storage), state leaks across tests/files
	// unless cleared - reset it so each test starts from a clean de-dupe state.
	if (typeof sessionStorage !== 'undefined') sessionStorage.clear();
});

describe('FollowingEvents', () => {
	it('toasts a weekly-mix refresh once and ignores the replayed snapshot', () => {
		const fe = createFollowingEvents();
		fe.start();
		const payload = { event_id: 'evt-1', playlist_id: 'pl-1', track_count: 42 };

		FakeEventSource.instances[0].emit('personal_mix_refreshed', payload);
		expect(mockShow).toHaveBeenCalledTimes(1);

		// SSEPublisher replays its last payload to every new subscriber
		FakeEventSource.instances[0].emit('personal_mix_refreshed', payload);
		expect(mockShow).toHaveBeenCalledTimes(1);
	});

	it('ignores a malformed payload without throwing', () => {
		const fe = createFollowingEvents();
		fe.start();
		FakeEventSource.instances[0].listeners['personal_mix_refreshed']?.({
			data: 'not json'
		} as MessageEvent);
		expect(mockShow).not.toHaveBeenCalled();
	});

	it('refreshes the wanted list when the watcher reports new candidates', () => {
		const fe = createFollowingEvents();
		fe.start();
		FakeEventSource.instances[0].emit('wanted_new_candidates', {});
		expect(mockInvalidate).toHaveBeenCalled();
	});
});
