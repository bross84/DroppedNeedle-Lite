import { writable } from 'svelte/store';

interface Toast {
	message: string;
	type: 'success' | 'error' | 'info';
	duration?: number;
}

function createToastStore() {
	const { subscribe, set } = writable<Toast | null>(null);
	// Exactly one dismissal timer is live at a time. Without cancelling the
	// previous one, an earlier toast's timer stayed armed and blanked whichever
	// message had replaced it: showing a second toast 1.5s into the first one's
	// 2s window left the second on screen for 500ms instead of its own 2s.
	let timer: ReturnType<typeof setTimeout> | undefined;

	function stopTimer(): void {
		if (timer !== undefined) {
			clearTimeout(timer);
			timer = undefined;
		}
	}

	return {
		subscribe,
		show: (toast: Toast) => {
			stopTimer();
			set(toast);
			const duration = toast.duration ?? 3000;
			// 0 means "leave it up until something replaces it or hides it", the
			// same meaning Toast.svelte gives it via its own `duration > 0` check.
			// Nothing in the app passes 0; a caller that does owns dismissing it,
			// because Toast renders no close control.
			if (duration > 0) {
				timer = setTimeout(() => {
					timer = undefined;
					set(null);
				}, duration);
			}
		},
		hide: () => {
			stopTimer();
			set(null);
		}
	};
}

export const toastStore = createToastStore();
