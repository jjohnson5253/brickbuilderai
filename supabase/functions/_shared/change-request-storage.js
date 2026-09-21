export function storedScreenshotPaths(row) {
  if (!row?.id || !Array.isArray(row.screenshots)) return [];
  const prefix = `${row.id}/`;
  return [...new Set(row.screenshots.filter((path) =>
    typeof path === 'string'
    && path.startsWith(prefix)
    && !path.includes('..')
    && /^[a-zA-Z0-9-]+\/[a-zA-Z0-9._-]+$/.test(path)))];
}

export async function purgeChangeRequestScreenshots(db, bucket, row) {
  const paths = storedScreenshotPaths(row);
  if (paths.length) {
    const removed = await db.storage.from(bucket).remove(paths);
    if (removed.error) throw removed.error;
  }
  if (row?.id) {
    const cleared = await db.from('change_requests').update({ screenshots: [] }).eq('id', row.id);
    if (cleared.error) throw cleared.error;
  }
  return paths.length;
}
