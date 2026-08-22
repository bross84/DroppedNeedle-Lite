export function getSourceLabel(sourceType: string): string {
	if (sourceType === 'local') return 'Local';
	if (sourceType === 'navidrome') return 'Navidrome';
	if (sourceType === 'youtube') return 'YouTube';
	return 'Unknown';
}

export function getSourceColor(sourceType: string): string {
	if (sourceType === 'navidrome') return 'rgb(var(--brand-navidrome))';
	if (sourceType === 'local') return 'rgb(var(--brand-localfiles))';
	if (sourceType === 'youtube') return 'var(--color-youtube)';
	return 'currentColor';
}
