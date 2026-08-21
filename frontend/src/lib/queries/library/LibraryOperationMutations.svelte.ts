import { createMutation } from '@tanstack/svelte-query';
import { api } from '$lib/api/client';
import { API } from '$lib/constants';
import { invalidateQueriesWithPersister } from '$lib/queries/QueryClient';
import { toastStore } from '$lib/stores/toast';
import { LibraryQueryKeyFactory } from './LibraryQueryKeyFactory';
import type {
	IdentificationControlResponse,
	OperationResponse,
	ScanControlResponse,
	ScanKind,
	ScanRunRequestedResponse
} from './LibraryOperationsTypes';

async function invalidateWork(): Promise<void> {
	await Promise.all([
		invalidateQueriesWithPersister({ queryKey: LibraryQueryKeyFactory.activityPrefix() }),
		invalidateQueriesWithPersister({ queryKey: LibraryQueryKeyFactory.operationsPrefix() })
	]);
}

/**
 * Report what the server actually decided.
 *
 * A scan request has five outcomes and three of them mean no new work will
 * run: the request was folded into a run that already covers it, merged into
 * one already queued, or rejected because incompatible work holds the
 * follow-up slot. Reporting all five as "queued" makes an absorbed request
 * indistinguishable from one that started - the operator clicks, is told it
 * worked, and nothing happens.
 */
export function describeScanRequest(result: ScanRunRequestedResponse | undefined): {
	message: string;
	type: 'success' | 'error' | 'info';
} {
	switch (result?.disposition) {
		case 'started':
			return { message: 'Library work started', type: 'success' };
		case 'queued':
			return { message: 'Library work queued', type: 'success' };
		case 'expanded':
			return { message: 'Added to the library work already queued', type: 'success' };
		case 'coalesced':
			return {
				message: 'Library work already in progress covers this - nothing new was queued',
				type: 'info'
			};
		case 'conflict':
			return {
				message:
					result.queued_reason ??
					`Blocked: ${result.conflicting_kind ?? 'other'} work is already waiting to run`,
				type: 'error'
			};
		default:
			// absent or unrecognised outcome: report that the request was sent and
			// claim nothing about whether work will actually run
			return { message: 'Library work requested', type: 'info' };
	}
}

export function requestLibraryRun() {
	return createMutation(() => ({
		mutationFn: (input: {
			kind: ScanKind;
			scope_ids: string[];
			expected_policy_revision: string;
		}) => api.global.post<ScanRunRequestedResponse>(API.library.scanRuns(), input),
		onSuccess: async (result) => {
			await invalidateWork();
			toastStore.show(describeScanRequest(result));
		},
		onError: (error: Error) =>
			toastStore.show({
				message: `Could not queue library work: ${error.message}`,
				type: 'error'
			})
	}));
}

export function controlLibraryRun(action: 'pause' | 'resume' | 'stop') {
	return createMutation(() => ({
		mutationFn: (input: { runId: string; expectedRevision: number }) => {
			const url =
				action === 'pause'
					? API.library.pauseScanRun(input.runId)
					: action === 'resume'
						? API.library.resumeScanRun(input.runId)
						: API.library.stopScanRun(input.runId);
			return api.global.post<ScanControlResponse>(url, {
				expected_revision: input.expectedRevision
			});
		},
		onSuccess: invalidateWork,
		onError: () => toastStore.show({ message: `Could not ${action} the scan`, type: 'error' })
	}));
}

export function controlIdentification(action: 'pause' | 'resume') {
	return createMutation(() => ({
		mutationFn: (expectedRevision: number) =>
			api.global.post<IdentificationControlResponse>(
				action === 'pause' ? API.library.pauseIdentification() : API.library.resumeIdentification(),
				{ expected_revision: expectedRevision }
			),
		onSuccess: invalidateWork,
		onError: () => toastStore.show({ message: `Could not ${action} identification`, type: 'error' })
	}));
}

export function controlLibraryOperation(action: 'pause' | 'resume' | 'stop') {
	return createMutation(() => ({
		mutationFn: (input: { jobId: string; expectedRevision: number }) => {
			const url =
				action === 'pause'
					? API.library.pauseOperation(input.jobId)
					: action === 'resume'
						? API.library.resumeOperation(input.jobId)
						: API.library.stopOperation(input.jobId);
			return api.global.post<OperationResponse>(url, {
				expected_row_revision: input.expectedRevision
			});
		},
		onSuccess: invalidateWork,
		onError: () => toastStore.show({ message: `Could not ${action} this job`, type: 'error' })
	}));
}
