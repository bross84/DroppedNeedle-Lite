import { describe, expect, it } from 'vitest';

import { SourcePlaylistQueryKeyFactory } from './SourcePlaylistQueryKeyFactory';

describe('SourcePlaylistQueryKeyFactory', () => {
	it('separates persisted playlist data by DroppedNeedle user', () => {
		expect(SourcePlaylistQueryKeyFactory.list('alice', 'navidrome', 200)).not.toEqual(
			SourcePlaylistQueryKeyFactory.list('bob', 'navidrome', 200)
		);
	});

	it('nests detail under the user and source prefix', () => {
		expect(SourcePlaylistQueryKeyFactory.detail('alice', 'navidrome', 'playlist-1')).toEqual([
			'source-playlists',
			'alice',
			'navidrome',
			'detail',
			'playlist-1'
		]);
	});
});
