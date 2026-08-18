import { createQuery } from '@tanstack/svelte-query';
import { api } from '$lib/api/client';
import { API } from '$lib/constants';
import { authStore } from '$lib/stores/authStore.svelte';
import { FollowQueryKeyFactory } from './FollowQueryKeyFactory';

type Getter<T> = () => T;

/**
 * The admin sidebar badge count. Sums the approval kinds that still exist:
 * album requests awaiting approval, plus weekly-mix auto-request grants. The
 * per-artist follow auto-download grants that used to be part of this total
 * were removed with the auto-download feature.
 */
export const getPendingApprovalCountQuery = (getEnabled: Getter<boolean>) =>
	createQuery(() => ({
		queryKey: FollowQueryKeyFactory.pendingApprovalCount(authStore.user?.id),
		queryFn: ({ signal }: { signal: AbortSignal }) =>
			api.global.get<{ count: number }>(API.requests.pendingApprovalCount(), { signal }),
		enabled: getEnabled() && !!authStore.user?.id,
		staleTime: 0,
		refetchInterval: 120_000,
		refetchIntervalInBackground: false,
		refetchOnReconnect: 'always' as const,
		refetchOnWindowFocus: 'always' as const
	}));
